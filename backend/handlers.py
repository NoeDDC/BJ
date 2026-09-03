"""HTTP routing: the small JSON API plus static file serving for /public."""
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

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
    # HTTP/1.1 keep-alive: the hosting proxy (Render) reuses one TCP
    # connection to the app for many requests instead of opening a new one
    # per fetch. This relies on every response carrying a Content-Length
    # (they all do) and every request body being consumed (see do_POST).
    protocol_version = "HTTP/1.1"
    timeout = 30  # an idle keep-alive connection frees its thread after this

    def log_message(self, *a):
        pass

    # ── helpers ──────────────────────────────────────────────────────
    def _counters_payload(self):
        return db.get_dashboard()

    def _notes_payload(self, person):
        other = "n" if person == "z" else "z"
        return {"mine": db.get_notes(person), "otherCount": db.count_notes(other)}

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        """Read (and always fully consume) the request body. Malformed or
        non-object JSON is treated as an empty payload."""
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

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
        no_cache = candidate.endswith((".html", "sw.js", ".webmanifest", ".css", ".js"))
        self.send_header("Cache-Control", "no-cache" if no_cache else "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    # ── GET ──────────────────────────────────────────────────────────
    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path

        if path == "/api/counters":
            self._send_json(self._counters_payload())
        elif path == "/api/availability":
            self._send_json(db.get_availability())
        elif path == "/api/notes":
            person = parse_qs(parsed.query).get("person", [None])[0]
            if person not in db.VALID_PERSONS:
                self.send_error(400)
                return
            self._send_json(self._notes_payload(person))
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
        # Always read the body, even for unknown routes: with keep-alive an
        # unread body would be parsed as the start of the next request.
        body = self._read_json_body()

        if path == "/api/counters":
            # Meta only (currently: theme). Counter values, and running
            # counters like jours_sans_course, are never set as absolute
            # snapshots here — see /api/counters/adjust — because a client
            # sending its whole locally-held state back can clobber
            # increments another device made in the meantime.
            body.pop("jours_sans_course", None)
            db.set_meta(body)
            self._send_json(self._counters_payload())

        elif path == "/api/counters/adjust":
            key = body.get("key")
            try:
                delta = int(body.get("delta", 0))
            except (TypeError, ValueError):
                delta = 0

            if key == "jours_sans_course":
                db.adjust_running(delta)
            elif key in db.KEYS and delta:
                increased = db.adjust_journee(key, delta)
                if increased:
                    person, ttype = key[0], key[1]
                    threading.Thread(target=_notify_journee_added, args=(person, ttype), daemon=True).start()

            self._send_json(self._counters_payload())

        elif path == "/api/availability":
            db.set_availability(body.get("person"), body.get("date"), body.get("status"))
            self._send_json(db.get_availability())

        elif path == "/api/notes":
            person = body.get("person")
            if person not in db.VALID_PERSONS:
                self.send_error(400)
                return
            db.add_note(person, body.get("text"))
            self._send_json(self._notes_payload(person))

        elif path == "/api/notes/delete":
            person = body.get("person")
            if person not in db.VALID_PERSONS:
                self.send_error(400)
                return
            try:
                note_id = int(body.get("id"))
            except (TypeError, ValueError):
                note_id = None
            if note_id is not None:
                db.delete_note(person, note_id)
            self._send_json(self._notes_payload(person))

        elif path == "/api/push/subscribe":
            sub = body.get("subscription") or {}
            keys = sub.get("keys") or {}
            db.add_subscription(body.get("person"), sub.get("endpoint"), keys.get("p256dh"), keys.get("auth"))
            self._send_json({"ok": True})

        elif path == "/api/push/unsubscribe":
            db.remove_subscription(body.get("endpoint"))
            self._send_json({"ok": True})

        else:
            self.send_error(404)
