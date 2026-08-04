# Bonne journée

App privée pour Zoé (Z) et Noé (N) : journal de bonnes/mauvaises journées + calendrier des disponibilités. Installable comme une PWA sur iPhone (Ajouter à l'écran d'accueil) et sur Windows (bouton "Installer" de Chrome/Edge), avec notifications push.

## Lancer en local

```
pip install -r requirements.txt
python server.py
```

Puis ouvrir `http://localhost:3000`.

Variables d'environnement :
- `DATABASE_URL` — connection string Postgres (Neon). Si définie, remplace SQLite (voir section Neon plus bas).
- `DB` — chemin du fichier SQLite, utilisé seulement si `DATABASE_URL` n'est pas définie (par défaut `/data/counters.db`)
- `PORT` — port HTTP (par défaut `3000`)
- `VAPID_SUBJECT` — contact utilisé pour les notifications push (par défaut `mailto:noedrionduchapois@gmail.com`)

## Structure du projet

```
server.py             point d'entrée (démarre le serveur HTTP)
backend/
  constants.py         clés/tables partagées entre les deux backends de données
  db.py                aiguilleur : Postgres si DATABASE_URL est définie, sinon SQLite
  db_sqlite.py          implémentation SQLite (dev local)
  db_postgres.py        implémentation Postgres/Neon (prod)
  push.py               clés VAPID + envoi des notifications web push
  handlers.py           routes de l'API + service des fichiers statiques
public/                tout ce qui est servi au navigateur
  index.html
  css/style.css
  js/app.js
  manifest.webmanifest  métadonnées de l'app installable
  sw.js                 service worker (mode hors-ligne + réception des notifications)
  icons/                icônes de l'app (régénérables via scripts/generate_icons.py)
scripts/
  generate_icons.py             régénère les PNG dans public/icons/ (à lancer manuellement si besoin)
  neon_get_connection_string.py aide à récupérer le DATABASE_URL depuis une clé API Neon
  migrate_sqlite_to_neon.py     copie les données existantes (Render/SQLite) vers Neon
requirements.txt
Procfile               commande de démarrage pour l'hébergeur (web: python server.py)
```

## Migration vers Neon (Postgres)

⚠️ **La clé qui commence par `napi_...`** que tu as mise dans les variables d'environnement de Render est une **clé API Neon** (elle sert à gérer Neon lui-même : créer/lister des projets, des branches...). Ce n'est **pas** ce dont l'app a besoin pour se connecter à la base — il lui faut la **connection string Postgres** (elle commence par `postgresql://`).

### 1. Récupérer la connection string

Deux façons :

- **Manuellement** : Neon Console → ton projet → bouton "Connect" → choisis "Pooled connection" → copie l'URL (elle contient déjà `?sslmode=require`).
- **Avec le script** (utilise ta clé `napi_...` en local, jamais collée ailleurs) :
  ```
  NEON_API_KEY=napi_xxx python scripts/neon_get_connection_string.py
  ```

### 2. Configurer Render

Dans les variables d'environnement de Render, **renomme/ajoute** une variable nommée exactement `DATABASE_URL` avec cette connection string comme valeur (garde aussi `napi_...` si tu veux t'en resservir plus tard, mais l'app ne s'en sert pas). Ne redéploie pas encore.

### 3. Migrer les données existantes (⚠️ à ne pas oublier)

Les données actuelles vivent dans le fichier SQLite sur le disque persistant de Render. Avant — ou juste après — d'activer `DATABASE_URL`, lance depuis le **Shell de Render** (onglet "Shell" du service, qui a accès au disque ET, une fois la variable ajoutée, à Neon) :

```
python scripts/migrate_sqlite_to_neon.py --dry-run
```

Vérifie que les compteurs affichés correspondent à ce que vous avez dans l'app, puis lance pour de vrai :

```
python scripts/migrate_sqlite_to_neon.py --yes
```

Le script lit `DB` (chemin SQLite) et `DATABASE_URL` (Neon) depuis les variables d'environnement déjà présentes sur Render — pas besoin de les repasser en argument. Il est prévu pour ne tourner qu'une fois ; le relancer plus tard écraserait les compteurs/thème avec l'ancien instantané SQLite (voir l'avertissement en tête du script).

### 4. Redéployer

Une fois la migration confirmée, redéploie le service. Le prochain démarrage détecte `DATABASE_URL`, bascule automatiquement sur Postgres (le log de démarrage affichera `DB backend: postgres`), et les tables sont créées si besoin (les données migrées à l'étape 3 sont déjà là).

## Notifications push

Au premier démarrage, une paire de clés VAPID est générée et sauvegardée à côté de la base de données (`vapid_private_key.pem`, sur le même volume persistant que `DB`) — elle ne doit **jamais** être commitée ni régénérée en prod, sinon tous les abonnements existants deviennent invalides.

Déclencheur actuel : quand Zoé ou Noé ajoute une bonne ou une mauvaise journée dans le Journal, l'autre reçoit une notification (si il/elle a activé le bouton "Activer les notifications" dans l'app). Chacun peut désactiver ses propres notifications à tout moment via ce même bouton.

Ça nécessite HTTPS en production (le navigateur bloque les notifications push en HTTP simple, `localhost` excepté).

## Ajouter une fonctionnalité

- Nouvelle route API → `backend/handlers.py` (+ logique de données dans `backend/db.py` si besoin d'une nouvelle table)
- Nouvel élément d'interface → `public/index.html` + `public/css/style.css` + `public/js/app.js`
- Si un nouveau fichier statique est ajouté (image, police...), penser à l'ajouter à `APP_SHELL` dans `public/sw.js` pour qu'il soit mis en cache hors-ligne.
