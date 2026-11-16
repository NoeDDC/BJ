"""Lance une commande avec les accès de Bonne journée, préfixés BJ_
(BJ_DATABASE_URL, BJ_NEON_API_KEY), sans jamais les afficher.

    python3 outils/avec_env.py <commande> [args...]

Lit ~/Developer/sauvegardes/bonne-journee/env.json (hors Git, chmod 600,
compris dans sauvegarde-cles.sh). Ces valeurs vivaient sur le service Render,
supprimé le 2026-11-16.
"""
import json, os, subprocess, sys

with open(os.path.expanduser("~/Developer/sauvegardes/bonne-journee/env.json")) as f:
    valeurs = json.load(f)
env = dict(os.environ)
for k, v in valeurs.items():
    env["BJ_" + k] = v
sys.exit(subprocess.call(sys.argv[1:], env=env))
