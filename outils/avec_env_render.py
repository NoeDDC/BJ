"""Lance une commande avec les variables Render du service BonneJournée, préfixées BJ_
(BJ_DATABASE_URL, BJ_NEON_API_KEY...), sans jamais les afficher.

    python3 outils/avec_env_render.py <commande> [args...]

Lit la clé API Render dans ~/Developer/ORAPACE/.env (même compte Render).
Utile tant que Render garde ces variables ; à retirer avec le service Render.
"""
import json, os, ssl, subprocess, sys, urllib.request
import certifi
from dotenv import dotenv_values

SERVICE = "srv-d88p2djbc2fs73efvlk0"
cle = dotenv_values(os.path.expanduser("~/Developer/ORAPACE/.env"))["RENDER_API_KEY"]
ctx = ssl.create_default_context(cafile=certifi.where())
req = urllib.request.Request(f"https://api.render.com/v1/services/{SERVICE}/env-vars?limit=50",
                             headers={"Authorization": "Bearer " + cle, "Accept": "application/json"})
env = dict(os.environ)
for v in json.load(urllib.request.urlopen(req, context=ctx)):
    env["BJ_" + v["envVar"]["key"]] = v["envVar"]["value"]
sys.exit(subprocess.call(sys.argv[1:], env=env))
