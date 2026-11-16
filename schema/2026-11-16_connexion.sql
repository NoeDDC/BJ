-- Connexion (2026-11-16). Idempotent. Un mot de passe par personne, jamais en clair :
-- PBKDF2-SHA256 (100 000 tours, le maximum de WebCrypto chez Cloudflare), sel aléatoire.
-- must_change : le mot de passe par défaut doit être remplacé à la première connexion.
-- version : augmente à chaque changement ; une session émise avant ne vaut plus rien.
CREATE TABLE IF NOT EXISTS passwords (
  person TEXT PRIMARY KEY CHECK (person IN ('z', 'n')),
  hash TEXT NOT NULL,
  salt TEXT NOT NULL,
  iterations INTEGER NOT NULL,
  must_change BOOLEAN NOT NULL DEFAULT true,
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Essais ratés, pour freiner qui tenterait de deviner (10 par personne en 15 minutes).
CREATE TABLE IF NOT EXISTS login_fails (
  id SERIAL PRIMARY KEY,
  person TEXT NOT NULL,
  at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS login_fails_person_at ON login_fails (person, at);
