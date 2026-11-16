// Garde de tout le site : sans session, rien d'autre que la page de connexion.
// S'exécute avant les fichiers de public/ comme avant l'API.
import { db } from './_lib/db.js';
import { currentSession } from './_lib/auth.js';

// Ouverts sans connexion : la page de connexion, ses routes, ce qu'il faut à
// un téléphone pour installer l'app (manifeste, icônes), et les flux .ics,
// qu'un agenda lit sans cookie et que protège déjà leur jeton secret.
const PUBLICS = ['/login', '/login.html', '/api/auth/login', '/api/auth/logout', '/manifest.webmanifest', '/favicon.ico'];
const PREFIXES_PUBLICS = ['/icons/', '/calendar/'];
// Avec le mot de passe par défaut encore en place : seulement de quoi le changer.
const AVANT_CHANGEMENT = ['/login', '/login.html', '/api/auth/change', '/api/auth/me', '/api/auth/logout', '/api/auth/login'];

export async function onRequest(ctx) {
  const url = new URL(ctx.request.url);
  const path = url.pathname;
  if (PUBLICS.includes(path) || PREFIXES_PUBLICS.some(p => path.startsWith(p))) return ctx.next();

  const session = await currentSession(ctx.env, db(ctx.env), ctx.request);
  const refuse = raison => path.startsWith('/api/')
    ? new Response(JSON.stringify({ error: raison }), { status: 401, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } })
    : Response.redirect(`${url.origin}/login${raison === 'changer' ? '?changer' : ''}`, 302);

  if (!session) return refuse('connexion');
  if (session.mustChange && !AVANT_CHANGEMENT.includes(path)) return refuse('changer');
  ctx.data.session = session;
  const res = await ctx.next();
  // Rien de ce qui suit une connexion ne doit rester dans un cache partagé.
  const out = new Response(res.body, res);
  out.headers.set('Vary', 'Cookie');
  return out;
}
