"""Postgres (Neon) implementation — used when DATABASE_URL is set.

Uses a fresh connection per call, same pattern as the SQLite backend. Neon's
pooled connection string (the "-pooler" host) is meant for exactly this kind
of short-lived-connection workload, so use that one for DATABASE_URL.
"""
import secrets

import psycopg2

from .constants import DATE_RE, KEYS, META_KEYS, VALID_PERSONS, VALID_STATUSES

_dsn = None


def init_db(database_url):
    global _dsn
    _dsn = database_url
    con = _connect()
    cur = con.cursor()
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
    con.commit()
    cur.close()
    con.close()


def _connect():
    return psycopg2.connect(_dsn)


# ── counters ──────────────────────────────────────────────────────────
def get_counters():
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT id, val FROM counters")
    rows = dict(cur.fetchall())
    cur.close()
    con.close()
    return {k: rows.get(k, 0) for k in KEYS}


def adjust_counter(key, delta):
    if key not in KEYS or not delta:
        return
    con = _connect()
    cur = con.cursor()
    cur.execute("UPDATE counters SET val = GREATEST(0, val + %s) WHERE id = %s", (int(delta), key))
    con.commit()
    cur.close()
    con.close()


def adjust_running(delta):
    if not delta:
        return
    con = _connect()
    cur = con.cursor()
    cur.execute(
        "UPDATE meta SET value = GREATEST(0, value::int + %s)::text WHERE key = 'jours_sans_course'",
        (int(delta),),
    )
    con.commit()
    cur.close()
    con.close()


# ── streaks (server-side, so both people see the same running streak) ──
def get_streaks():
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT person, count, type FROM streaks")
    rows = cur.fetchall()
    cur.close()
    con.close()
    result = {p: {"count": 0, "type": None} for p in VALID_PERSONS}
    for person, count, ttype in rows:
        if person in result:
            result[person] = {"count": count, "type": ttype or None}
    return result


def bump_streak(person, ttype, delta):
    if person not in VALID_PERSONS or ttype not in ("g", "b") or not delta:
        return
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT count, type FROM streaks WHERE person=%s", (person,))
    row = cur.fetchone()
    count, cur_type = row if row else (0, "")
    if delta > 0:
        count = count + delta if cur_type == ttype else delta
        cur_type = ttype
    elif cur_type == ttype:
        # a correction on the same type undoes the tail of the current run;
        # a correction on the other type is further back and doesn't touch it
        count = max(0, count + delta)
        if count == 0:
            cur_type = ""
    cur.execute(
        "INSERT INTO streaks (person, count, type) VALUES (%s, %s, %s) "
        "ON CONFLICT (person) DO UPDATE SET count=EXCLUDED.count, type=EXCLUDED.type",
        (person, count, cur_type),
    )
    con.commit()
    cur.close()
    con.close()


# ── meta ──────────────────────────────────────────────────────────────
def get_meta(keys):
    if not keys:
        return {}
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT key, value FROM meta WHERE key = ANY(%s)", (list(keys),))
    rows = dict(cur.fetchall())
    cur.close()
    con.close()
    return {k: rows.get(k, "") for k in keys}


def set_meta(data):
    con = _connect()
    cur = con.cursor()
    for k in META_KEYS:
        if k in data:
            value = data[k]
            value = "" if value is None else str(value)
            cur.execute(
                "INSERT INTO meta (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (k, value),
            )
    con.commit()
    cur.close()
    con.close()


# ── availability ──────────────────────────────────────────────────────
def get_availability():
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT person, date, status FROM availability")
    rows = cur.fetchall()
    cur.close()
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
    cur = con.cursor()
    if status in VALID_STATUSES:
        cur.execute(
            "INSERT INTO availability (person, date, status) VALUES (%s, %s, %s) "
            "ON CONFLICT (person, date) DO UPDATE SET status = EXCLUDED.status",
            (person, date, status),
        )
    else:
        cur.execute("DELETE FROM availability WHERE person=%s AND date=%s", (person, date))
    con.commit()
    cur.close()
    con.close()


# ── push subscriptions ───────────────────────────────────────────────
def add_subscription(person, endpoint, p256dh, auth):
    if person not in VALID_PERSONS or not endpoint:
        return
    con = _connect()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO push_subscriptions (endpoint, person, p256dh, auth) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (endpoint) DO UPDATE SET person=EXCLUDED.person, p256dh=EXCLUDED.p256dh, auth=EXCLUDED.auth",
        (endpoint, person, p256dh, auth),
    )
    con.commit()
    cur.close()
    con.close()


def remove_subscription(endpoint):
    con = _connect()
    cur = con.cursor()
    cur.execute("DELETE FROM push_subscriptions WHERE endpoint=%s", (endpoint,))
    con.commit()
    cur.close()
    con.close()


def get_subscriptions(person):
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE person=%s", (person,))
    rows = cur.fetchall()
    cur.close()
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
    cur = con.cursor()
    cur.execute("SELECT token FROM ics_tokens WHERE person=%s", (person,))
    row = cur.fetchone()
    cur.close()
    con.close()
    return row[0] if row else None


def find_person_by_ics_token(token):
    if not token:
        return None
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT person FROM ics_tokens WHERE token=%s", (token,))
    row = cur.fetchone()
    cur.close()
    con.close()
    return row[0] if row else None
