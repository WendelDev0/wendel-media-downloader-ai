from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from main import (
    DOWNLOADS,
    ENV_FILE,
    ROOT,
    SUPPORTED_MEDIA,
    TRANSCRIPTS,
    YOUTUBE_URL,
    download,
    generate_creative_metadata,
    get_openai_client,
    transcribe,
)

load_dotenv(ENV_FILE)

STATIC = ROOT / "static"
UPLOADS = ROOT / "uploads"
MAX_UPLOAD_BYTES = 512 * 1024 * 1024
SESSION_COOKIE = "wendel_session"
JOBS_LOCK = threading.Lock()
JOB_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="web-job")


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"
    stage: str = "Na fila"
    percent: float = 0
    error: str | None = None
    results: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


JOBS: dict[str, Job] = {}


def app_password() -> str:
    return os.getenv("APP_PASSWORD", "").strip()


def session_secret() -> bytes:
    secret = os.getenv("APP_SECRET", "").strip() or app_password() or "wendel-dev-local"
    return secret.encode("utf-8")


def sign_session() -> str:
    nonce = secrets.token_hex(8)
    digest = hmac.new(session_secret(), nonce.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{nonce}.{digest}"


def valid_session(token: str | None) -> bool:
    if not app_password():
        return True
    if not token or "." not in token:
        return False
    nonce, digest = token.split(".", 1)
    expected = hmac.new(session_secret(), nonce.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


def public_path(path: Path) -> dict:
    resolved = path.resolve()
    rel = resolved.relative_to(ROOT.resolve()).as_posix()
    return {
        "name": path.name,
        "rel": rel,
        "url": f"/api/files/{quote(rel, safe='/')}",
        "folder": path.parent.name,
    }


class WebDashboard:
    def __init__(self, job: Job, sources: list[Path]) -> None:
        self.job = job
        self.lock = threading.Lock()
        self.parts = {str(source): ("Na fila", 0.0, "waiting") for source in sources}

    def update(self, source: Path, stage: str, percent: float, status: str = "running") -> None:
        with self.lock:
            self.parts[str(source)] = (stage, max(0.0, min(100.0, percent)), status)
            values = list(self.parts.values())
            self.job.percent = sum(item[1] for item in values) / max(1, len(values))
            active = next((item[0] for item in values if item[2] == "running"), stage)
            self.job.stage = active
            if status == "error":
                self.job.status = "error"
                self.job.error = stage


def create_job(kind: str) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], kind=kind)
    with JOBS_LOCK:
        JOBS[job.id] = job
    return job


def get_job(job_id: str) -> Job:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")
    return job


def job_payload(job: Job) -> dict:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "stage": job.stage,
        "percent": round(job.percent, 1),
        "error": job.error,
        "results": job.results,
    }


def download_hook(job: Job):
    def hook(data: dict) -> None:
        if data.get("status") == "downloading":
            downloaded = data.get("downloaded_bytes", 0)
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            job.status = "running"
            job.stage = "Baixando do YouTube"
            job.percent = (downloaded / total * 70) if total else min(60.0, job.percent + 0.4)
        elif data.get("status") == "finished":
            job.stage = "Processando arquivo"
            job.percent = max(job.percent, 75)

    return hook


def save_uploads(files: list[UploadFile], allowed: set[str]) -> list[Path]:
    UPLOADS.mkdir(exist_ok=True)
    saved: list[Path] = []
    for upload in files:
        if not upload.filename:
            continue
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in allowed:
            raise HTTPException(400, f"Formato não suportado: {upload.filename}")
        target = UPLOADS / f"{uuid.uuid4().hex[:8]}-{Path(upload.filename).name}"
        size = 0
        with target.open("wb") as handle:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    handle.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, "Arquivo maior que 512 MB.")
                handle.write(chunk)
        saved.append(target)
    if not saved:
        raise HTTPException(400, "Nenhum arquivo válido foi enviado.")
    return saved


def finish_ok(job: Job, results: list[Path]) -> None:
    job.results = [public_path(path) for path in results]
    job.percent = 100
    job.stage = "Concluído"
    job.status = "done"


def finish_error(job: Job, exc: Exception) -> None:
    job.status = "error"
    job.error = str(exc)
    job.stage = "Falhou"
    job.percent = 100


def run_download_job(job: Job, url: str, media_format: str, also_transcribe: bool, translate: bool) -> None:
    try:
        job.status = "running"
        media = download(url, media_format, on_progress=download_hook(job))
        results = [media]
        if also_transcribe:
            job.stage = "Preparando transcrição"
            job.percent = 78
            dashboard = WebDashboard(job, [media])
            txt, srt = transcribe(media, translate, get_openai_client(interactive=False), dashboard)
            results.extend([txt, srt])
        finish_ok(job, results)
    except Exception as exc:
        finish_error(job, exc)


def run_transcribe_job(job: Job, sources: list[Path], translate: bool, workers: int) -> None:
    try:
        job.status = "running"
        client = get_openai_client(interactive=False)
        dashboard = WebDashboard(job, sources)
        completed: list[Path] = []
        failed: list[str] = []
        with ThreadPoolExecutor(max_workers=max(1, min(workers, 4)), thread_name_prefix="web-tr") as pool:
            futures = {
                pool.submit(transcribe, source, translate, client, dashboard): source
                for source in sources
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    txt, srt = future.result()
                    completed.extend([txt, srt])
                except Exception as exc:
                    failed.append(f"{source.name}: {exc}")
                    dashboard.update(source, str(exc)[:80], 100, "error")
        if not completed:
            raise RuntimeError("; ".join(failed) or "Nenhuma transcrição concluída.")
        finish_ok(job, completed)
        if failed:
            job.stage = f"Concluído com {len(failed)} falha(s)"
    except Exception as exc:
        finish_error(job, exc)


def run_metadata_job(job: Job, transcript: Path) -> None:
    try:
        job.status = "running"
        job.stage = "Gerando título e descrição"
        job.percent = 20
        output = generate_creative_metadata(get_openai_client(interactive=False), transcript)
        finish_ok(job, [output])
    except Exception as exc:
        finish_error(job, exc)


def submit(job: Job, fn, *args) -> Job:
    JOB_EXECUTOR.submit(fn, job, *args)
    return job


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


app = FastAPI(title="Wendel Dev")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def protect(request: Request, call_next):
    path = request.url.path
    open_paths = {"/health", "/login", "/api/login", "/api/status"}
    if path.startswith("/static/") or path in open_paths:
        return await call_next(request)
    if valid_session(request.cookies.get(SESSION_COOKIE)):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Faça login para usar o painel."}, status_code=401)
    return RedirectResponse("/login", status_code=302)


@app.get("/health")
def health():
    return {"ok": True, "service": "wendel-dev"}


@app.get("/api/status")
def status(request: Request):
    load_dotenv(ENV_FILE)
    return {
        "authRequired": bool(app_password()),
        "authenticated": valid_session(request.cookies.get(SESSION_COOKIE)),
        "hasOpenAI": bool(os.getenv("OPENAI_API_KEY", "").strip()),
    }


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    password = str(body.get("password", "")).strip()
    expected = app_password()
    if not expected or not hmac.compare_digest(password, expected):
        raise HTTPException(401, "Senha inválida.")
    response = JSONResponse({"ok": True})
    response.set_cookie(SESSION_COOKIE, sign_session(), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 14)
    return response


@app.post("/api/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.post("/api/download")
def api_download(
    url: str = Form(...),
    media_format: str = Form("mp4"),
    transcribe_after: str = Form("false"),
    translate: str = Form("true"),
):
    if not YOUTUBE_URL.match(url.strip()):
        raise HTTPException(400, "Cole uma URL válida do YouTube.")
    if media_format not in {"mp4", "mp3"}:
        raise HTTPException(400, "Formato inválido.")
    also_transcribe = parse_bool(transcribe_after)
    kind = "download-transcribe" if also_transcribe else "download"
    job = create_job(kind)
    submit(job, run_download_job, url.strip(), media_format, also_transcribe, parse_bool(translate, True))
    return job_payload(job)


@app.post("/api/transcribe")
async def api_transcribe(
    translate: str = Form("true"),
    workers: int = Form(2),
    files: list[UploadFile] = File(...),
):
    sources = save_uploads(files, SUPPORTED_MEDIA)
    job = create_job("transcribe")
    submit(job, run_transcribe_job, sources, parse_bool(translate, True), max(1, min(workers, 4)))
    return job_payload(job)


@app.post("/api/metadata")
async def api_metadata(files: list[UploadFile] = File(...)):
    sources = save_uploads(files, {".txt"})
    job = create_job("metadata")
    submit(job, run_metadata_job, sources[0])
    return job_payload(job)


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    return job_payload(get_job(job_id))


@app.get("/api/files/{rel:path}")
def api_file(rel: str):
    path = (ROOT / rel).resolve()
    allowed = (DOWNLOADS.resolve(), TRANSCRIPTS.resolve(), UPLOADS.resolve())
    if not any(path == folder or folder in path.parents for folder in allowed):
        raise HTTPException(403, "Caminho não permitido.")
    if not path.is_file():
        raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(path, filename=path.name)
