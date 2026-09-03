"""Postgres (Neon) implementation — used when DATABASE_URL is set.

Connections are pooled and reused across requests. Opening a fresh
connection to Neon costs a TLS handshake plus authentication (several
network round trips, easily 200-500 ms from another region), and the old
one-connection-per-call pattern paid that price up to seven times for a
single tap on "+". Now a request borrows an already-open connection, runs
its queries and hands it back.

Pooled connections run in autocommit mode, so a plain read is a single
round trip and nothing is ever left "idle in transaction" (which would pin
a server connection behind Neon's pooler). Multi-statement writes open an
explicit transaction (see adjust_journee).

Use Neon's pooled connection string (the "-pooler" host) for DATABASE_URL.
"""
import secrets
import threading
import time

import psycopg2
import psycopg2.extensions

from .constants import DATE_RE, KEYS, META_KEYS, NOTE_MAX_LEN, VALID_PERSONS, VALID_STATUSES

_dsn = None

# ── tiny thread-safe connection pool ─────────────────────────────────
MAX_CONN = 5           # plenty for two people plus a background poll
STALE_AFTER = 60.0     # idle seconds after which a connection is pinged before reuse
ACQUIRE_TIMEOUT = 15   # seconds to wait for a free slot before giving up

_idle = []             # [(connection, last_used)] — a stack, so the warmest one is reused first
_idle_lock = threading.Lock()
_slots = threading.BoundedSemaphore(MAX_CONN)


def _connect():
    """Open a brand-new, transactional (non-autocommit) connection.
    Also used directly by scripts/migrate_sqlite_to_neon.py."""
    return psycopg2.connect(
        _dsn,
        connect_timeout=10,
        # notice a silently dropped connection within about a minute instead
        # of hanging on the next query
        keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
    )


def _open_pooled():
    con = _connect()
    con.autocommit = True
    return con


def _is_alive(con):
    try:
        with con.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        return False


def _discard(con):
    try:
        con.close()
    except Exception:
        pass


def _acquire():
    if not _slots.acquire(timeout=ACQUIRE_TIMEOUT):
        raise RuntimeError("database busy: no free connection")
    try:
        while True:
            with _idle_lock:
                if not _idle:
                    break
                con, last_used = _idle.pop()
            if con.closed:
                continue
            # After sitting idle for a while the other end may have hung up
            # (Neon suspends idle computes). Ping first, so a write never has
            # to be retried on an ambiguous failure.
            if time.monotonic() - last_used > STALE_AFTER and not _is_alive(con):
                _discard(con)
                continue
            return con
        return _open_pooled()
    except BaseException:
        _slots.release()
        raise


def _release(con, discard=False):
    if discard or con.closed:
        _discard(con)
    else:
        with _idle_lock:
            _idle.append((con, time.monotonic()))
    _slots.release()


def _run(fn):
    """Run fn(cursor) on a pooled connection and return its result.

    If the connection turns out to be dead (server closed it, network blip)
    it is dropped and fn is retried once on a fresh connection. Any other
    error rolls back a transaction fn may have opened, keeps the connection,
    and propagates."""
    last_err = None
    for _attempt in range(2):
        con = _acquire()
        try:
            with con.cursor() as cur:
                result = fn(cur)
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            _release(con, discard=True)
            last_err = e
            continue
        except Exception:
            try:
                if con.get_transaction_status() != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
                    with con.cursor() as cur:
                        cur.execute("ROLLBACK")
                _release(con)
            except Exception:
                _release(con, discard=True)
            raise
        _release(con)
        return result
    raise last_err


# ── schema ────────────────────────────────────────────────────────────
def init_db(database_url):
    global _dsn
    _dsn = database_url

    def q(cur):
        cur.execute("CREATE TABLE IF NOT EXISTS counters (id TEXT PRIMARY KEY, val INTEGER NOT NULL DEFAULT 0)")
        cur.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')")
        cur.execute("CREATE TABLE IF NOT EXISTS availability (person TEXT NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY (person, date))")
        cur.execute("""CREATE TABLE IF NOT EXISTS push_subscriptions (
            endpoint TEXT PRIMARY KEY,
            person TEXT NOT NULL,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL
        )""")
        cur.execute("CREATE TABLE IF NOT EXISTS ics_tokens (person TEXT PRIMARY KEY, token TEXT NOT NULL UNIQUE)")
        cur.execute("CREATE TABLE IF NOT EXISTS streaks (person TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0, type TEXT NOT NULL DEFAULT '')")
        cur.execute("""CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            person TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""")
        for k in KEYS:
            cur.execute("INSERT INTO counters (id, val) VALUES (%s, 0) ON CONFLICT (id) DO NOTHING", (k,))
        for k, v in (("theme", "theme-1"), ("message_zn", ""), ("message_nz", ""), ("jours_sans_course", "0")):
            cur.execute("INSERT INTO meta (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (k, v))
        for p in VALID_PERSONS:
            cur.execute(
                "INSERT INTO ics_tokens (person, token) VALUES (%s, %s) ON CONFLICT (person) DO NOTHING",
                (p, secrets.token_urlsafe(24)),
            )
            cur.execute(
                "INSERT INTO streaks (person, count, type) VALUES (%s, 0, '') ON CONFLICT (person) DO NOTHING",
                (p,),
            )
    _run(q)


# ── counters / journal ────────────────────────────────────────────────
def get_counters():
    def q(cur):
        cur.execute("SELECT id, val FROM counters")
        return dict(cur.fetchall())
    rows = _run(q)
    return {k: rows.get(k, 0) for k in KEYS}


def _shape_streaks(rows):
    result = {p: {"count": 0, "type": None} for p in VALID_PERSONS}
    for person, count, ttype in rows:
        if person in result:
            result[person] = {"count": count, "type": ttype or None}
    return result


def get_dashboard():
    """Everything the journal screen needs — counters, meta and streaks —
    fetched on a single connection."""
    def q(cur):
        cur.execute("SELECT id, val FROM counters")
        counters = dict(cur.fetchall())
        cur.execute("SELECT key, value FROM meta WHERE key = ANY(%s)", (list(META_KEYS),))
        meta = dict(cur.fetchall())
        cur.execute("SELECT person, count, type FROM streaks")
        return counters, meta, cur.fetchall()
    counters, meta, streaks = _run(q)
    data = {k: counters.get(k, 0) for k in KEYS}
    data.update({k: meta.get(k, "") for k in META_KEYS})
    data["streaks"] = _shape_streaks(streaks)
    return data


# Applies one journal tap to the person's running streak in a single
# statement (both SET expressions see the pre-update row, per SQL rules):
# +N on the same type extends the run, +N on the other type starts a new run
# of N; -N on the current type shortens it (back to "no streak" at 0); -N on
# the other type is a correction further back and leaves the current run alone.
_STREAK_SQL = """
    UPDATE streaks SET
      count = CASE
                WHEN %(d)s > 0 THEN CASE WHEN type = %(t)s THEN count + %(d)s ELSE %(d)s END
                WHEN type = %(t)s THEN GREATEST(0, count + %(d)s)
                ELSE count
              END,
      type  = CASE
                WHEN %(d)s > 0 THEN %(t)s
                WHEN type = %(t)s AND count + %(d)s <= 0 THEN ''
                ELSE type
              END
    WHERE person = %(p)s
"""


def adjust_journee(key, delta):
    """One tap on a journal counter: move the counter (never below 0) and
    update that person's streak, atomically. Returns True if the counter
    went up (the caller notifies the other person in that case)."""
    delta = int(delta)
    if key not in KEYS or not delta:
        return False
    person, ttype = key[0], key[1]

    def q(cur):
        cur.execute("BEGIN")
        cur.execute("UPDATE counters SET val = GREATEST(0, val + %s) WHERE id = %s", (delta, key))
        cur.execute(_STREAK_SQL, {"d": delta, "t": ttype, "p": person})
        cur.execute("COMMIT")
    _run(q)
    return delta > 0


def adjust_running(delta):
    if not delta:
        return
    _run(lambda cur: cur.execute(
        "UPDATE meta SET value = GREATEST(0, value::int + %s)::text WHERE key = 'jours_sans_course'",
        (int(delta),),
    ))


# ── meta ──────────────────────────────────────────────────────────────
def get_meta(keys):
    if not keys:
        return {}

    def q(cur):
        cur.execute("SELECT key, value FROM meta WHERE key = ANY(%s)", (list(keys),))
        return dict(cur.fetchall())
    rows = _run(q)
    return {k: rows.get(k, "") for k in keys}


def set_meta(data):
    items = [(k, "" if data[k] is None else str(data[k])) for k in META_KEYS if k in data]
    if not items:
        return

    def q(cur):
        for k, value in items:
            cur.execute(
                "INSERT INTO meta (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (k, value),
            )
    _run(q)


# ── availability ──────────────────────────────────────────────────────
def get_availability():
    def q(cur):
        cur.execute("SELECT person, date, status FROM availability")
        return cur.fetchall()
    result = {"z": {}, "n": {}}
    for person, date, status in _run(q):
        if person in result:
            result[person][date] = status
    return result


def set_availability(person, date, status):
    if person not in VALID_PERSONS or not DATE_RE.match(date or ""):
        return
    if status in VALID_STATUSES:
        _run(lambda cur: cur.execute(
            "INSERT INTO availability (person, date, status) VALUES (%s, %s, %s) "
            "ON CONFLICT (person, date) DO UPDATE SET status = EXCLUDED.status",
            (person, date, status),
        ))
    else:
        _run(lambda cur: cur.execute(
            "DELETE FROM availability WHERE person=%s AND date=%s", (person, date)
        ))


# ── push subscriptions ───────────────────────────────────────────────
def add_subscription(person, endpoint, p256dh, auth):
    if person not in VALID_PERSONS or not endpoint:
        return
    _run(lambda cur: cur.execute(
        "INSERT INTO push_subscriptions (endpoint, person, p256dh, auth) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (endpoint) DO UPDATE SET person=EXCLUDED.person, p256dh=EXCLUDED.p256dh, auth=EXCLUDED.auth",
        (endpoint, person, p256dh, auth),
    ))


def remove_subscription(endpoint):
    _run(lambda cur: cur.execute("DELETE FROM push_subscriptions WHERE endpoint=%s", (endpoint,)))


def get_subscriptions(person):
    def q(cur):
        cur.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE person=%s", (person,))
        return cur.fetchall()
    return [
        {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
        for endpoint, p256dh, auth in _run(q)
    ]


# ── ics subscription tokens ────────────────────────────────────────────
def get_ics_token(person):
    if person not in VALID_PERSONS:
        return None

    def q(cur):
        cur.execute("SELECT token FROM ics_tokens WHERE person=%s", (person,))
        return cur.fetchone()
    row = _run(q)
    return row[0] if row else None


def find_person_by_ics_token(token):
    if not token:
        return None

    def q(cur):
        cur.execute("SELECT person FROM ics_tokens WHERE token=%s", (token,))
        return cur.fetchone()
    row = _run(q)
    return row[0] if row else None


# ── discussion notes ─────────────────────────────────────────────────
def add_note(person, text):
    text = (text or "").strip()[:NOTE_MAX_LEN]
    if person not in VALID_PERSONS or not text:
        return
    _run(lambda cur: cur.execute("INSERT INTO notes (person, text) VALUES (%s, %s)", (person, text)))


def get_notes(person):
    if person not in VALID_PERSONS:
        return []

    def q(cur):
        cur.execute("SELECT id, text, created_at FROM notes WHERE person=%s ORDER BY id ASC", (person,))
        return cur.fetchall()
    return [{"id": i, "text": t, "created_at": c.isoformat() if c else None} for i, t, c in _run(q)]


def count_notes(person):
    if person not in VALID_PERSONS:
        return 0

    def q(cur):
        cur.execute("SELECT COUNT(*) FROM notes WHERE person=%s", (person,))
        return cur.fetchone()
    row = _run(q)
    return row[0] if row else 0


def delete_note(person, note_id):
    if person not in VALID_PERSONS:
        return
    _run(lambda cur: cur.execute("DELETE FROM notes WHERE id=%s AND person=%s", (note_id, person)))
