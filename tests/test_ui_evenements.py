"""Parcours à l'écran (WebKit, format iPhone) contre wrangler pages dev (8788) :
Zoé écrit un événement en invitant Noé, Noé le voit « t'invite » sans pouvoir le modifier,
Zoé le modifie puis le retire ; les dispos (tap) marchent toujours.

    python3 tests/test_ui_evenements.py        (captures dans tests/captures/)
"""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from session import cookie
from playwright.sync_api import sync_playwright

CF = "http://127.0.0.1:8788"
ICI = os.path.dirname(os.path.abspath(__file__))
erreurs = []


def api(path):
    r = urllib.request.Request(CF + path, headers={"Cookie": cookie(CF, "z")})
    return json.load(urllib.request.urlopen(r))


with sync_playwright() as p:
    nav = p.webkit.launch()
    iphone = {**p.devices["iPhone 13"]}
    def page_de(qui):
        ctx = nav.new_context(**iphone)
        nom, val = cookie(CF, qui).split("=", 1)
        ctx.add_cookies([{"name": nom, "value": val, "url": CF}])
        ctx.add_init_script(f"localStorage.setItem('bj_person', '{qui}')")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: erreurs.append(f"{qui}: {e}"))
        pg.goto(CF + "/")
        pg.click(".nav-btn[data-view=calendar]")
        pg.wait_for_selector("#calEventsList")
        return pg

    z = page_de("z")
    avant = len(api("/api/events"))
    z.click(".cal-write-btn")
    z.wait_for_selector("#eventSheet.show")
    assert z.inner_text("#evInviteLabel") == "Inviter Noé"
    z.fill("#evText", "Resto chez Léa")
    z.fill("#evTime", "19:30")
    z.check("#evInvited")
    z.screenshot(path=f"{ICI}/captures/1-ecrire.png")
    z.click("#evSave")
    z.wait_for_selector("#eventSheet:not(.show)")
    z.wait_for_selector(".ev-item.mine")
    texte = z.inner_text(".ev-item.mine")
    assert "Resto chez Léa" in texte and "19:30" in texte and "Noé invité" in texte, texte
    assert z.locator(".day-cell.today .day-ev.both").count() == 1, "marque du jour absente"
    z.screenshot(path=f"{ICI}/captures/2-liste-zoe.png")

    n = page_de("n")
    n.wait_for_selector(".ev-item.z")
    tn = n.inner_text(".ev-item.z")
    assert "t'invite" in tn and "Zoé" in tn, tn
    assert n.locator(".ev-item.mine").count() == 0
    n.click(".ev-item.z")
    assert not n.is_visible("#eventSheet.show"), "Noé ne doit pas pouvoir ouvrir l'événement de Zoé"
    n.screenshot(path=f"{ICI}/captures/3-liste-noe.png")

    z.click(".ev-item.mine")
    z.wait_for_selector("#eventSheet.show")
    assert z.input_value("#evText") == "Resto chez Léa" and z.is_checked("#evInvited")
    assert z.is_visible("#evDelete")
    z.fill("#evText", "Resto chez Léa et Tom")
    z.uncheck("#evInvited")
    z.click("#evSave")
    z.wait_for_selector("#eventSheet:not(.show)")
    t2 = z.inner_text(".ev-item.mine")
    assert "Léa et Tom" in t2 and "invité" not in t2, t2
    assert z.locator(".day-cell.today .day-ev.z").count() == 1

    # la dispo (tap) marche toujours, et ne touche pas aux événements
    z.click(".day-cell.today")
    z.wait_for_timeout(1500)
    aujourdhui = z.get_attribute(".day-cell.today", "data-date")
    assert api("/api/availability")["z"].get(aujourdhui) == "free", "le tap ne pose plus la dispo"
    z.click(".day-cell.today"); z.wait_for_timeout(1500)
    assert aujourdhui not in api("/api/availability")["z"]

    # sans texte : message, rien n'est enregistré
    z.click(".cal-write-btn"); z.wait_for_selector("#eventSheet.show")
    z.click("#evSave")
    assert z.inner_text("#evError") == "Écris quelque chose."
    z.click("text=Annuler")

    z.click(".ev-item.mine"); z.wait_for_selector("#eventSheet.show")
    z.click("#evDelete")
    z.wait_for_selector("#eventSheet:not(.show)")
    assert len(api("/api/events")) == avant, "événement pas retiré"
    assert "Rien d'écrit ce mois-ci." in z.inner_text("#calEventsList") or z.locator(".ev-item.mine").count() == 0
    nav.close()

print("erreurs JS :", erreurs)
sys.exit(1 if erreurs else 0)
