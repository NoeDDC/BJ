"""Shared constants used by both the SQLite and Postgres db backends."""
import re

KEYS = ("zg", "zb", "ng", "nb")
META_KEYS = ("ui", "theme_a", "theme_b", "message_zn", "message_nz", "jours_sans_course")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_PERSONS = ("z", "n")
VALID_STATUSES = ("free", "busy")
