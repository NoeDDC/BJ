# Bonne journée
App privée de Zoé et Noé, installée en PWA sur leurs téléphones : journal des bonnes et mauvaises journées, calendrier (dispos et programme écrit, avec ou sans invitation), « à se dire », liste de courses commune, notifications. Pas de compte : on choisit « Zoé » ou « Noé » sur le téléphone.

## Démarrer
```bash
npm install
python3 outils/avec_env_render.py python3 outils/neon_branche_essai.py creer   # copie jetable de la base -> .dev.vars
# ajouter VAPID_PUBLIC et VAPID_PRIVATE de test à .dev.vars (n'importe quelle paire P-256)
npx wrangler pages dev --port 8788       # app + API en local, sur la copie
python3 tests/test_push.py               # chiffrement des notifications (http_ece)
python3 tests/test_api.py                # API (+ comparaison à l'ancien serveur Python s'il tourne sur 3011)
python3 tests/test_invitation_push.py    # invitation reçue par un faux téléphone
python3 tests/test_ui_evenements.py      # parcours à l'écran, WebKit format iPhone
python3 outils/avec_env_render.py python3 outils/neon_branche_essai.py supprimer
npx wrangler pages deploy --branch main  # mise en ligne (accord de Noé)
```
Nouveau fichier de `schema/` : `outils/appliquer_schema.sh schema/<fichier>.sql` (idempotent, base de production).

## Organisation
- `public/` : l'app (index.html, js/app.js, css, sw.js, manifeste, icônes), servie telle quelle ; `public/_headers` pour le cache.
- `functions/api/[[route]].js` : toute l'API ; `functions/calendar/[[path]].js` : flux `.ics` ; `functions/_lib/` : base (`db.js`), notifications Web Push écrites en WebCrypto (`push.js`), iCalendar (`ics.js`).
- `schema/` : changements de base, datés. `outils/`, `tests/`.
- `backend/`, `server.py`, `Procfile`, `requirements.txt` : ancien serveur Python de Render, gardé tant que Render n'est pas arrêté.

## Où travailler
- Dossier `~/Developer/BJ`, dépôt `NoeDDC/BJ`. Branche `cloudflare` : la version en ligne depuis le 2026-11-16. `main` porte encore l'ancienne version Render.
- En ligne : https://bonne-journee.pages.dev (projet Cloudflare Pages `bonne-journee`, compte de Noé, déployé par `wrangler`, pas relié à GitHub, séparé du projet du fermage).
- Données : Neon, projet `royal-dawn-05099161` (us-east-2), base `neondb`.

## Accès
- `wrangler` est connecté au compte Cloudflare de Noé (OAuth, `npx wrangler whoami`).
- Secrets du projet Pages (jamais dans Git) : `DATABASE_URL`, `VAPID_PUBLIC`, `VAPID_PRIVATE`. Copie des clés VAPID : `~/Developer/sauvegardes/bonne-journee/vapid.json` (dans `sauvegarde-cles.sh`).
- `DATABASE_URL` et `NEON_API_KEY` sont aussi lues sur le service Render « BonneJournée » par `outils/avec_env_render.py` (clé Render dans `~/Developer/ORAPACE/.env`). À recopier ailleurs avant de supprimer ce service.

## Décisions
- 2026-11-16 : quitter Render (7,25 $ par mois, plan Starter et disque) pour Cloudflare Pages gratuit, sans délai de réveil du serveur. Neon gardé (réveil en moins d'une seconde). Demande de Noé, projet Pages séparé de celui du fermage.
- API identique à l'ancien serveur Python (vérifié par `tests/test_api.py`, mêmes réponses sur la même base) : l'app n'a pas changé pour ça.
- Calendrier (demande de Noé, 2026-11-16) : le tap (dispo) et l'appui long (acti le soir, nuit ok) ne changent pas ; « ✎ Écrire » ajoute un programme sur un jour, heure facultative, case « Inviter ». Les deux voient tout ; seul l'auteur modifie ou retire. Une invitation neuve notifie l'autre. Le flux `.ics` d'une personne contient ses dispos, ce qu'elle a écrit et ce à quoi on l'a invitée.
- `placement = smart` : la fonction tourne près de Neon (Virginie), pas près du téléphone.

## État au 2026-11-16
- Fait et vérifié : en ligne sur https://bonne-journee.pages.dev ; mêmes compteurs et mêmes dispos que Render, 45 appels sans erreur, aucune erreur JS à l'écran, écriture et retrait d'un événement en production. Table `events` créée en production.
- Pas fait : Zoé et Noé doivent installer la nouvelle adresse, réactiver les notifications (nouvelles clés) et recoller leur lien `.ics`. Service Render « BonneJournée » toujours actif (et payant).
- Pas vérifié : une vraie notification sur un vrai iPhone depuis Cloudflare (vérifiée seulement avec un faux service de notification).

## Prochaines étapes
1. Zoé et Noé passent sur la nouvelle adresse et confirment.
2. Avec l'accord de Noé : arrêter le service Render « BonneJournée » et son disque, puis fusionner `cloudflare` dans `main` et retirer `backend/`, `server.py`, `Procfile`, `requirements.txt`.

## Pièges
- `wrangler pages deploy` sans `--branch main` publie une préversion (nom de la branche Git), pas la production.
- Le tout premier appel après un déploiement peut répondre 522 ; les suivants passent.
- Python de python.org sans certificats racine : `certifi` ou `curl` pour appeler l'app en HTTPS depuis un script.
- Ne pas lancer `tests/test_ui_evenements.py` contre la production : il bascule la dispo du jour.
