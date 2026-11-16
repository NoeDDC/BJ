-- Événements écrits dans le calendrier (2026-11-16). Idempotent.
-- author : 'z' ou 'n' ; invited : l'autre est invité ; time : 'HH:MM' ou NULL (toute la journée).
CREATE TABLE IF NOT EXISTS events (
  id SERIAL PRIMARY KEY,
  author TEXT NOT NULL CHECK (author IN ('z', 'n')),
  date TEXT NOT NULL,
  time TEXT,
  text TEXT NOT NULL,
  invited BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_date ON events (date);
