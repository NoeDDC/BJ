"""Parcours de connexion à l'écran (WebKit, format iPhone) contre wrangler pages dev (8788).
Zoé doit avoir le mot de passe par défaut (outils/mot_de_passe_defaut.py --reinitialiser z).

    printf %s changemoi | python3 tests/test_ui_connexion.py
"""
import os, sys
from playwright.sync_api import sync_playwright

B = "http://127.0.0.1:8788"
DEFAUT = sys.stdin.read()
ICI = os.path.dirname(os.path.abspath(__file__))
os.makedirs(f"{ICI}/captures", exist_ok=True)
erreurs = []
with sync_playwright() as p:
    nav = p.webkit.launch()
    pg = nav.new_context(**p.devices["iPhone 13"]).new_page()
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(B + "/")
    assert pg.url.endswith("/login"), pg.url
    pg.screenshot(path=f"{ICI}/captures/c1-qui.png")
    pg.click("button.z")
    assert pg.inner_text("#bonjour") == "Zoé"
    pg.fill("#mdp", "faux-mot-de-passe"); pg.click("#btnMdp")
    pg.wait_for_selector("#errMdp:not(:empty)")
    assert pg.inner_text("#errMdp") == "Mot de passe incorrect.", pg.inner_text("#errMdp")
    pg.fill("#mdp", DEFAUT); pg.screenshot(path=f"{ICI}/captures/c2-mdp.png"); pg.click("#btnMdp")
    pg.wait_for_selector("#etapeNouveau:not([hidden])")
    pg.fill("#nouveau", "un-autre-mot"); pg.fill("#nouveau2", "pas-pareil"); pg.click("#btnNouveau")
    assert pg.inner_text("#errNouveau") == "Les deux ne sont pas pareils."
    pg.fill("#nouveau", DEFAUT); pg.fill("#nouveau2", DEFAUT); pg.click("#btnNouveau")
    pg.wait_for_selector("#errNouveau:not(:empty)")
    assert "différent" in pg.inner_text("#errNouveau"), pg.inner_text("#errNouveau")
    pg.fill("#nouveau", "mot-de-passe-du-banc"); pg.fill("#nouveau2", "mot-de-passe-du-banc")
    pg.screenshot(path=f"{ICI}/captures/c3-nouveau.png"); pg.click("#btnNouveau")
    pg.wait_for_url(B + "/")
    pg.click(".nav-btn[data-view=calendar]"); pg.wait_for_selector("#calYou b")
    assert pg.inner_text("#calYou b") == "Zoé", pg.inner_text("#calYou")
    pg.screenshot(path=f"{ICI}/captures/c4-dans-l-app.png")
    # rechargée : toujours connectée, sans repasser par la connexion
    pg.reload(); pg.wait_for_timeout(1500)
    assert pg.url == B + "/", pg.url
    pg.click(".nav-btn[data-view=calendar]"); pg.wait_for_selector("#calYou a")
    pg.click("#calYou a")
    pg.wait_for_url(B + "/login")
    pg.goto(B + "/"); assert pg.url.endswith("/login"), "toujours connectée après la déconnexion"
    nav.close()
print("erreurs JS :", erreurs)
sys.exit(1 if erreurs else 0)
