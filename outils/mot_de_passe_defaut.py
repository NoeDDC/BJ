"""Pose le mot de passe par défaut (à changer à la première connexion) pour Zoé et Noé.

    printf %s 'le-mot-de-passe' | python3 outils/avec_env_render.py python3 outils/mot_de_passe_defaut.py
    printf %s 'le-mot-de-passe' | DATABASE_URL=... python3 outils/mot_de_passe_defaut.py     (branche d'essai)

Le mot de passe arrive par l'entrée standard, jamais en argument ni dans Git. Il n'est
écrit qu'en hash PBKDF2-SHA256 (même calcul que functions/_lib/auth.js), avec must_change.
Ne remplace JAMAIS un mot de passe déjà choisi : seulement les personnes sans ligne,
ou, avec --reinitialiser z|n, celle qu'on nomme (mot de passe oublié).
"""
import hashlib, os, secrets, subprocess, sys

ITERATIONS = 100000
mdp = sys.stdin.read()
if not mdp:
    sys.exit("mot de passe vide sur l'entrée standard")
url = os.environ.get("DATABASE_URL") or os.environ["BJ_DATABASE_URL"]
reinit = sys.argv[2] if sys.argv[1:2] == ["--reinitialiser"] else None
psql = os.path.expanduser("~/Applications/Postgres.app/Contents/Versions/18/bin/psql")
sql = []
for p in ("z", "n"):
    sel = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", mdp.encode(), bytes.fromhex(sel), ITERATIONS).hex()
    conflit = ("DO UPDATE SET hash = EXCLUDED.hash, salt = EXCLUDED.salt, iterations = EXCLUDED.iterations, "
               "must_change = true, version = passwords.version + 1, updated_at = now()") if reinit == p else "DO NOTHING"
    if reinit and reinit != p:
        continue
    sql.append(f"INSERT INTO passwords (person, hash, salt, iterations, must_change) "
               f"VALUES ('{p}', '{h}', '{sel}', {ITERATIONS}, true) ON CONFLICT (person) {conflit};")
sql.append("SELECT person || ' : ' || CASE WHEN must_change THEN 'à changer' ELSE 'choisi' END FROM passwords ORDER BY person;")
r = subprocess.run([psql, url, "-q", "-At", "-v", "ON_ERROR_STOP=1", "-c", "\n".join(sql)], capture_output=True, text=True)
print(r.stdout.strip() or r.stderr.strip()[-300:])
sys.exit(r.returncode)
