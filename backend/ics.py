"""Builds a minimal RFC 5545 iCalendar feed from a list of "free" dates."""
from datetime import datetime, timedelta

PERSON_NAMES = {"z": "Zoé", "n": "Noé"}


def _next_day(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    return d.strftime("%Y%m%d")


def _now_stamp():
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def build_ics(person, dates):
    name = PERSON_NAMES.get(person, person)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Bonne journee//Disponibilites//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Dispos de {name}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for date in sorted(dates):
        start = date.replace("-", "")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{person}-{start}@bonnejournee.app",
            f"DTSTAMP:{_now_stamp()}",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{_next_day(date)}",
            f"SUMMARY:{name} disponible",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
