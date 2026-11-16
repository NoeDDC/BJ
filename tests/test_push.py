"""Chiffre avec functions/_lib/push.js (Node, WebCrypto), déchiffre avec http_ece
(bibliothèque Python de référence) et vérifie la signature du jeton VAPID.

    python3 tests/test_push.py      (pip install http_ece cryptography)
"""
import base64, json, os, subprocess
import http_ece
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
unb64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
PUSH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "functions", "_lib", "push.js")

telephone = ec.generate_private_key(ec.SECP256R1())
tel_pub = telephone.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
auth = os.urandom(16)
vapid = ec.generate_private_key(ec.SECP256R1())
v_pub = vapid.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
v_priv = vapid.private_numbers().private_value.to_bytes(32, "big")
message = {"title": "Bonne journée", "body": "Zoé t'invite samedi ☀︎"}

js = f"""
let entetes, corps;
globalThis.fetch = async (u, o) => {{ entetes = o.headers; corps = o.body; return new Response('', {{status: 201}}); }};
const {{ sendPush, bytesToB64url }} = await import({json.dumps(os.path.abspath(PUSH))});
const r = await sendPush({{VAPID_PUBLIC: '{b64(v_pub)}', VAPID_PRIVATE: '{b64(v_priv)}'}},
  {{endpoint: 'https://fcm.googleapis.com/fcm/send/abc', keys: {{p256dh: '{b64(tel_pub)}', auth: '{b64(auth)}'}}}},
  {json.dumps(message)});
console.log(JSON.stringify({{ok: r.ok, corps: bytesToB64url(corps), auth: entetes.Authorization, ce: entetes['Content-Encoding']}}));
"""
node_path = os.path.expanduser("~/.local/opt/node/bin") + ":" + os.environ["PATH"]
out = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", js], env={**os.environ, "PATH": node_path}))
clair = http_ece.decrypt(unb64(out["corps"]), private_key=telephone, auth_secret=auth, version="aes128gcm")
assert json.loads(clair) == message, clair
assert out["ce"] == "aes128gcm" and out["ok"]
t = out["auth"].split("t=")[1].split(",")[0]
k = out["auth"].split("k=")[1]
h, p, s = t.split(".")
sig = unb64(s)
der = encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big"))
ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64(k)).verify(der, f"{h}.{p}".encode(), ec.ECDSA(hashes.SHA256()))
assert json.loads(unb64(p))["aud"] == "https://fcm.googleapis.com"
print("OK : message déchiffré par http_ece, jeton VAPID signé et valide")
