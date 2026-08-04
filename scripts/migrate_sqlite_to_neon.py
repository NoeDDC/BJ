"""One-off migration: copy the existing Render SQLite data into Neon Postgres.

Run this ONCE, from an environment that can see BOTH the SQLite file (e.g.
Render's Shell tab, since the file lives on Render's persistent disk) AND
the Neon database (reachable from anywhere once you have the connection
string). See README.md for the full runbook.

Usage:
    python scripts/migrate_sqlite_to_neon.py --database-url "postgresql://..." [--dry-run] [--yes]

    --sqlite         path to the SQLite file (default: $DB or /data/counters.db)
    --database-url   Neon Postgres connection string (default: $DATABASE_URL)
    --dry-run        show what would be copied without writing anything
    --yes            skip the confirmation prompt (for non-interactive use)

Safe to re-run: it upserts, so running it twice just re-copies the same
SQLite snapshot. But if the app has already been receiving writes on Neon
since a previous migration, re-running will overwrite those newer Neon
counters/theme/running-counter values with the older SQLite snapshot —
availability and push subscriptions are unaffected since those are
per-row upserts. When in doubt, use --dry-run first.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from backend import db_postgres, db_sqlite  # noqa: E402
from backend.constants import KEYS, META_KEYS  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sqlite", default=os.environ.get("DB", "/data/counters.db"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if not args.database_url:
        sys.exit("Missing --database-url (or set DATABASE_URL). This must be the Postgres connection "
                  "string from Neon's dashboard, not the napi_... API key.")
    if not os.path.isfile(args.sqlite):
        sys.exit(f"SQLite file not found: {args.sqlite}")

    db_sqlite.init_db(args.sqlite)
    dump = db_sqlite.dump_all()

    print(f"Read from SQLite ({args.sqlite}):")
    print(f"  counters:           {len(dump['counters'])} rows -> {dict(dump['counters'])}")
    print(f"  meta:               {len(dump['meta'])} rows -> {dict(dump['meta'])}")
    print(f"  availability:       {len(dump['availability'])} rows")
    print(f"  push_subscriptions: {len(dump['push_subscriptions'])} rows")

    if args.dry_run:
        print("\n--dry-run: nothing written to Postgres.")
        return

    if not args.yes:
        answer = input("\nWrite this into the Neon database now? This may overwrite existing Neon data "
                        "for matching rows. [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return

    db_postgres.init_db(args.database_url)
    con = db_postgres._connect()
    cur = con.cursor()

    for id_, val in dump["counters"]:
        if id_ in KEYS:
            cur.execute("UPDATE counters SET val=%s WHERE id=%s", (val, id_))

    for key, value in dump["meta"]:
        if key in META_KEYS:
            cur.execute(
                "INSERT INTO meta (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )

    for person, date, status in dump["availability"]:
        cur.execute(
            "INSERT INTO availability (person, date, status) VALUES (%s, %s, %s) "
            "ON CONFLICT (person, date) DO UPDATE SET status = EXCLUDED.status",
            (person, date, status),
        )

    for endpoint, person, p256dh, auth in dump["push_subscriptions"]:
        cur.execute(
            "INSERT INTO push_subscriptions (endpoint, person, p256dh, auth) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (endpoint) DO UPDATE SET person=EXCLUDED.person, p256dh=EXCLUDED.p256dh, auth=EXCLUDED.auth",
            (endpoint, person, p256dh, auth),
        )

    con.commit()
    cur.close()
    con.close()

    print("\nDone. Verifying by reading back from Neon:")
    print(f"  counters: {db_postgres.get_counters()}")
    print(f"  meta:     {db_postgres.get_meta(META_KEYS)}")


if __name__ == "__main__":
    main()
