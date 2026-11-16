// Flux .ics d'abonnement (Google Agenda, Apple Calendrier) : /calendar/<jeton>.ics
import * as D from '../_lib/db.js';
import { buildIcs } from '../_lib/ics.js';

export async function onRequestGet(ctx) {
  const m = new URL(ctx.request.url).pathname.match(/^\/calendar\/([^/]+)\.ics$/);
  if (!m) return new Response('Not Found', { status: 404 });
  const sql = D.db(ctx.env);
  const person = await D.personForIcsToken(sql, m[1]);
  if (!person) return new Response('Not Found', { status: 404 });
  const [avail, events] = await Promise.all([D.getAvailability(sql), D.getEvents(sql)]);
  // Ce qu'elle a écrit, et ce à quoi l'autre l'a invitée.
  const siens = events.filter(e => e.author === person || e.invited);
  const body = buildIcs(person, Object.entries(avail[person] || {}), siens);
  return new Response(body, {
    headers: { 'Content-Type': 'text/calendar; charset=utf-8', 'Cache-Control': 'no-cache' },
  });
}
