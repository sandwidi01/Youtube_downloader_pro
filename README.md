# Youtube Downloader Pro

Application web qui permet de télécharger une vidéo (MP4) ou son audio (MP3) à partir d'un simple lien.
Elle s'appuie sur **yt-dlp** et **ffmpeg**, derrière une API **FastAPI** et une interface web légère.

> **Projet à but pédagogique.** Il sert à démontrer une architecture web complète (API, tâches en arrière-plan,
> sécurité, déploiement). Utilisez-le uniquement pour des contenus dont vous détenez les droits ou dont l'auteur
> autorise le téléchargement, et respectez les conditions d'utilisation des plateformes.

## Fonctionnalités

- Collage d'un lien, aperçu de la vidéo (miniature, titre, auteur) et choix de la qualité disponible
- Export **MP4** (qualité choisie) ou **MP3** (192 kbps)
- Téléchargement en tâche de fond avec **barre de progression** en temps réel
- Sites pris en charge : YouTube, TikTok, Facebook, Instagram, X, Vimeo, Dailymotion, Twitch, Reddit (liste configurable)
- Journal des téléchargements dans **Firebase Firestore** (optionnel, IP hachée)
- Déploiement prêt à l'emploi avec **Docker** et **HTTPS automatique** (Caddy)

## Architecture

```
Navigateur ──► Caddy (HTTPS, nom de domaine) ──► FastAPI ──► yt-dlp + ffmpeg
                                                    │
                                                    └──► Firebase Firestore (historique, optionnel)
```

| Élément | Rôle |
|---|---|
| `backend/main.py` | API FastAPI : analyse du lien, création des tâches, suivi, envoi du fichier |
| `frontend/` | Page HTML/CSS/JS sans framework, servie par le backend |
| `Dockerfile`, `docker-compose.yml` | Image avec ffmpeg et Node, orchestration avec Caddy |
| `Caddyfile` | Reverse proxy et certificat HTTPS automatique |

### API

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/info` | Métadonnées de la vidéo et qualités disponibles |
| `POST` | `/api/download` | Lance un téléchargement, renvoie un `job_id` |
| `GET` | `/api/jobs/{id}` | Statut et progression de la tâche |
| `GET` | `/api/file/{id}` | Récupération du fichier final |
| `GET` | `/api/health` | Vérification de l'état du service |

## Sécurité et limites

- **Liste blanche de domaines** (`ALLOWED_DOMAINS`) : empêche d'utiliser le serveur comme proxy ouvert
- Extracteur générique de yt-dlp désactivé
- **Limitation de débit** par IP (`RATE_LIMIT_PER_MIN`)
- Durée maximale des vidéos (`MAX_DURATION_SECONDS`) et nettoyage automatique des fichiers (`FILE_TTL_SECONDS`)
- Aucune adresse IP stockée en clair : seul un hash tronqué est enregistré

## Installation en local

Prérequis : Python 3.11+, ffmpeg, Node.js (requis par yt-dlp pour YouTube).

```bash
git clone https://github.com/sandwidi01/Youtube_downloader_pro.git
cd Youtube_downloader_pro/backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Puis ouvrir http://localhost:8000.

## Déploiement

L'application doit tourner sur un **serveur (VPS)** : Firebase Hosting et Cloud Functions ne permettent pas
d'exécuter ffmpeg et yt-dlp de façon fiable. Firebase ne sert ici qu'à la base de données.

1. Faire pointer l'enregistrement DNS (type A) de votre domaine vers l'IP du serveur.
2. `cp .env.example .env` puis renseigner `DOMAIN`.
3. *(Optionnel)* Créer un projet Firebase, activer Firestore et placer la clé de compte de service
   dans `secrets/firebase.json`.
4. `docker compose up -d --build`

### Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `DOMAIN` | — | Nom de domaine servi par Caddy |
| `ALLOWED_DOMAINS` | liste de sites | Sites acceptés |
| `RATE_LIMIT_PER_MIN` | `6` | Requêtes par minute et par IP |
| `MAX_DURATION_SECONDS` | `7200` | Durée maximale d'une vidéo |
| `FILE_TTL_SECONDS` | `3600` | Durée de conservation des fichiers |
| `FIREBASE_CREDENTIALS` | — | Chemin de la clé Firebase |

## Maintenance

Les plateformes changent souvent : mettez yt-dlp à jour régulièrement.

```bash
docker compose build --no-cache app && docker compose up -d
```

## Pistes d'évolution

- Comptes utilisateurs (Firebase Auth) et quotas hebdomadaires par compte
- Limitation de qualité selon l'offre
- Paiement par mobile money pour une offre premium

## Technologies

Python · FastAPI · yt-dlp · ffmpeg · JavaScript · Firebase Firestore · Docker · Caddy

## Licence

Aucune licence n'est définie pour le moment : tous droits réservés par défaut.
