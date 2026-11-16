// Flux iCalendar (RFC 5545) d'une personne : ses dispos, ce qu'elle a écrit,
// et ce à quoi l'autre l'a invitée. Même forme que l'ancien backend/ics.py,
// mêmes identifiants (UID) pour les dispos : un agenda déjà abonné ne voit pas
// ses jours dupliqués.
import { NAMES } from './db.js';

const SUMMARIES = {
  free: '{name} disponible',
  evening: '{name} dispo après une activité le soir (nuit ok)',
};

const compact = d => d.replace(/-/g, '');

function nextDay(date) {
  const d = new Date(date + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10).replace(/-/g, '');
}

// Texte iCalendar : \ ; , et retours à la ligne s'échappent.
const esc = s => String(s).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');

export function buildIcs(person, days, events) {
  const name = NAMES[person] || person;
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+/, '');
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Bonne journee//Disponibilites//FR',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    `X-WR-CALNAME:Dispos de ${name}`,
    'X-WR-TIMEZONE:Europe/Brussels',
    'REFRESH-INTERVAL;VALUE=DURATION:PT12H',
    'X-PUBLISHED-TTL:PT12H',
  ];
  for (const [date, status] of [...days].sort()) {
    const summary = SUMMARIES[status];
    if (!summary) continue;
    lines.push(
      'BEGIN:VEVENT',
      `UID:${person}-${compact(date)}@bonnejournee.app`,
      `DTSTAMP:${stamp}`,
      `DTSTART;VALUE=DATE:${compact(date)}`,
      `DTEND;VALUE=DATE:${nextDay(date)}`,
      `SUMMARY:${summary.replace('{name}', name)}`,
      'TRANSP:TRANSPARENT',
      'END:VEVENT',
    );
  }
  for (const e of events) {
    const avec = e.invited ? ` (${NAMES[e.author]} + ${NAMES[e.author === 'z' ? 'n' : 'z']})` : '';
    const start = e.time
      ? [`DTSTART;TZID=Europe/Brussels:${compact(e.date)}T${e.time.replace(':', '')}00`, 'DURATION:PT1H']
      : [`DTSTART;VALUE=DATE:${compact(e.date)}`, `DTEND;VALUE=DATE:${nextDay(e.date)}`];
    lines.push(
      'BEGIN:VEVENT',
      `UID:evenement-${e.id}@bonnejournee.app`,
      `DTSTAMP:${stamp}`,
      ...start,
      `SUMMARY:${esc(e.text + avec)}`,
      'END:VEVENT',
    );
  }
  lines.push('END:VCALENDAR');
  return lines.join('\r\n') + '\r\n';
}
