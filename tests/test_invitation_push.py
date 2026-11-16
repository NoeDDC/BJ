"""Bout en bout : un faux téléphone de Noé s'abonne (serveur local qui joue le service de
notification), Zoé écrit un événement en l'invitant, le message arrive et se déchiffre.

    python3 tests/test_invitation_push.py     (wrangler pages dev sur 8788, branche d'essai)
"""
import base64, http.server, json, os, sys, threading, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from session import cookie
import http_ece
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

CF = "http://127.0.0.1:8788"
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
recus = []


class FauxService(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        recus.append((dict(self.headers), self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(201); self.end_headers()
    def log_message(self, *a): pass


srv = http.server.HTTPServer(("127.0.0.1", 9911), FauxService)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tel = ec.generate_private_key(ec.SECP256R1())
pub = tel.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
auth = os.urandom(16)
endpoint = "http://127.0.0.1:9911/telephone-de-noe"


def post(path, body):
    h = {"Content-Type": "application/json", "Cookie": cookie(CF, body.get("person") or "z")}
    r = urllib.request.Request(CF + path, data=json.dumps(body).encode(), headers=h, method="POST")
    return json.load(urllib.request.urlopen(r, timeout=30))


post("/api/push/subscribe", {"person": "n", "subscription": {"endpoint": endpoint, "keys": {"p256dh": b64(pub), "auth": b64(auth)}}})
ev = post("/api/events", {"person": "z", "date": "2030-05-17", "time": "19:30", "text": "Concert", "invited": True})
eid = [e for e in ev if e["text"] == "Concert"][0]["id"]
for _ in range(50):
    if recus: break
    time.sleep(0.2)
try:
    assert recus, "aucune notification reçue"
    entetes, corps = recus[0]
    msg = json.loads(http_ece.decrypt(corps, private_key=tel, auth_secret=auth, version="aes128gcm"))
    print("reçu :", msg["body"])
    assert msg["body"].startswith("Zoé t'invite vendredi 17 mai à 19 h 30 : Concert"), msg
    assert entetes["Authorization"].startswith("vapid t=")
    # sans invitation : rien ne part
    recus.clear()
    post("/api/events", {"person": "z", "id": eid, "date": "2030-05-17", "time": "19:30", "text": "Concert", "invited": True})
    post("/api/events", {"person": "z", "date": "2030-05-18", "text": "Seule", "invited": False})
    time.sleep(3)
    assert not recus, f"{len(recus)} notification(s) de trop"
    print("OK : invitation reçue et déchiffrée ; rien de plus pour une modification ni sans invitation")
finally:
    for e in post("/api/events", {"person": "z", "date": "2030-05-18", "text": "x"}):
        if e["date"].startswith("2030-05"):
            post("/api/events/delete", {"person": e["author"], "id": e["id"]})
    post("/api/push/unsubscribe", {"person": "n", "endpoint": endpoint})
