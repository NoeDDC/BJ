"""Branche Neon d'essai (copie de la base de production, jetable).

    python3 outils/avec_env_render.py python3 outils/neon_branche_essai.py creer
    python3 outils/avec_env_render.py python3 outils/neon_branche_essai.py supprimer

`creer` remplace une éventuelle branche du même nom et écrit son adresse dans
.dev.vars (ignoré par Git, droits 600), lu par `wrangler pages dev`. Rien n'est affiché.
"""
import json, os, ssl, sys, time, urllib.error, urllib.request
import certifi

PROJET = "royal-dawn-05099161"
NOM = "essai-cloudflare"
ctx = ssl.create_default_context(cafile=certifi.where())


def api(method, path, body=None):
    r = urllib.request.Request("https://console.neon.tech/api/v2" + path, method=method,
                               data=json.dumps(body).encode() if body else None,
                               headers={"Authorization": "Bearer " + os.environ["BJ_NEON_API_KEY"],
                                        "Accept": "application/json", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, context=ctx))


def supprimer():
    for b in api("GET", f"/projects/{PROJET}/branches")["branches"]:
        if b["name"] == NOM:
            api("DELETE", f"/projects/{PROJET}/branches/{b['id']}")
            print("branche supprimée :", b["id"])
            time.sleep(3)


if sys.argv[1:] == ["creer"]:
    supprimer()
    d = api("POST", f"/projects/{PROJET}/branches", {"branch": {"name": NOM}, "endpoints": [{"type": "read_write"}]})
    lignes = []
    if os.path.exists(".dev.vars"):
        lignes = [l for l in open(".dev.vars") if not l.startswith("DATABASE_URL=")]
    lignes.append(f'DATABASE_URL="{d["connection_uris"][0]["connection_uri"]}"\n')
    with open(".dev.vars", "w") as f:
        f.writelines(lignes)
    os.chmod(".dev.vars", 0o600)
    print("branche créée :", d["branch"]["id"])
elif sys.argv[1:] == ["supprimer"]:
    supprimer()
else:
    print(__doc__)
