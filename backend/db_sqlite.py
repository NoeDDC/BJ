"""SQLite implementation — used for local dev when DATABASE_URL isn't set."""
import os
import secrets
import sqlite3

from .constants import DATE_RE, KEYS, META_KEYS, NOTE_MAX_LEN, VALID_PERSONS, VALID_STATUSES

DB_PATH = None  # set once by init_db()


def init_db(db_path):
    global DB_PATH
    DB_PATH = db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = _connect()
    con.execute("CREATE TABLE IF NOT EXISTS counters (id TEXT PRIMARY KEY, val INTEGER DEFAULT 0)")
    con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT DEFAULT '')")
    con.execute("CREATE TABLE IF NOT EXISTS availability (person TEXT NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY (person, date))")
    con.execute("""CREATE TABLE IF NOT EXISTS push_subscriptions (
        endpoint TEXT PRIMARY KEY,
        person TEXT NOT NULL,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL
    )""")
    con.execute("CREATE TABLE IF NOT EXISTS ics_tokens (person TEXT PRIMARY KEY, token TEXT NOT NULL UNIQUE)")
    con.execute("CREATE TABLE IF NOT EXISTS streaks (person TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0, type TEXT NOT NULL DEFAULT '')")
    con.execute("""CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    for k in KEYS:
        con.execute("INSERT OR IGNORE INTO counters VALUES (?, 0)", (k,))
    con.execute("INSERT OR IGNORE INTO meta VALUES (?, ?)", ("theme", "theme-1"))
    con.execute("INSERT OR IGNORE INTO meta VALUES (?, ?)", ("message_zn", ""))
    con.execute("INSERT OR IGNORE INTO meta VALUES (?, ?)", ("message_nz", ""))
    con.execute("INSERT OR IGNORE INTO meta VALUES (?, ?)", ("jours_sans_course", "0"))
    for p in VALID_PERSONS:
        con.execute("INSERT OR IGNORE INTO ics_tokens (person, token) VALUES (?, ?)", (p, secrets.token_urlsafe(24)))
        con.execute("INSERT OR IGNORE INTO streaks (person, count, type) VALUES (?, 0, '')", (p,))
    con.commit()
    con.close()


def _connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA busy_timeout = 3000")
    return con


# ── counters / journal ────────────────────────────────────────────────
def get_counters():
    con = _connect()
    rows = dict(con.execute("SELECT id, val FROM counters").fetchall())
    con.close()
    return {k: rows.get(k, 0) for k in KEYS}


def _shape_streaks(rows):
    result = {p: {"count": 0, "type": None} for p in VALID_PERSONS}
    for person, count, ttype in rows:
        if person in result:
            result[person] = {"count": count, "type": ttype or None}
    return result


def get_dashboard():
    """Everything the journal screen needs — counters, meta and streaks."""
    con = _connect()
    counters = dict(con.execute("SELECT id, val FROM counters").fetchall())
    meta = dict(con.execute(
        "SELECT key, value FROM meta WHERE key IN ({})".format(",".join("?" * len(META_KEYS))),
        META_KEYS,
    ).fetchall())
    streaks = con.execute("SELECT person, count, type FROM streaks").fetchall()
    con.close()
    data = {k: counters.get(k, 0) for k in KEYS}
    data.update({k: meta.get(k, "") for k in META_KEYS})
    data["streaks"] = _shape_streaks(streaks)
    return data


# Same streak rule as the Postgres backend, see db_postgres._STREAK_SQL.
_STREAK_SQL = """
    UPDATE streaks SET
      count = CASE
                WHEN :d > 0 THEN CASE WHEN type = :t THEN count + :d ELSE :d END
                WHEN type = :t THEN MAX(0, count + :d)
                ELSE count
              END,
      type  = CASE
                WHEN :d > 0 THEN :t
                WHEN type = :t AND count + :d <= 0 THEN ''
                ELSE type
              END
    WHERE person = :p
"""


def adjust_journee(key, delta):
    """One tap on a journal counter: move the counter (never below 0) and
    update that person's streak, in one transaction. Returns True if the
    counter went up."""
    delta = int(delta)
    if key not in KEYS or not delta:
        return False
    person, ttype = key[0], key[1]
    con = _connect()
    con.execute("UPDATE counters SET val = MAX(0, val + ?) WHERE id = ?", (delta, key))
    con.execute(_STREAK_SQL, {"d": delta, "t": ttype, "p": person})
    con.commit()
    con.close()
    return delta > 0


def adjust_running(delta):
    if not delta:
        return
    con = _connect()
    con.execute(
        "UPDATE meta SET value = CAST(MAX(0, CAST(value AS INTEGER) + ?) AS TEXT) WHERE key = 'jours_sans_course'",
        (int(delta),),
    )
    con.commit()
    con.close()


# ── meta ──────────────────────────────────────────────────────────────
def get_meta(keys):
    if not keys:
        return {}
    con = _connect()
    rows = dict(con.execute(
        "SELECT key, value FROM meta WHERE key IN ({})".format(",".join("?" * len(keys))),
        keys
    ).fetchall())
    con.close()
    return {k: rows.get(k, "") for k in keys}


def set_meta(data):
    con = _connect()
    for k in META_KEYS:
        if k in data:
            value = data[k]
            con.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, "" if value is None else str(value)))
    con.commit()
    con.close()


# ── availability ──────────────────────────────────────────────────────
def get_availability():
    con = _connect()
    rows = con.execute("SELECT person, date, status FROM availability").fetchall()
    con.close()
    result = {"z": {}, "n": {}}
    for person, date, status in rows:
        if person in result:
            result[person][date] = status
    return result


def set_availability(person, date, status):
    if person not in VALID_PERSONS or not DATE_RE.match(date or ""):
        return
    con = _connect()
    if status in VALID_STATUSES:
        con.execute("INSERT OR REPLACE INTO availability VALUES (?, ?, ?)", (person, date, status))
    else:
        con.execute("DELETE FROM availability WHERE person=? AND date=?", (person, date))
    con.commit()
    con.close()


# ── push subscriptions ───────────────────────────────────────────────
def add_subscription(person, endpoint, p256dh, auth):
    if person not in VALID_PERSONS or not endpoint:
        return
    con = _connect()
    con.execute(
        "INSERT OR REPLACE INTO push_subscriptions VALUES (?, ?, ?, ?)",
        (endpoint, person, p256dh, auth),
    )
    con.commit()
    con.close()


def remove_subscription(endpoint):
    con = _connect()
    con.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))
    con.commit()
    con.close()


def get_subscriptions(person):
    con = _connect()
    rows = con.execute(
        "SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE person=?", (person,)
    ).fetchall()
    con.close()
    return [
        {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
        for endpoint, p256dh, auth in rows
    ]


# ── ics subscription tokens ────────────────────────────────────────────
def get_ics_token(person):
    if person not in VALID_PERSONS:
        return None
    con = _connect()
    row = con.execute("SELECT token FROM ics_tokens WHERE person=?", (person,)).fetchone()
    con.close()
    return row[0] if row else None


def find_person_by_ics_token(token):
    if not token:
        return None
    con = _connect()
    row = con.execute("SELECT person FROM ics_tokens WHERE token=?", (token,)).fetchone()
    con.close()
    return row[0] if row else None


# ── discussion notes ─────────────────────────────────────────────────
def add_note(person, text):
    text = (text or "").strip()[:NOTE_MAX_LEN]
    if person not in VALID_PERSONS or not text:
        return
    con = _connect()
    con.execute(
        "INSERT INTO notes (person, text, created_at) VALUES (?, ?, datetime('now'))",
        (person, text),
    )
    con.commit()
    con.close()


def get_notes(person):
    if person not in VALID_PERSONS:
        return []
    con = _connect()
    rows = con.execute(
        "SELECT id, text, created_at FROM notes WHERE person=? ORDER BY id ASC", (person,)
    ).fetchall()
    con.close()
    return [{"id": i, "text": t, "created_at": c} for i, t, c in rows]


def count_notes(person):
    if person not in VALID_PERSONS:
        return 0
    con = _connect()
    row = con.execute("SELECT COUNT(*) FROM notes WHERE person=?", (person,)).fetchone()
    con.close()
    return row[0] if row else 0


def delete_note(person, note_id):
    if person not in VALID_PERSONS:
        return
    con = _connect()
    con.execute("DELETE FROM notes WHERE id=? AND person=?", (note_id, person))
    con.commit()
    con.close()


# ── raw export (used by the Neon migration script) ─────────────────────
def dump_all():
    con = _connect()
    counters = con.execute("SELECT id, val FROM counters").fetchall()
    meta = con.execute("SELECT key, value FROM meta").fetchall()
    availability = con.execute("SELECT person, date, status FROM availability").fetchall()
    subs = con.execute("SELECT endpoint, person, p256dh, auth FROM push_subscriptions").fetchall()
    con.close()
    return {"counters": counters, "meta": meta, "availability": availability, "push_subscriptions": subs}
