import hashlib
import os
import shutil
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "/tmp/downloads"))
FILE_TTL = int(os.getenv("FILE_TTL_SECONDS", "3600"))
MAX_DURATION = int(os.getenv("MAX_DURATION_SECONDS", "7200"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "6"))
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", Path(__file__).parent.parent / "frontend"))
ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in os.getenv(
        "ALLOWED_DOMAINS",
        "youtube.com,youtu.be,tiktok.com,facebook.com,fb.watch,instagram.com,"
        "twitter.com,x.com,vimeo.com,dailymotion.com,twitch.tv,reddit.com",
    ).split(",")
    if d.strip()
]

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Youtube Downloader Pro")

# --- Firestore (optionnel) -------------------------------------------------
_db = None
_cred = os.getenv("FIREBASE_CREDENTIALS")
if _cred and Path(_cred).exists():
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        firebase_admin.initialize_app(credentials.Certificate(_cred))
        _db = firestore.client()
    except Exception as exc:  # le site doit marcher même sans Firebase
        print(f"[firebase] désactivé: {exc}")


def log_download(job: dict, ip: str) -> None:
    if _db is None:
        return
    try:
        _db.collection("downloads").add(
            {
                "domain": job["domain"],
                "title": job.get("title"),
                "format": job["format"],
                "quality": job["quality"],
                "status": job["status"],
                "ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:16],
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )
    except Exception as exc:
        print(f"[firebase] log échoué: {exc}")


# --- Utilitaires -----------------------------------------------------------
_hits: dict[str, deque] = defaultdict(deque)


def check_rate_limit(ip: str) -> None:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Trop de requêtes, réessayez dans une minute.")
    q.append(now)


def validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host:
        raise HTTPException(400, "Lien invalide.")
    if not any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS):
        raise HTTPException(400, "Ce site n'est pas pris en charge.")
    return url.strip()


BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "allowed_extractors": ["default", "-generic"],
    "socket_timeout": 20,
    "js_runtimes": {"node": {}},  # requis par YouTube
}
if os.getenv("FFMPEG_LOCATION"):
    BASE_OPTS["ffmpeg_location"] = os.environ["FFMPEG_LOCATION"]

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


class UrlIn(BaseModel):
    url: str


class DownloadIn(BaseModel):
    url: str
    format: str = "mp4"  # mp4 | mp3
    quality: int = 720  # hauteur max pour mp4


# --- API -------------------------------------------------------------------
@app.post("/api/info")
def info(body: UrlIn, request: Request):
    check_rate_limit(request.client.host)
    url = validate_url(body.url)
    try:
        with yt_dlp.YoutubeDL({**BASE_OPTS, "skip_download": True}) as ydl:
            data = ydl.extract_info(url, download=False)
    except Exception:
        raise HTTPException(422, "Impossible de lire cette vidéo.")
    if (data.get("duration") or 0) > MAX_DURATION:
        raise HTTPException(413, "Vidéo trop longue.")
    heights = sorted({f["height"] for f in data.get("formats", []) if f.get("height")})
    return {
        "title": data.get("title"),
        "thumbnail": data.get("thumbnail"),
        "duration": data.get("duration"),
        "uploader": data.get("uploader"),
        "heights": heights,
    }


def run_job(job_id: str, ip: str) -> None:
    job = jobs[job_id]
    job_dir = DOWNLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                job["progress"] = round(d["downloaded_bytes"] / total * 100, 1)
        elif d["status"] == "finished":
            job["progress"] = 99.0

    opts = {
        **BASE_OPTS,
        "outtmpl": str(job_dir / "%(title).80s.%(ext)s"),
        "progress_hooks": [hook],
        "restrictfilenames": True,
    }
    if job["format"] == "mp3":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    else:
        h = job["quality"]
        opts["format"] = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
        opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(job["url"], download=True)
        job["title"] = data.get("title")
        files = [p for p in job_dir.iterdir() if p.is_file()]
        if not files:
            raise RuntimeError("aucun fichier")
        job["file"] = str(files[0])
        job["filename"] = files[0].name
        job["progress"] = 100.0
        job["status"] = "done"
    except Exception:
        job["status"] = "error"
        job["error"] = "Le téléchargement a échoué."
    finally:
        log_download(job, ip)


@app.post("/api/download")
def download(body: DownloadIn, request: Request):
    ip = request.client.host
    check_rate_limit(ip)
    url = validate_url(body.url)
    if body.format not in ("mp4", "mp3"):
        raise HTTPException(400, "Format invalide.")
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {
            "url": url,
            "domain": urlparse(url).hostname,
            "format": body.format,
            "quality": max(144, min(body.quality, 2160)),
            "status": "running",
            "progress": 0.0,
            "created": time.time(),
        }
    threading.Thread(target=run_job, args=(job_id, ip), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Tâche introuvable.")
    return {k: job.get(k) for k in ("status", "progress", "title", "filename", "error")}


@app.get("/api/file/{job_id}")
def get_file(job_id: str):
    job = jobs.get(job_id)
    if not job or job["status"] != "done" or not Path(job["file"]).exists():
        raise HTTPException(404, "Fichier indisponible.")
    return FileResponse(job["file"], filename=job["filename"])


@app.get("/api/health")
def health():
    return {"ok": True, "firebase": _db is not None}


# --- Nettoyage des fichiers expirés ------------------------------------------
def cleaner() -> None:
    while True:
        time.sleep(300)
        now = time.time()
        with jobs_lock:
            for jid in [j for j, v in jobs.items() if now - v["created"] > FILE_TTL]:
                shutil.rmtree(DOWNLOAD_DIR / jid, ignore_errors=True)
                del jobs[jid]


threading.Thread(target=cleaner, daemon=True).start()

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
