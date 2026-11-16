// Accès à la base Neon depuis les fonctions Cloudflare.
//
// Le pilote HTTP de Neon fait UN aller-retour par requête (ou par transaction
// groupée), sans connexion à garder ouverte : c'est ce qui convient à une
// fonction qui naît et meurt à chaque appel. Même schéma et mêmes réponses que
// l'ancien serveur Python (backend/db_postgres.py), pour que l'app n'ait rien
// à changer.
import { neon } from '@neondatabase/serverless';

export const KEYS = ['zg', 'zb', 'ng', 'nb'];
export const META_KEYS = ['theme', 'message_zn', 'message_nz', 'jours_sans_course'];
export const PERSONS = ['z', 'n'];
export const NAMES = { z: 'Zoé', n: 'Noé' };
// "free" : toute la journée ; "evening" : activité le soir mais nuit ensemble
// possible ; "busy" : ancienne valeur, gardée lisible.
export const STATUSES = ['free', 'evening', 'busy'];
export const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
export const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
export const NOTE_MAX_LEN = 200;
export const EVENT_MAX_LEN = 120;
const SHOP_MAX_LEN = 60;
const SHOP_MAX_ADD = 20;
const SHOP_KEEP_HOURS = 24;
const SHOP_SUGGESTIONS = 14;

export function db(env) {
  return neon(env.DATABASE_URL);
}

export const other = p => (p === 'z' ? 'n' : 'z');

// ── journal ───────────────────────────────────────────────────────────
export async function getDashboard(sql) {
  const [counters, meta, streaks] = await sql.transaction([
    sql`SELECT id, val FROM counters`,
    sql`SELECT key, value FROM meta WHERE key = ANY(${META_KEYS})`,
    sql`SELECT person, count, type FROM streaks`,
  ], { readOnly: true });
  const data = {};
  const c = Object.fromEntries(counters.map(r => [r.id, r.val]));
  for (const k of KEYS) data[k] = c[k] ?? 0;
  const m = Object.fromEntries(meta.map(r => [r.key, r.value]));
  for (const k of META_KEYS) data[k] = m[k] ?? '';
  const s = { z: { count: 0, type: null }, n: { count: 0, type: null } };
  for (const r of streaks) if (s[r.person]) s[r.person] = { count: r.count, type: r.type || null };
  data.streaks = s;
  return data;
}

// Un appui sur un compteur du journal : le compteur bouge (jamais sous 0) et
// la série de la personne suit, dans une seule transaction. +N sur le même
// type prolonge la série, +N sur l'autre type en démarre une de N ; -N sur le
// type courant la raccourcit (plus de série à 0) ; -N sur l'autre type est une
// correction plus ancienne et ne la touche pas.
export async function adjustJournee(sql, key, delta) {
  if (!KEYS.includes(key) || !delta) return false;
  const person = key[0], t = key[1];
  await sql.transaction([
    sql`UPDATE counters SET val = GREATEST(0, val + ${delta}) WHERE id = ${key}`,
    sql`UPDATE streaks SET
          count = CASE
                    WHEN ${delta}::int > 0 THEN CASE WHEN type = ${t} THEN count + ${delta}::int ELSE ${delta}::int END
                    WHEN type = ${t} THEN GREATEST(0, count + ${delta}::int)
                    ELSE count
                  END,
          type  = CASE
                    WHEN ${delta}::int > 0 THEN ${t}
                    WHEN type = ${t} AND count + ${delta}::int <= 0 THEN ''
                    ELSE type
                  END
        WHERE person = ${person}`,
  ]);
  return delta > 0;
}

export async function adjustRunning(sql, delta) {
  if (!delta) return;
  await sql`UPDATE meta SET value = GREATEST(0, value::int + ${delta})::text WHERE key = 'jours_sans_course'`;
}

export async function setMeta(sql, data) {
  const items = META_KEYS.filter(k => k in data).map(k => [k, data[k] == null ? '' : String(data[k])]);
  if (!items.length) return;
  await sql.transaction(items.map(([k, v]) =>
    sql`INSERT INTO meta (key, value) VALUES (${k}, ${v}) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`));
}

// ── disponibilités ────────────────────────────────────────────────────
export async function getAvailability(sql) {
  const rows = await sql`SELECT person, date, status FROM availability`;
  const out = { z: {}, n: {} };
  for (const r of rows) if (out[r.person]) out[r.person][r.date] = r.status;
  return out;
}

export async function setAvailability(sql, person, date, status) {
  if (!PERSONS.includes(person) || !DATE_RE.test(date || '')) return;
  if (STATUSES.includes(status)) {
    await sql`INSERT INTO availability (person, date, status) VALUES (${person}, ${date}, ${status})
              ON CONFLICT (person, date) DO UPDATE SET status = EXCLUDED.status`;
  } else {
    await sql`DELETE FROM availability WHERE person = ${person} AND date = ${date}`;
  }
}

// ── événements écrits dans le calendrier ──────────────────────────────
// Chacun peut écrire quelque chose sur un jour (« Resto chez Léa », « Train
// 18 h »), et choisir d'y inviter l'autre ou non. Les deux voient tout : un
// événement sans invitation dit seulement « c'est mon programme ».
function shapeEvent(r) {
  return { id: r.id, author: r.author, date: r.date, time: r.time || null, text: r.text, invited: !!r.invited };
}

export async function getEvents(sql) {
  const rows = await sql`SELECT id, author, date, time, text, invited FROM events ORDER BY date, time NULLS FIRST, id`;
  return rows.map(shapeEvent);
}

export function cleanEvent(body) {
  const text = String(body.text || '').replace(/\s+/g, ' ').trim().slice(0, EVENT_MAX_LEN);
  const date = String(body.date || '');
  const time = body.time ? String(body.time) : null;
  if (!text || !DATE_RE.test(date) || (time && !TIME_RE.test(time))) return null;
  return { text, date, time, invited: !!body.invited };
}

export async function addEvent(sql, author, e) {
  const [r] = await sql`INSERT INTO events (author, date, time, text, invited)
                        VALUES (${author}, ${e.date}, ${e.time}, ${e.text}, ${e.invited})
                        RETURNING id, author, date, time, text, invited`;
  return shapeEvent(r);
}

// Seul l'auteur modifie ou retire ce qu'il a écrit. Rend l'état d'avant
// (null si l'événement n'est pas le sien) : il dit si l'invitation est neuve.
export async function updateEvent(sql, author, id, e) {
  const [avant] = await sql`SELECT invited FROM events WHERE id = ${id} AND author = ${author}`;
  if (!avant) return null;
  await sql`UPDATE events SET date = ${e.date}, time = ${e.time}, text = ${e.text}, invited = ${e.invited}
            WHERE id = ${id} AND author = ${author}`;
  return { wasInvited: !!avant.invited };
}

export async function deleteEvent(sql, author, id) {
  await sql`DELETE FROM events WHERE id = ${id} AND author = ${author}`;
}

// ── notifications ─────────────────────────────────────────────────────
export async function addSubscription(sql, person, endpoint, p256dh, auth) {
  if (!PERSONS.includes(person) || !endpoint || !p256dh || !auth) return;
  await sql`INSERT INTO push_subscriptions (endpoint, person, p256dh, auth) VALUES (${endpoint}, ${person}, ${p256dh}, ${auth})
            ON CONFLICT (endpoint) DO UPDATE SET person = EXCLUDED.person, p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth`;
}

export async function removeSubscription(sql, endpoint) {
  if (!endpoint) return;
  await sql`DELETE FROM push_subscriptions WHERE endpoint = ${endpoint}`;
}

export async function getSubscriptions(sql, person) {
  const rows = await sql`SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE person = ${person}`;
  return rows.map(r => ({ endpoint: r.endpoint, keys: { p256dh: r.p256dh, auth: r.auth } }));
}

// ── liens d'abonnement .ics ───────────────────────────────────────────
export async function getIcsTokens(sql) {
  const rows = await sql`SELECT person, token FROM ics_tokens`;
  return Object.fromEntries(rows.map(r => [r.person, r.token]));
}

export async function personForIcsToken(sql, token) {
  if (!token) return null;
  const [r] = await sql`SELECT person FROM ics_tokens WHERE token = ${token}`;
  return r ? r.person : null;
}

// ── à se dire ─────────────────────────────────────────────────────────
export async function notesPayload(sql, person) {
  const [mine, count] = await sql.transaction([
    sql`SELECT id, text, created_at FROM notes WHERE person = ${person} ORDER BY id ASC`,
    sql`SELECT COUNT(*)::int AS n FROM notes WHERE person = ${other(person)}`,
  ], { readOnly: true });
  return {
    mine: mine.map(r => ({ id: r.id, text: r.text, created_at: r.created_at ? new Date(r.created_at).toISOString() : null })),
    otherCount: count[0] ? count[0].n : 0,
  };
}

export async function addNote(sql, person, text) {
  text = String(text || '').trim().slice(0, NOTE_MAX_LEN);
  if (!text) return;
  await sql`INSERT INTO notes (person, text) VALUES (${person}, ${text})`;
}

export async function deleteNote(sql, person, id) {
  await sql`DELETE FROM notes WHERE id = ${id} AND person = ${person}`;
}

// ── liste de courses ──────────────────────────────────────────────────
// `label` est la forme minuscule qui repère un doublon et regroupe
// l'historique des raccourcis : « Lait » et « lait » ne font qu'un.
export function cleanShoppingTexts(texts) {
  if (typeof texts === 'string') texts = [texts];
  const out = [], seen = new Set();
  for (const raw of Array.isArray(texts) ? texts : []) {
    if (typeof raw !== 'string') continue;
    const text = raw.split(/\s+/).filter(Boolean).join(' ').slice(0, SHOP_MAX_LEN);
    const label = text.toLowerCase();
    if (!text || seen.has(label)) continue;
    seen.add(label);
    out.push([label, text]);
    if (out.length >= SHOP_MAX_ADD) break;
  }
  return out;
}

// La lecture sert aussi de ménage (articles cochés depuis plus de 24 h) :
// c'est la seule chose qui arrive assez souvent, l'app n'a pas de tâche planifiée.
export async function shoppingBoard(sql) {
  const [, items, sugg] = await sql.transaction([
    sql`DELETE FROM shopping WHERE checked_at IS NOT NULL AND checked_at < now() - make_interval(hours => ${SHOP_KEEP_HOURS})`,
    sql`SELECT id, text, added_by, checked_by, checked_at FROM shopping
        ORDER BY (checked_at IS NOT NULL), checked_at DESC NULLS LAST, id`,
    sql`SELECT text FROM shopping_history ORDER BY uses DESC, last_used DESC LIMIT ${SHOP_SUGGESTIONS}`,
  ]);
  return {
    items: items.map(r => ({
      id: r.id, text: r.text, added_by: r.added_by || '',
      checked_by: r.checked_by || null,
      checked_at: r.checked_at ? new Date(r.checked_at).toISOString() : null,
    })),
    suggestions: sugg.map(r => r.text),
  };
}

export async function addShopping(sql, person, texts) {
  const items = cleanShoppingTexts(texts);
  if (!items.length) return;
  const queries = [];
  for (const [label, text] of items) {
    // Déjà sur la liste et pas encore pris : ni doublon, ni +1 à l'historique.
    // L'historique passe d'abord, tant que l'article n'est pas encore inséré.
    queries.push(sql`INSERT INTO shopping_history (label, text, uses, last_used)
                     SELECT ${label}, ${text}, 1, now()
                     WHERE NOT EXISTS (SELECT 1 FROM shopping WHERE checked_at IS NULL AND label = ${label})
                     ON CONFLICT (label) DO UPDATE SET text = EXCLUDED.text, uses = shopping_history.uses + 1, last_used = now()`);
    queries.push(sql`INSERT INTO shopping (text, label, added_by)
                     SELECT ${text}, ${label}, ${person}
                     WHERE NOT EXISTS (SELECT 1 FROM shopping WHERE checked_at IS NULL AND label = ${label})`);
  }
  await sql.transaction(queries);
}

export async function checkShopping(sql, person, id, checked) {
  if (checked) {
    // ... AND checked_at IS NULL : recocher un article déjà pris ne relance pas ses 24 h
    await sql`UPDATE shopping SET checked_by = ${person}, checked_at = now() WHERE id = ${id} AND checked_at IS NULL`;
  } else {
    await sql`UPDATE shopping SET checked_by = NULL, checked_at = NULL WHERE id = ${id}`;
  }
}

export async function deleteShopping(sql, id) {
  await sql`DELETE FROM shopping WHERE id = ${id}`;
}
