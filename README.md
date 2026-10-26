# Youtube Downloader Pro

Téléchargeur de vidéos en ligne (YouTube, TikTok, Facebook, Instagram, X, Vimeo…) basé sur yt-dlp + ffmpeg.
L'utilisateur colle un lien, choisit MP4 ou MP3, et télécharge.

## Architecture

- `backend/main.py` : API FastAPI (`/api/info`, `/api/download`, `/api/jobs/{id}`, `/api/file/{id}`)
- `frontend/` : page web statique servie par le backend
- Firebase Firestore (optionnel) : collection `downloads` (domaine, format, statut, IP hachée)
- Docker + Caddy : déploiement avec HTTPS automatique sur votre nom de domaine

> Firebase Hosting / Cloud Functions ne peuvent pas exécuter ffmpeg + yt-dlp de façon fiable :
> le backend doit tourner sur un VPS (Hetzner, OVH, DigitalOcean…).

## Lancer en local

```bash
cd backend
pip install -r requirements.txt   # ffmpeg doit être installé
uvicorn main:app --reload
```

Ouvrir http://localhost:8000

## Déployer sur un VPS

1. Faire pointer le DNS de votre domaine (enregistrement A) vers l'IP du VPS.
2. `cp .env.example .env` et renseigner `DOMAIN`.
3. Firebase : créer un projet, activer Firestore, générer une clé de compte de service
   et la placer dans `secrets/firebase.json`. Sans ce fichier, l'app fonctionne sans historique.
4. `docker compose up -d --build`

## Maintenance

yt-dlp doit être mis à jour régulièrement (les sites changent souvent) :
`docker compose build --no-cache app && docker compose up -d`

## Sécurité / limites

- Seuls les domaines de `ALLOWED_DOMAINS` sont acceptés (évite l'abus du serveur comme proxy).
- Limitation de débit par IP, durée maximale, suppression des fichiers après `FILE_TTL_SECONDS`.
- Respectez les conditions d'utilisation des plateformes et le droit d'auteur.
