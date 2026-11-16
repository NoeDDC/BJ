// Toute l'API de Bonne journée (/api/...), en une fonction Cloudflare.
// Mêmes routes et mêmes réponses que l'ancien serveur Python
// (backend/handlers.py), plus les événements écrits du calendrier.
import * as D from '../_lib/db.js';
import { sendPush } from '../_lib/push.js';

const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
});
const bad = () => new Response('Bad Request', { status: 400 });
const asInt = v => (v !== null && v !== '' && Number.isInteger(Number(v)) ? Number(v) : null);

// Prévient l'autre personne sur tous ses téléphones abonnés, sans retarder
// la réponse (waitUntil), et oublie les abonnements que le téléphone a quittés.
function notify(ctx, sql, to, message) {
  ctx.waitUntil((async () => {
    if (!ctx.env.VAPID_PRIVATE) return;
    for (const sub of await D.getSubscriptions(sql, to)) {
      const r = await sendPush(ctx.env, sub, message);
      if (r.expired) await D.removeSubscription(sql, sub.endpoint);
    }
  })());
}

function joliJour(date) {
  const d = new Date(date + 'T12:00:00Z');
  return d.toLocaleDateString('fr-BE', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });
}

const heure = t => (t ? ' à ' + t.replace(':', ' h ') : '');

async function readBody(request) {
  try {
    const b = await request.json();
    return b && typeof b === 'object' && !Array.isArray(b) ? b : {};
  } catch { return {}; }
}

export async function onRequest(ctx) {
  const { request } = ctx;
  const url = new URL(request.url);
  const path = url.pathname;
  const sql = D.db(ctx.env);

  if (request.method === 'GET') {
    switch (path) {
      case '/api/counters': return json(await D.getDashboard(sql));
      case '/api/availability': return json(await D.getAvailability(sql));
      case '/api/events': return json(await D.getEvents(sql));
      case '/api/notes': {
        const person = url.searchParams.get('person');
        if (!D.PERSONS.includes(person)) return bad();
        return json(await D.notesPayload(sql, person));
      }
      case '/api/shopping': return json(await D.shoppingBoard(sql));
      case '/api/push/public-key': return json({ publicKey: ctx.env.VAPID_PUBLIC || null });
      case '/api/calendar-links': {
        const tokens = await D.getIcsTokens(sql);
        return json(Object.fromEntries(D.PERSONS.map(p => [p, `${url.origin}/calendar/${tokens[p]}.ics`])));
      }
    }
    return new Response('Not Found', { status: 404 });
  }

  if (request.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
  const body = await readBody(request);
  const person = body.person;

  switch (path) {
    case '/api/counters': {
      // Le thème seulement : les compteurs ne s'écrivent jamais en valeur
      // absolue (voir /api/counters/adjust), sinon un téléphone qui renvoie
      // son état local écraserait les appuis faits ailleurs entre-temps.
      delete body.jours_sans_course;
      await D.setMeta(sql, body);
      return json(await D.getDashboard(sql));
    }
    case '/api/counters/adjust': {
      const key = body.key;
      const delta = parseInt(body.delta, 10) || 0;
      if (key === 'jours_sans_course') await D.adjustRunning(sql, delta);
      else if (D.KEYS.includes(key) && delta) {
        if (await D.adjustJournee(sql, key, delta)) {
          const who = key[0], t = key[1];
          notify(ctx, sql, D.other(who), {
            title: 'Bonne journée',
            body: `${D.NAMES[who]} a ajouté une ${t === 'g' ? 'bonne journée ☀︎' : 'mauvaise journée ☁︎'}`,
            tag: `journee-${who}${t}`,
          });
        }
      }
      return json(await D.getDashboard(sql));
    }
    case '/api/availability':
      await D.setAvailability(sql, person, body.date, body.status);
      return json(await D.getAvailability(sql));

    case '/api/events': {
      if (!D.PERSONS.includes(person)) return bad();
      const e = D.cleanEvent(body);
      if (!e) return bad();
      const id = asInt(body.id);
      let invitationNeuve = false;
      if (id === null) {
        await D.addEvent(sql, person, e);
        invitationNeuve = e.invited;
      } else {
        const avant = await D.updateEvent(sql, person, id, e);
        invitationNeuve = !!avant && e.invited && !avant.wasInvited;
      }
      if (invitationNeuve) notify(ctx, sql, D.other(person), {
        title: 'Bonne journée',
        body: `${D.NAMES[person]} t'invite ${joliJour(e.date)}${heure(e.time)} : ${e.text}`,
        tag: 'evenement',
      });
      return json(await D.getEvents(sql));
    }
    case '/api/events/delete': {
      const id = asInt(body.id);
      if (!D.PERSONS.includes(person) || id === null) return bad();
      await D.deleteEvent(sql, person, id);
      return json(await D.getEvents(sql));
    }

    case '/api/notes':
      if (!D.PERSONS.includes(person)) return bad();
      await D.addNote(sql, person, body.text);
      return json(await D.notesPayload(sql, person));
    case '/api/notes/delete': {
      if (!D.PERSONS.includes(person)) return bad();
      const id = asInt(body.id);
      if (id !== null) await D.deleteNote(sql, person, id);
      return json(await D.notesPayload(sql, person));
    }

    case '/api/shopping':
      if (!D.PERSONS.includes(person)) return bad();
      await D.addShopping(sql, person, body.texts || body.text);
      return json(await D.shoppingBoard(sql));
    case '/api/shopping/check': {
      if (!D.PERSONS.includes(person)) return bad();
      const id = asInt(body.id);
      if (id !== null) await D.checkShopping(sql, person, id, !!body.checked);
      return json(await D.shoppingBoard(sql));
    }
    case '/api/shopping/delete': {
      const id = asInt(body.id);
      if (id !== null) await D.deleteShopping(sql, id);
      return json(await D.shoppingBoard(sql));
    }

    case '/api/push/subscribe': {
      const sub = body.subscription || {};
      const keys = sub.keys || {};
      await D.addSubscription(sql, person, sub.endpoint, keys.p256dh, keys.auth);
      return json({ ok: true });
    }
    case '/api/push/unsubscribe':
      await D.removeSubscription(sql, body.endpoint);
      return json({ ok: true });
  }
  return new Response('Not Found', { status: 404 });
}
