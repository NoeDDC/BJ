"""HTTP routing: the small JSON API plus static file serving for /public."""
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from . import db, ics, push

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

    def _base_url(self):
        proto = self.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
        host = self.headers.get("Host", "localhost")
        if not proto:
            proto = "http" if host.startswith("localhost") or host.startswith("127.0.0.1") else "https"
        return f"{proto}://{host}"

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
        elif path == "/api/calendar-links":
            base = self._base_url()
            links = {p: f"{base}/calendar/{db.get_ics_token(p)}.ics" for p in db.VALID_PERSONS}
            self._send_json(links)
        elif path.startswith("/calendar/") and path.endswith(".ics"):
            token = path[len("/calendar/"):-len(".ics")]
            person = db.find_person_by_ics_token(token)
            if not person:
                self.send_error(404)
                return
            dates = [d for d, status in db.get_availability().get(person, {}).items() if status == "free"]
            body = ics.build_ics(person, dates).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/":
            self._serve_static("index.html")
        else:
            self._serve_static(path)

    # ── POST ─────────────────────────────────────────────────────────
    def do_POST(self):
        path = urlsplit(self.path).path

        if path == "/api/counters":
            # Meta only (currently: theme). Counter values, and running
            # counters like jours_sans_course, are never set as absolute
            # snapshots here — see /api/counters/adjust — because a client
            # sending its whole locally-held state back can clobber
            # increments another device made in the meantime.
            body = self._read_json_body()
            body.pop("jours_sans_course", None)
            db.set_meta(body)
            result = db.get_counters()
            result.update(db.get_meta(db.META_KEYS))
            self._send_json(result)

        elif path == "/api/counters/adjust":
            body = self._read_json_body()
            key = body.get("key")
            try:
                delta = int(body.get("delta", 0))
            except (TypeError, ValueError):
                delta = 0

            if key == "jours_sans_course":
                db.adjust_running(delta)
            elif key in db.KEYS and delta:
                old = db.get_counters()
                db.adjust_counter(key, delta)
                if db.get_counters().get(key, 0) > old.get(key, 0):
                    person, ttype = key[0], key[1]
                    threading.Thread(target=_notify_journee_added, args=(person, ttype), daemon=True).start()

            result = db.get_counters()
            result.update(db.get_meta(db.META_KEYS))
            self._send_json(result)

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
