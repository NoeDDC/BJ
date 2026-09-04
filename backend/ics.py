"""Builds a minimal RFC 5545 iCalendar feed from a person's availability."""
from datetime import datetime, timedelta

PERSON_NAMES = {"z": "Zoé", "n": "Noé"}

# statuses that show up in the feed, and how they read in a calendar app
SUMMARIES = {
    "free": "{name} disponible",
    "evening": "{name} dispo après une activité le soir (nuit ok)",
}


def _next_day(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    return d.strftime("%Y%m%d")


def _now_stamp():
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def build_ics(person, days):
    """days: iterable of (date 'YYYY-MM-DD', status). Statuses without a
    summary (unset, legacy 'busy') are skipped."""
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
    for date, status in sorted(days):
        summary = SUMMARIES.get(status)
        if not summary:
            continue
        start = date.replace("-", "")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{person}-{start}@bonnejournee.app",
            f"DTSTAMP:{_now_stamp()}",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{_next_day(date)}",
            f"SUMMARY:{summary.format(name=name)}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
