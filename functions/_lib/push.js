// Notifications Web Push (VAPID + chiffrement aes128gcm, RFC 8291 et 8292),
// écrites avec WebCrypto : les bibliothèques Node (web-push) ne tournent pas
// dans une fonction Cloudflare.
//
// Clés : VAPID_PUBLIC (65 octets, point non compressé) et VAPID_PRIVATE
// (32 octets), en base64url, posées comme secrets du projet Pages. Changer la
// paire rend invalides tous les abonnements existants : chacun devrait
// réactiver les notifications.

const enc = new TextEncoder();

export function b64urlToBytes(s) {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(s + '='.repeat((4 - (s.length % 4)) % 4));
  return Uint8Array.from(bin, c => c.charCodeAt(0));
}

export function bytesToB64url(b) {
  let s = '';
  for (const x of new Uint8Array(b)) s += String.fromCharCode(x);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function concat(...parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let i = 0;
  for (const p of parts) { out.set(p, i); i += p.length; }
  return out;
}

async function hkdf(salt, ikm, info, bytes) {
  const key = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'HKDF', hash: 'SHA-256', salt, info }, key, bytes * 8));
}

// Jeton VAPID (JWT ES256) : prouve au service de notification que l'envoi
// vient bien du détenteur de la clé avec laquelle le téléphone s'est abonné.
async function vapidHeader(endpoint, env) {
  const pub = b64urlToBytes(env.VAPID_PUBLIC);
  const jwk = {
    kty: 'EC', crv: 'P-256', ext: true,
    x: bytesToB64url(pub.slice(1, 33)),
    y: bytesToB64url(pub.slice(33, 65)),
    d: env.VAPID_PRIVATE,
  };
  const key = await crypto.subtle.importKey('jwk', jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const head = bytesToB64url(enc.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const body = bytesToB64url(enc.encode(JSON.stringify({
    aud: new URL(endpoint).origin,
    exp: Math.floor(Date.now() / 1000) + 12 * 3600,
    sub: env.VAPID_SUBJECT || 'mailto:noedrionduchapois@gmail.com',
  })));
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, enc.encode(`${head}.${body}`));
  return `vapid t=${head}.${body}.${bytesToB64url(sig)}, k=${env.VAPID_PUBLIC}`;
}

// Chiffre le message pour CE téléphone (clés p256dh et auth de son abonnement).
export async function encrypt(payload, p256dh, authSecret, salt = crypto.getRandomValues(new Uint8Array(16))) {
  const uaPub = b64urlToBytes(p256dh);
  const auth = b64urlToBytes(authSecret);
  const local = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const asPub = new Uint8Array(await crypto.subtle.exportKey('raw', local.publicKey));
  const uaKey = await crypto.subtle.importKey('raw', uaPub, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, local.privateKey, 256));

  const ikm = await hkdf(auth, shared, concat(enc.encode('WebPush: info\0'), uaPub, asPub), 32);
  const cek = await hkdf(salt, ikm, enc.encode('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(salt, ikm, enc.encode('Content-Encoding: nonce\0'), 12);

  const plain = concat(enc.encode(payload), new Uint8Array([2]));   // 2 = dernier (et seul) bloc
  const aes = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, aes, plain));

  const rs = new Uint8Array([0, 0, 16, 0]);   // taille de bloc 4096
  return concat(salt, rs, new Uint8Array([asPub.length]), asPub, cipher);
}

// Envoie un message à un abonnement. Rend { ok, expired } : expired = le
// téléphone s'est désabonné (404, 410), l'abonnement est à oublier.
export async function sendPush(env, sub, message) {
  try {
    const body = await encrypt(JSON.stringify(message), sub.keys.p256dh, sub.keys.auth);
    const res = await fetch(sub.endpoint, {
      method: 'POST',
      headers: {
        Authorization: await vapidHeader(sub.endpoint, env),
        'Content-Encoding': 'aes128gcm',
        'Content-Type': 'application/octet-stream',
        TTL: '86400',
        Urgency: 'normal',
      },
      body,
    });
    return { ok: res.ok, expired: res.status === 404 || res.status === 410 };
  } catch (e) {
    return { ok: false, expired: false };
  }
}
