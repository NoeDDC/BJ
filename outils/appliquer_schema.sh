#!/usr/bin/env bash
# Applique un fichier de schema/ (idempotent) sur la base de production, adresse lue sur Render.
#   outils/appliquer_schema.sh schema/2026-11-16_evenements.sql
set -euo pipefail
cd "$(dirname "$0")/.."
PSQL="$HOME/Applications/Postgres.app/Contents/Versions/18/bin/psql"
python3 outils/avec_env_render.py bash -c '"$0" "$BJ_DATABASE_URL" -q -v ON_ERROR_STOP=1 -f "$1" && "$0" "$BJ_DATABASE_URL" -Atc "select count(*) as evenements from events"' "$PSQL" "$1"
