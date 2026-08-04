"""Entry point — run with: python server.py

Env vars (see .env.example — locally, put them in a .env file next to this
script and they're loaded automatically; in production, set them in your
host's dashboard instead):
  DATABASE_URL  Postgres (Neon) connection string. If set, this is used
                instead of SQLite — see README.md for the Neon migration.
  DB            path to the SQLite file, only used when DATABASE_URL is
                unset (default /data/counters.db)
  PORT          HTTP port (default 3000)
"""
import os
from http.server import ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from backend import db, push  # noqa: E402 (must come after load_dotenv)
from backend.handlers import Handler  # noqa: E402

DB = os.environ.get("DB", "/data/counters.db")

if __name__ == "__main__":
    db.init_db(DB)
    push.init_vapid(DB)
    port = int(os.environ.get("PORT", 3000))
    print(f"Bonne journee -> http://localhost:{port}  (DB backend: {db.BACKEND})")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
