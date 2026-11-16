// Connexion de Bonne journée : un mot de passe par personne (Zoé, Noé).
//
// - Mots de passe : PBKDF2-SHA256, 100 000 tours (le maximum que WebCrypto
//   accepte chez Cloudflare), sel aléatoire, comparaison à temps constant.
//   Jamais en clair, ni en base ni dans Git.
// - Session : cookie HttpOnly signé (HMAC-SHA256, secret SESSION_SECRET) qui
//   porte la personne, la version de son mot de passe et l'obligation de le
//   changer. Changer de mot de passe augmente la version : les sessions
//   ouvertes avant (autre téléphone) ne valent plus rien.
// - Mot de passe par défaut : posé en base par outils/mot_de_passe_defaut.py,
//   avec must_change. Tant qu'il n'est pas remplacé, la session ne donne accès
//   qu'au changement de mot de passe.
import { PERSONS } from './db.js';

export const COOKIE = 'bj_session';
const ITERATIONS = 100000;
const SESSION_DAYS = 365;
const MAX_FAILS = 10;          // essais ratés par personne...
const FAIL_WINDOW_MIN = 15;    // ...sur cette fenêtre
export const MIN_LEN = 8;

const enc = new TextEncoder();
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
const unhex = s => Uint8Array.from(s.match(/../g).map(h => parseInt(h, 16)));

export async function hashPassword(password, saltHex, iterations = ITERATIONS) {
  const key = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: unhex(saltHex), iterations }, key, 256);
  return hex(bits);
}

function sameText(a, b) {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

async function hmac(secret, data) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', key, enc.encode(data)));
}

// Jeton : personne.version.mustChange.expiration.signature
export async function makeSession(env, person, version, mustChange) {
  const exp = Math.floor(Date.now() / 1000) + SESSION_DAYS * 86400;
  const body = `${person}.${version}.${mustChange ? 1 : 0}.${exp}`;
  return `${body}.${await hmac(env.SESSION_SECRET, body)}`;
}

export function sessionCookie(request, token) {
  const secure = new URL(request.url).protocol === 'https:' ? '; Secure' : '';
  const age = token ? SESSION_DAYS * 86400 : 0;
  return `${COOKIE}=${token || ''}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${age}${secure}`;
}

function readCookie(request) {
  const m = (request.headers.get('Cookie') || '').match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`));
  return m ? m[1] : null;
}

// Rend { person, mustChange } si le cookie est valide et que la version du
// mot de passe n'a pas changé depuis ; null sinon.
export async function currentSession(env, sql, request) {
  const token = readCookie(request);
  if (!token || !env.SESSION_SECRET) return null;
  const parts = token.split('.');
  if (parts.length !== 5) return null;
  const [person, version, mc, exp, sig] = parts;
  const expected = await hmac(env.SESSION_SECRET, parts.slice(0, 4).join('.'));
  if (!sameText(sig, expected) || !PERSONS.includes(person) || Number(exp) < Date.now() / 1000) return null;
  const [row] = await sql`SELECT version, must_change FROM passwords WHERE person = ${person}`;
  if (!row || String(row.version) !== version) return null;
  return { person, mustChange: mc === '1' || row.must_change };
}

// Vérifie un mot de passe. Rend { ok, row } ou { blocked } après trop d'essais.
export async function checkPassword(sql, person, password) {
  if (!PERSONS.includes(person) || typeof password !== 'string' || !password) return { ok: false };
  const [{ n }] = await sql`SELECT COUNT(*)::int AS n FROM login_fails
                           WHERE person = ${person} AND at > now() - make_interval(mins => ${FAIL_WINDOW_MIN})`;
  if (n >= MAX_FAILS) return { ok: false, blocked: true };
  const [row] = await sql`SELECT hash, salt, iterations, must_change, version FROM passwords WHERE person = ${person}`;
  const ok = !!row && sameText(await hashPassword(password, row.salt, row.iterations), row.hash);
  if (!ok) await sql`INSERT INTO login_fails (person) VALUES (${person})`;
  else await sql`DELETE FROM login_fails WHERE person = ${person}`;
  return { ok, row };
}

export async function setPassword(sql, person, password) {
  const salt = hex(crypto.getRandomValues(new Uint8Array(16)));
  const hash = await hashPassword(password, salt);
  const [row] = await sql`UPDATE passwords SET hash = ${hash}, salt = ${salt}, iterations = ${ITERATIONS},
                            must_change = false, version = version + 1, updated_at = now()
                          WHERE person = ${person} RETURNING version`;
  return row.version;
}
