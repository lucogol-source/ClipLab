"""YouTube OAuth and uploads. Credentials stay on this computer."""
from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from engine import DATA, check_cancel, project_dir, read_project, update_clip

SECRET_DIR = DATA / "secrets"
SECRET_DIR.mkdir(mode=0o700, exist_ok=True)
SECRET_DIR.chmod(0o700)
CLIENT = SECRET_DIR / "google-client.json"
TOKEN = SECRET_DIR / "youtube-token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
PENDING = {}
AUTH_LOCK = threading.RLock()


def save_secret(path: Path, value):
    temp = path.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8", opener=lambda p, flags: __import__("os").open(p, flags, 0o600)) as f:
        f.write(value if isinstance(value, str) else json.dumps(value))
    temp.chmod(0o600)
    temp.replace(path)


def configure(value: dict):
    cfg = value.get("installed", {})
    if not cfg.get("client_id", "").endswith(".apps.googleusercontent.com") or not cfg.get("client_secret"):
        raise ValueError("Carica il JSON OAuth di tipo App desktop scaricato da Google Cloud.")
    # Do not accept configurable token endpoints (avoid sending credentials elsewhere).
    clean = {"installed": {"client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
                           "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                           "token_uri": "https://oauth2.googleapis.com/token",
                           "redirect_uris": ["http://localhost"]}}
    with AUTH_LOCK:
        save_secret(CLIENT, clean)
        TOKEN.unlink(missing_ok=True)
        PENDING.clear()


def auth_url(base: str) -> str:
    if not CLIENT.exists():
        raise ValueError("Prima carica il file JSON OAuth nelle impostazioni.")
    flow = Flow.from_client_config(json.loads(CLIENT.read_text(encoding='utf-8')), scopes=SCOPES, autogenerate_code_verifier=True)
    flow.redirect_uri = base + "/api/youtube/callback"
    url, state = flow.authorization_url(access_type="offline", prompt="consent select_account", include_granted_scopes="true")
    with AUTH_LOCK:
        PENDING.clear()
        PENDING[state] = {"flow": flow, "created": time.time()}
    return url


def finish_auth(state: str, code: str):
    with AUTH_LOCK:
        pending = PENDING.pop(state, None)
    if not pending or time.time() - pending["created"] > 600:
        raise ValueError("Collegamento scaduto. Avvia di nuovo la connessione dall’app.")
    flow = pending["flow"]
    flow.fetch_token(code=code)
    credentials = flow.credentials
    service = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    items = service.channels().list(part="snippet", mine=True).execute().get("items", [])
    if len(items) != 1:
        raise ValueError("Seleziona un account con un singolo canale attivo nel consenso Google. Per un Brand Account scegli il relativo canale.")
    channel = {"id": items[0]["id"], "title": items[0]["snippet"]["title"]}
    save_secret(TOKEN, {"credentials": json.loads(credentials.to_json()), "channel": channel})
    return channel


def connection():
    if not TOKEN.exists():
        return {"configured": CLIENT.exists(), "connected": False}
    saved = json.loads(TOKEN.read_text(encoding='utf-8'))
    return {"configured": CLIENT.exists(), "connected": True, "channel": saved["channel"]}


def disconnect():
    # Forget local access. Google account settings also allow revoking the grant.
    with AUTH_LOCK:
        TOKEN.unlink(missing_ok=True)
        PENDING.clear()


def client_for_channel(channel_id):
    with AUTH_LOCK:
        if not TOKEN.exists():
            raise ValueError("Collega prima il canale YouTube nelle impostazioni.")
        saved = json.loads(TOKEN.read_text(encoding='utf-8'))
        if saved["channel"]["id"] != channel_id:
            raise ValueError("Il canale collegato è cambiato: seleziona nuovamente la destinazione.")
        creds = Credentials.from_authorized_user_info(saved["credentials"], SCOPES)
        if not creds.valid:
            if not creds.refresh_token:
                raise ValueError("Ricollega il canale YouTube: autorizzazione scaduta.")
            creds.refresh(Request())
            save_secret(TOKEN, {"credentials": json.loads(creds.to_json()), "channel": saved["channel"]})
        service = build("youtube", "v3", credentials=creds, cache_discovery=False)
        items = service.channels().list(part="id", mine=True).execute().get("items", [])
        if len(items) != 1 or items[0]["id"] != channel_id:
            raise ValueError("Il canale autorizzato non corrisponde alla destinazione. Ricollegalo.")
        return service


def upload_clip(pid, cid, channel_id, privacy, made_for_kids, title, description, export_id=None):
    if privacy not in ("private", "unlisted", "public"):
        raise ValueError("Visibilità non valida")
    p = read_project(pid)
    clip = next(c for c in p["clips"] if c["id"] == cid)
    if clip.get("youtube"):
        update_clip(pid,cid,status='published',error=None)
        return clip["youtube"]  # idempotent: one upload per clip
    if clip.get("upload_uncertain"):
        raise ValueError("Esito del precedente upload incerto. Verifica YouTube Studio prima di riprovare.")
    if not clip["exports"]:
        raise ValueError("Esporta prima la clip in MP4.")
    selected=next((e for e in clip["exports"] if e["id"]==export_id),None) if export_id else clip["exports"][-1]
    if selected is None:raise ValueError("L’esportazione programmata non è più disponibile.")
    title = title.strip().replace("<", "").replace(">", "")[:100]
    if not title:
        raise ValueError("Inserisci un titolo.")
    check_cancel(pid)
    service = client_for_channel(channel_id)
    upload = service.videos().insert(
        part="snippet,status",
        body={"snippet": {"title": title, "description": description[:5000], "categoryId": "22", "tags": ["Shorts"]},
              "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": bool(made_for_kids)}},
        media_body=MediaFileUpload(str(project_dir(pid) / selected["file"]),
                                   mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True))
    update_clip(pid, cid, status="uploading", upload_progress=0, error=None)
    attempted = False
    try:
        response = None
        while response is None:
            check_cancel(pid)
            attempted = True
            status, response = upload.next_chunk(num_retries=3)
            if status:
                update_clip(pid, cid, upload_progress=round(status.progress() * 100))
        result = {"id": response["id"], "url": "https://www.youtube.com/watch?v=" + response["id"],
                  "privacy": response.get("status", {}).get("privacyStatus", privacy), "channel_id": channel_id}
        update_clip(pid, cid, youtube=result, status="published", upload_progress=100, error=None)
        return result
    except Exception as e:
        # A lost final response can hide a successful upload. Never retry blindly.
        known_rejection = isinstance(e, HttpError) and 400 <= e.resp.status < 500 and e.resp.status != 408
        uncertain = attempted and not known_rejection
        message = ("Upload interrotto; verifica YouTube Studio prima di riprovare. " if uncertain else "Caricamento YouTube non riuscito. ") + str(e)[-800:]
        update_clip(pid, cid, status="error", error=message, upload_uncertain=uncertain)
        raise RuntimeError(message)
