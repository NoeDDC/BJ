// Toute l'API de Bonne journée (/api/...), en une fonction Cloudflare.
// Mêmes routes et mêmes réponses que l'ancien serveur Python
// (backend/handlers.py), plus les événements écrits du calendrier.
import * as D from '../_lib/db.js';
import { sendPush } from '../_lib/push.js';
import * as A from '../_lib/auth.js';

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

// ── connexion ──
async function auth(ctx, sql, path, url) {
  const { request } = ctx;
  if (path === '/api/auth/me' && request.method === 'GET') {
    const s = ctx.data.session;
    return json({ person: s.person, mustChange: s.mustChange });
  }
  if (request.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
  const body = await readBody(request);
  if (path === '/api/auth/login') {
    const r = await A.checkPassword(sql, body.person, body.password);
    if (r.blocked) return json({ error: 'Trop d\'essais : réessaie dans un quart d\'heure.' }, 429);
    if (!r.ok) return json({ error: 'Mot de passe incorrect.' }, 401);
    const token = await A.makeSession(ctx.env, body.person, r.row.version, r.row.must_change);
    return new Response(JSON.stringify({ person: body.person, mustChange: r.row.must_change }), {
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Set-Cookie': A.sessionCookie(request, token) },
    });
  }
  if (path === '/api/auth/logout') {
    return new Response(JSON.stringify({ ok: true }), {
      headers: { 'Content-Type': 'application/json', 'Set-Cookie': A.sessionCookie(request, null) },
    });
  }
  if (path === '/api/auth/change') {
    const s = ctx.data.session;
    const pw = typeof body.password === 'string' ? body.password : '';
    if (pw.length < A.MIN_LEN) return json({ error: `Au moins ${A.MIN_LEN} caractères.` }, 400);
    // Le même que l'actuel (donc, au premier passage, le mot de passe par défaut) : refusé.
    const [row] = await sql`SELECT hash, salt, iterations FROM passwords WHERE person = ${s.person}`;
    if (row && (await A.hashPassword(pw, row.salt, row.iterations)) === row.hash) {
      return json({ error: 'Choisis un mot de passe différent de l\'actuel.' }, 400);
    }
    const version = await A.setPassword(sql, s.person, pw);
    const token = await A.makeSession(ctx.env, s.person, version, false);
    return new Response(JSON.stringify({ person: s.person, mustChange: false }), {
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Set-Cookie': A.sessionCookie(request, token) },
    });
  }
  return new Response('Not Found', { status: 404 });
}

export async function onRequest(ctx) {
  const { request } = ctx;
  const url = new URL(request.url);
  const path = url.pathname;
  const sql = D.db(ctx.env);
  if (path.startsWith('/api/auth/')) return auth(ctx, sql, path, url);

  // La personne est celle de la session (functions/_middleware.js), jamais
  // celle que le téléphone annonce : Noé n'écrit pas au nom de Zoé et ne lit
  // pas ses notes « à se dire ».
  const me = ctx.data.session.person;

  if (request.method === 'GET') {
    switch (path) {
      case '/api/counters': return json(await D.getDashboard(sql));
      case '/api/availability': return json(await D.getAvailability(sql));
      case '/api/events': return json(await D.getEvents(sql));
      case '/api/notes': return json(await D.notesPayload(sql, me));
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
  body.person = me;
  const person = me;

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
