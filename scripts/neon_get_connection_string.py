"""Fetch your Neon Postgres connection string using your Neon API key.

The napi_... key you already have manages Neon itself (list/create
projects & branches) — it is NOT what the app uses to talk to the
database. This script spends that key once to look up the real Postgres
connection string, so you don't have to hunt for it in the dashboard.

Run this LOCALLY, in your own terminal, so the key never leaves your
machine (don't paste it into a chat/AI tool). It reads NEON_API_KEY from
your .env file if you have one there, or you can pass it inline:

    python scripts/neon_get_connection_string.py
    NEON_API_KEY=napi_xxx python scripts/neon_get_connection_string.py

If you have more than one Neon project, it'll ask you to also set
NEON_PROJECT_ID. Prints the pooled connection string — that's the value
to set as DATABASE_URL in Render.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API = "https://console.neon.tech/api/v2"


def call(path, token):
    req = urllib.request.Request(f"{API}{path}", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main():
    token = os.environ.get("NEON_API_KEY")
    if not token:
        sys.exit("Set NEON_API_KEY in your shell first (don't paste it anywhere else).")

    projects = call("/projects", token)["projects"]
    if not projects:
        sys.exit("No Neon projects found for this API key.")

    project_id = os.environ.get("NEON_PROJECT_ID")
    if not project_id:
        if len(projects) > 1:
            print("Multiple Neon projects found — set NEON_PROJECT_ID to one of:")
            for p in projects:
                print(f"  {p['id']}  ({p['name']})")
            sys.exit(1)
        project_id = projects[0]["id"]
        print(f"Using project: {projects[0]['name']} ({project_id})")

    branches = call(f"/projects/{project_id}/branches", token)["branches"]
    default_branch = next((b for b in branches if b.get("default")), branches[0])
    branch_id = default_branch["id"]

    databases = call(f"/projects/{project_id}/branches/{branch_id}/databases", token)["databases"]
    database_name = databases[0]["name"]

    roles = call(f"/projects/{project_id}/branches/{branch_id}/roles", token)["roles"]
    role_name = next((r["name"] for r in roles if not r.get("protected")), roles[0]["name"])

    uri = call(
        f"/projects/{project_id}/connection_uri"
        f"?branch_id={branch_id}&database_name={database_name}&role_name={role_name}&pooled=true",
        token,
    )["uri"]

    print("\nDATABASE_URL (pooled) — copy this into Render's environment variables:\n")
    print(uri)


if __name__ == "__main__":
    main()
