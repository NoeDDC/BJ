"""HTTP routing: the small JSON API plus static file serving for /public."""
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from . import db, push

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/png", ".png")

PERSON_NAMES = {"z": "Zoé", "n": "Noé"}


def _notify_journee_added(person, ttype):
    """Runs on a background thread so the API response is never delayed
    by the outbound push network call."""
    other = "n" if person == "z" else "z"
    subs = db.get_subscriptions(other)
    if not subs:
        return
    kind = "bonne journée ☀︎" if ttype == "g" else "mauvaise journée ☁︎"
    payload = {
        "title": "Bonne journée",
        "body": f"{PERSON_NAMES.get(person, person)} a ajouté une {kind}",
        "tag": f"journee-{person}{ttype}",
    }
    for sub in subs:
        ok, expired = push.send_push(sub, payload)
        if expired:
            db.remove_subscription(sub["endpoint"])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    # ── helpers ──────────────────────────────────────────────────────
    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _serve_static(self, rel_path):
        rel_path = rel_path.lstrip("/") or "index.html"
        candidate = os.path.normpath(os.path.join(PUBLIC_DIR, rel_path))
        if not candidate.startswith(os.path.normpath(PUBLIC_DIR)):
            self.send_error(403)
            return
        if not os.path.isfile(candidate):
            self.send_error(404)
            return
        ctype, _ = mimetypes.guess_type(candidate)
        with open(candidate, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", len(data))
        no_cache = candidate.endswith((".html", "sw.js", ".webmanifest"))
        self.send_header("Cache-Control", "no-cache" if no_cache else "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    # ── GET ──────────────────────────────────────────────────────────
    def do_GET(self):
        path = urlsplit(self.path).path

        if path == "/api/counters":
            data = db.get_counters()
            data.update(db.get_meta(db.META_KEYS))
            self._send_json(data)
        elif path == "/api/availability":
            self._send_json(db.get_availability())
        elif path == "/api/push/public-key":
            self._send_json({"publicKey": push.get_public_key()})
        elif path == "/":
            self._serve_static("index.html")
        else:
            self._serve_static(path)

    # ── POST ─────────────────────────────────────────────────────────
    def do_POST(self):
        path = urlsplit(self.path).path

        if path == "/api/counters":
            body = self._read_json_body()
            old = db.get_counters()
            db.set_counters(body)
            db.set_meta(body)
            result = db.get_counters()
            result.update(db.get_meta(db.META_KEYS))
            self._send_json(result)

            for k in db.KEYS:
                if k not in body:
                    continue
                try:
                    new_val = int(body[k])
                except (TypeError, ValueError):
                    continue
                if new_val > old.get(k, 0):
                    person, ttype = k[0], k[1]
                    threading.Thread(target=_notify_journee_added, args=(person, ttype), daemon=True).start()

        elif path == "/api/availability":
            body = self._read_json_body()
            db.set_availability(body.get("person"), body.get("date"), body.get("status"))
            self._send_json(db.get_availability())

        elif path == "/api/push/subscribe":
            body = self._read_json_body()
            sub = body.get("subscription") or {}
            keys = sub.get("keys") or {}
            db.add_subscription(body.get("person"), sub.get("endpoint"), keys.get("p256dh"), keys.get("auth"))
            self._send_json({"ok": True})

        elif path == "/api/push/unsubscribe":
            body = self._read_json_body()
            db.remove_subscription(body.get("endpoint"))
            self._send_json({"ok": True})

        else:
            self.send_error(404)
