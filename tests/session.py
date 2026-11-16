"""Sessions du banc : Zoé et Noé connectés avec le mot de passe du banc
(posé par tests/test_connexion.py). Rend le cookie « bj_session=... » de chacun."""
import json, urllib.request

BANC = "mot-de-passe-du-banc"
_cache = {}


def cookie(base, person):
    if (base, person) not in _cache:
        r = urllib.request.Request(base + "/api/auth/login", data=json.dumps({"person": person, "password": BANC}).encode(),
                                   headers={"Content-Type": "application/json"}, method="POST")
        res = urllib.request.urlopen(r, timeout=30)
        assert not json.load(res)["mustChange"], "lancer d'abord tests/test_connexion.py"
        _cache[(base, person)] = res.headers["Set-Cookie"].split(";")[0]
    return _cache[(base, person)]
