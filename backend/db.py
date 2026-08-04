"""Data access dispatcher: Postgres (Neon) when DATABASE_URL is set,
otherwise SQLite for local dev. Same public function names either way, so
the rest of the app (handlers.py) doesn't need to care which one is active.

The choice is made inside init_db(), not at import time, so it still works
correctly even if DATABASE_URL is loaded from a .env file after this module
has already been imported.
"""
import os

from .constants import DATE_RE, KEYS, META_KEYS, VALID_PERSONS, VALID_STATUSES  # noqa: F401 (re-exported)

_impl = None
BACKEND = None


def init_db(sqlite_path):
    global _impl, BACKEND
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        from . import db_postgres
        _impl = db_postgres
        BACKEND = "postgres"
        _impl.init_db(database_url)
    else:
        from . import db_sqlite
        _impl = db_sqlite
        BACKEND = "sqlite"
        _impl.init_db(sqlite_path)


def get_counters():
    return _impl.get_counters()


def adjust_counter(key, delta):
    return _impl.adjust_counter(key, delta)


def adjust_running(delta):
    return _impl.adjust_running(delta)


def get_meta(keys):
    return _impl.get_meta(keys)


def set_meta(data):
    return _impl.set_meta(data)


def get_availability():
    return _impl.get_availability()


def set_availability(person, date, status):
    return _impl.set_availability(person, date, status)


def add_subscription(person, endpoint, p256dh, auth):
    return _impl.add_subscription(person, endpoint, p256dh, auth)


def remove_subscription(endpoint):
    return _impl.remove_subscription(endpoint)


def get_subscriptions(person):
    return _impl.get_subscriptions(person)


def get_ics_token(person):
    return _impl.get_ics_token(person)


def find_person_by_ics_token(token):
    return _impl.find_person_by_ics_token(token)
