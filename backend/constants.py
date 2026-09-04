"""Shared constants used by both the SQLite and Postgres db backends."""
import re

KEYS = ("zg", "zb", "ng", "nb")
META_KEYS = ("theme", "message_zn", "message_nz", "jours_sans_course")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_PERSONS = ("z", "n")
# "free": whole day; "evening": activity in the evening but the night together
# is possible; "busy": legacy value from the old 3-state tap, kept readable.
VALID_STATUSES = ("free", "evening", "busy")
NOTE_MAX_LEN = 200
