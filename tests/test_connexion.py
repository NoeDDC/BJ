"""Connexion, contre wrangler pages dev (8788) sur une branche Neon d'essai où le mot de
passe par défaut vient d'être posé (outils/mot_de_passe_defaut.py, lu sur l'entrée standard).

    printf %s changemoi | python3 tests/test_connexion.py

Laisse Zoé et Noé avec le mot de passe du banc (tests/session.py s'en sert ensuite).
"""
import json, sys, urllib.error, urllib.request

B = "http://127.0.0.1:8788"
DEFAUT = sys.stdin.read()
BANC = "mot-de-passe-du-banc"
echecs = 0


class SansRedirection(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None


ouvrir = urllib.request.build_opener(SansRedirection).open


def req(path, body=None, cookie=None, method=None):
    h = {"Content-Type": "application/json"}
    if cookie: h["Cookie"] = cookie
    r = urllib.request.Request(B + path, data=json.dumps(body).encode() if body is not None else None, headers=h,
                               method=method or ("POST" if body is not None else "GET"))
    try:
        res = ouvrir(r, timeout=30)
    except urllib.error.HTTPError as e:
        res = e
    txt = res.read().decode(errors="replace")
    sc = res.headers.get("Set-Cookie", "")
    return res.status, txt, res.headers.get("Location", ""), sc.split(";")[0] if sc else None


def verifie(label, ok, detail=""):
    global echecs
    print(("OK   " if ok else "ÉCHEC ") + label + ("" if ok else "  " + str(detail)[:300]))
    echecs += not ok


s, _, loc, _ = req("/")
verifie("sans session, / renvoie vers /login", s == 302 and loc.endswith("/login"), (s, loc))
verifie("sans session, /js/app.js aussi", req("/js/app.js")[0] == 302)
verifie("sans session, l'API répond 401", req("/api/counters")[0] == 401)
verifie("sans session, une écriture aussi", req("/api/events", {"person": "z", "date": "2030-01-01", "text": "x"})[0] == 401)
verifie("la page de connexion est ouverte", req("/login")[0] == 200)
verifie("le manifeste et les icônes restent ouverts", req("/manifest.webmanifest")[0] == 200 and req("/icons/icon-192.png")[0] == 200)
verifie("les flux .ics restent lisibles sans cookie (jeton faux : 404, pas une redirection)", req("/calendar/faux.ics")[0] == 404)
verifie("mauvais mot de passe : 401", req("/api/auth/login", {"person": "z", "password": "nimporte"})[0] == 401)
verifie("l'autre valeur passée à l'outil n'a rien écrasé", req("/api/auth/login", {"person": "z", "password": "autre"})[0] == 401)
verifie("personne inconnue : 401", req("/api/auth/login", {"person": "x", "password": DEFAUT})[0] == 401)

s, txt, _, c_defaut = req("/api/auth/login", {"person": "z", "password": DEFAUT})
verifie("mot de passe par défaut accepté, changement exigé", s == 200 and json.loads(txt)["mustChange"] is True and c_defaut, txt)
brut = urllib.request.urlopen(urllib.request.Request(B + "/api/auth/logout", data=b"{}", method="POST")).headers.get("Set-Cookie", "")
verifie("cookie HttpOnly et SameSite", "HttpOnly" in brut and "SameSite=Lax" in brut, brut)
s, _, loc, _ = req("/", cookie=c_defaut)
verifie("avant changement, l'app renvoie vers /login?changer", s == 302 and loc.endswith("/login?changer"), (s, loc))
verifie("avant changement, l'API refuse", req("/api/counters", cookie=c_defaut)[0] == 401)
verifie("avant changement, /api/auth/me répond", json.loads(req("/api/auth/me", cookie=c_defaut)[1]) == {"person": "z", "mustChange": True})
verifie("garder le mot de passe par défaut : refusé", req("/api/auth/change", {"password": DEFAUT}, c_defaut)[0] == 400)
verifie("trop court : refusé", req("/api/auth/change", {"password": "court"}, c_defaut)[0] == 400)
s, txt, _, c_z = req("/api/auth/change", {"password": BANC}, c_defaut)
verifie("nouveau mot de passe enregistré, nouvelle session", s == 200 and c_z and c_z != c_defaut, txt)
verifie("l'ancienne session ne vaut plus rien", req("/api/counters", cookie=c_defaut)[0] == 401)
verifie("la nouvelle ouvre l'app et l'API", req("/", cookie=c_z)[0] == 200 and req("/api/counters", cookie=c_z)[0] == 200)
verifie("le mot de passe par défaut ne marche plus pour Zoé", req("/api/auth/login", {"person": "z", "password": DEFAUT})[0] == 401)
verifie("Noé a toujours le sien par défaut", json.loads(req("/api/auth/login", {"person": "n", "password": DEFAUT})[1])["mustChange"] is True)

# la personne vient de la session, pas du corps de la requête
ev = json.loads(req("/api/events", {"person": "n", "date": "2030-02-02", "text": "écrit par Zoé"}, c_z)[1])
e = [x for x in ev if x["text"] == "écrit par Zoé"][0]
verifie("Zoé qui se dit Noé écrit quand même au nom de Zoé", e["author"] == "z")
req("/api/events/delete", {"person": "n", "id": e["id"]}, c_z)
verifie("et retire bien le sien", not [x for x in json.loads(req("/api/events", cookie=c_z)[1]) if x["id"] == e["id"]])
notes_z = json.loads(req("/api/notes?person=n", cookie=c_z)[1])
verifie("Zoé ne lit pas les notes de Noé en demandant ?person=n", "mine" in notes_z)

# Noé : changement, puis blocage après 10 essais ratés
s, _, _, c_ndef = req("/api/auth/login", {"person": "n", "password": DEFAUT})
s, _, _, c_n = req("/api/auth/change", {"password": BANC}, c_ndef)
verifie("Noé choisit le sien", s == 200)
nz = json.loads(req("/api/notes", cookie=c_z)[1]); nn = json.loads(req("/api/notes", cookie=c_n)[1])
verifie("chacun ses notes « à se dire »", nz != nn or nz["mine"] == nn["mine"] == [])
s, _, _, c_out = req("/api/auth/logout", {}, c_z)
verifie("déconnexion : cookie vidé", s == 200 and c_out == "bj_session=")
for _ in range(10):
    req("/api/auth/login", {"person": "n", "password": "faux"})
verifie("après 10 essais ratés, même le bon est refusé (429)", req("/api/auth/login", {"person": "n", "password": BANC})[0] == 429)
print(f"\n{'TOUT VERT' if not echecs else str(echecs) + ' ÉCHEC(S)'}")
sys.exit(1 if echecs else 0)
