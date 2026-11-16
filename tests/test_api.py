"""Compare l'API Cloudflare (wrangler pages dev, 8788) à l'ancien serveur Python (3011),
tous deux branchés sur la MÊME branche Neon d'essai, puis teste les événements.

    python3 outils/avec_env.py python3 outils/neon_branche_essai.py creer
    npx wrangler pages dev --port 8788      # et l'ancien : PORT=3011 python3 server.py (branche main)
    python3 tests/test_api.py               # sans l'ancien serveur : seulement les événements
"""
import json, os, sys, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PY, CF = "http://127.0.0.1:3011", "http://127.0.0.1:8788"
echecs = 0


from session import cookie


def call(base, path, body=None):
    h = {"Content-Type": "application/json"}
    if base == CF:   # la personne vient de la session : on se connecte en tant qu'elle
        qui = (body or {}).get("person") or ("n" if "person=n" in path else "z")
        h["Cookie"] = cookie(CF, qui if qui in ("z", "n") else "z")
    r = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                               headers=h, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(r, timeout=30) as res:
        txt = res.read().decode()
        return json.loads(txt) if res.headers.get_content_type() == "application/json" else txt


def status(base, path, body=None):
    try:
        call(base, path, body); return 200
    except urllib.error.HTTPError as e:
        return e.code


def verifie(label, ok, detail=""):
    global echecs
    print(("OK   " if ok else "ÉCHEC ") + label)
    if not ok:
        echecs += 1
        if detail: print("     ", detail[:400])


def sans_dates(x):
    # Python rend des microsecondes et +00:00, JavaScript des millisecondes et Z : même instant.
    if isinstance(x, dict): return {k: (v[:19] if k in ("created_at", "checked_at") and v else sans_dates(v)) for k, v in x.items()}
    if isinstance(x, list): return [sans_dates(v) for v in x]
    return x


try:
    call(PY, "/api/counters"); ancien = True
except Exception:
    ancien = False; print("(ancien serveur absent : comparaison sautée)")

if ancien:
    for p in ["/api/counters", "/api/availability", "/api/notes?person=z", "/api/notes?person=n", "/api/shopping"]:
        a, b = sans_dates(call(PY, p)), sans_dates(call(CF, p))
        verifie("même réponse GET " + p, a == b, f"python={json.dumps(a)} cf={json.dumps(b)}")
    lp, lc = call(PY, "/api/calendar-links"), call(CF, "/api/calendar-links")
    verifie("mêmes jetons de calendrier", {k: v.split("/calendar/")[1] for k, v in lp.items()} == {k: v.split("/calendar/")[1] for k, v in lc.items()})
    etapes = [
        ("/api/counters/adjust", {"key": "zg", "delta": 1}, "/api/counters"),
        ("/api/counters/adjust", {"key": "zg", "delta": -1}, "/api/counters"),
        ("/api/counters/adjust", {"key": "nb", "delta": 2}, "/api/counters"),
        ("/api/counters/adjust", {"key": "nb", "delta": -2}, "/api/counters"),
        ("/api/counters/adjust", {"key": "jours_sans_course", "delta": 1}, "/api/counters"),
        ("/api/counters", {"theme": "theme-2", "jours_sans_course": 999}, "/api/counters"),
        ("/api/availability", {"person": "n", "date": "2030-01-02", "status": "evening"}, "/api/availability"),
        ("/api/availability", {"person": "n", "date": "2030-01-02", "status": None}, "/api/availability"),
        ("/api/notes", {"person": "z", "text": "  note d'essai  "}, "/api/notes?person=z"),
        ("/api/shopping", {"person": "n", "texts": ["Lait", "lait", "  Pain   complet "]}, "/api/shopping"),
        ("/api/shopping", {"person": "z", "text": "LAIT"}, "/api/shopping"),
    ]
    for i, (path, body, relu) in enumerate(etapes):
        srv = CF if i % 2 == 0 else PY
        call(srv, path, body)
        a, b = sans_dates(call(PY, relu)), sans_dates(call(CF, relu))
        verifie(f"écrit par {'CF' if srv == CF else 'PY'}, relu pareil : {path} {json.dumps(body, ensure_ascii=False)}", a == b,
                f"python={json.dumps(a)} cf={json.dumps(b)}")
    # cocher, décocher, supprimer un article (par CF), relu par Python
    art = [x for x in call(CF, "/api/shopping")["items"] if x["text"] == "Pain complet"][0]
    for path, body in [("/api/shopping/check", {"person": "z", "id": art["id"], "checked": True}),
                       ("/api/shopping/check", {"person": "z", "id": art["id"], "checked": False}),
                       ("/api/shopping/delete", {"id": art["id"]})]:
        call(CF, path, body)
        verifie(f"courses {path} relu pareil", sans_dates(call(PY, "/api/shopping")) == sans_dates(call(CF, "/api/shopping")))
    note = [x for x in call(CF, "/api/notes?person=z")["mine"] if x["text"] == "note d'essai"][0]
    call(CF, "/api/notes/delete", {"person": "z", "id": note["id"]})
    verifie("note retirée, relue pareil", sans_dates(call(PY, "/api/notes?person=z")) == sans_dates(call(CF, "/api/notes?person=z")))

# ── événements ──
ev = call(CF, "/api/events", {"person": "z", "date": "2030-03-07", "time": "19:30", "text": "  Resto,  chez Léa ; ", "invited": True})
mien = [e for e in ev if e["date"] == "2030-03-07"]
verifie("événement créé, texte nettoyé", len(mien) == 1 and mien[0]["text"] == "Resto, chez Léa ;" and mien[0]["invited"] and mien[0]["author"] == "z" and mien[0]["time"] == "19:30", json.dumps(mien))
eid = mien[0]["id"]
verifie("refus sans texte (400)", status(CF, "/api/events", {"person": "z", "date": "2030-03-07", "text": "  "}) == 400)
verifie("refus date invalide (400)", status(CF, "/api/events", {"person": "z", "date": "7 mars", "text": "x"}) == 400)
verifie("refus heure invalide (400)", status(CF, "/api/events", {"person": "z", "date": "2030-03-07", "time": "25:00", "text": "x"}) == 400)
call(CF, "/api/events", {"person": "n", "id": eid, "date": "2030-03-08", "text": "piraté", "invited": False})
e = [x for x in call(CF, "/api/events") if x["id"] == eid][0]
verifie("Noé ne modifie pas l'événement de Zoé", e["text"] == "Resto, chez Léa ;" and e["date"] == "2030-03-07")
call(CF, "/api/events/delete", {"person": "n", "id": eid})
verifie("Noé ne retire pas l'événement de Zoé", any(x["id"] == eid for x in call(CF, "/api/events")))
call(CF, "/api/events", {"person": "z", "id": eid, "date": "2030-03-08", "time": None, "text": "Resto déplacé", "invited": False})
e = [x for x in call(CF, "/api/events") if x["id"] == eid][0]
verifie("Zoé modifie le sien (jour, heure retirée, invitation retirée)", e == {"id": eid, "author": "z", "date": "2030-03-08", "time": None, "text": "Resto déplacé", "invited": False}, json.dumps(e))
ev2 = call(CF, "/api/events", {"person": "n", "date": "2030-03-08", "text": "Foot", "invited": False})
autre = [x for x in ev2 if x["text"] == "Foot"][0]
liens = call(CF, "/api/calendar-links")
ics_z = call(CF, "/calendar/" + liens["z"].split("/calendar/")[1])
ics_n = call(CF, "/calendar/" + liens["n"].split("/calendar/")[1])
verifie("flux de Zoé : son événement, pas celui de Noé non invité", "Resto déplacé" in ics_z and "Foot" not in ics_z)
verifie("flux de Noé : son Foot, pas le resto de Zoé (pas invité)", "Foot" in ics_n and "Resto déplacé" not in ics_n)
call(CF, "/api/events", {"person": "z", "id": eid, "date": "2030-03-08", "time": "20:00", "text": "Resto déplacé", "invited": True})
ics_n = call(CF, "/calendar/" + liens["n"].split("/calendar/")[1])
verifie("invité : le resto entre dans le flux de Noé, avec l'heure", "Resto déplacé (Zoé + Noé)" in ics_n and "DTSTART;TZID=Europe/Brussels:20300308T200000" in ics_n)
verifie("le flux garde les dispos (UID inchangés)", "BEGIN:VCALENDAR" in ics_n and ics_n.endswith("END:VCALENDAR\r\n"))
for x in (eid, autre["id"]):
    who = "z" if x == eid else "n"
    call(CF, "/api/events/delete", {"person": who, "id": x})
verifie("événements d'essai retirés", not [x for x in call(CF, "/api/events") if x["date"].startswith("2030-03")])
verifie("flux inconnu : 404", status(CF, "/calendar/inconnu.ics") == 404)
verifie("route inconnue : 404", status(CF, "/api/nimporte") == 404)
print(f"\n{'TOUT VERT' if not echecs else str(echecs) + ' ÉCHEC(S)'}")
sys.exit(1 if echecs else 0)
