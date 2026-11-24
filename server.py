from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

import engine
import youtube
import captions
import publishing
import promotion
import bundles
import suggestions
import tiktok
from version import VERSION
from filelock import FileLock, Timeout
from platform_support import is_windows

POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cliplab")
BUSY = engine.BUSY
BUSY_LOCK = engine.BUSY_LOCK
MAX_UPLOAD = 2 * 1024**3


@asynccontextmanager
async def lifespan(app):
    instance_lock=FileLock(str(engine.DATA/'engine.lock'))
    try:
        instance_lock.acquire(timeout=0)
    except Timeout:
        raise RuntimeError('Un altro motore ClipLab sta già usando questa cartella.')
    try:
        for path in engine.PROJECTS.glob('*/project.json'):
            p=json.loads(path.read_text(encoding='utf-8'))
            changed=False
            if p['status'] in ('queued','processing','uploading') and os.environ.get('CLIPLAB_LEGACY_ACTIVE')!='1':
                p.update(status='error',stage='Interrotto dal riavvio',error='L’app è stata chiusa durante l’elaborazione. Reimporta il video per ripartire.')
                changed=True
            for clip in p.get('clips',[]):
                if clip['status'] in ('queued','rendering','uploading','tracking','transcribing') and os.environ.get('CLIPLAB_LEGACY_ACTIVE')!='1':
                    clip.update(upload_uncertain=clip['status']=='uploading',status='error',error='Operazione interrotta dal riavvio. Se era un upload, verifica la piattaforma.')
                    changed=True
            if changed:engine.write_project(p)
        publishing.start()
        suggestions.start()
        try:
            yield
        finally:
            for event in list(engine.EVENTS.values()):event.set()
            suggestions.stop()
            publishing.stop()
            POOL.shutdown(wait=False,cancel_futures=True)
    finally:
        instance_lock.release()


app = FastAPI(title="ClipLab locale", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])


@app.middleware("http")
async def local_only(request: Request, call_next):
    origin = request.headers.get("origin")
    allowed = {f"http://127.0.0.1:{os.environ.get('CLIPLAB_PORT', '8765')}", f"http://localhost:{os.environ.get('CLIPLAB_PORT', '8765')}"}
    if request.method not in ("GET", "HEAD", "OPTIONS") and (origin and origin not in allowed or request.headers.get("sec-fetch-site") == "cross-site"):
        return JSONResponse({"detail": "Accesso consentito solo dall’app locale."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(engine.ClipBusy)
async def busy(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(FileNotFoundError)
async def missing(request, exc):
    return JSONResponse({"detail": "File o progetto non trovato."}, status_code=404)


class Options(BaseModel):
    mode: Literal["highlights", "full"] = "highlights"
    duration: Literal[30, 45, 60, 90, 120, 180] = 45
    count: int = Field(4, ge=1, le=8)
    format: Literal["9:16", "1:1", "16:9"] = "9:16"
    captions: Literal["karaoke", "clean", "none"] = "karaoke"
    language: Literal["auto", "it", "en", "es", "fr", "de"] = "auto"
    model: Literal["tiny", "base", "small"] = "small"
    glossary: str = Field("",max_length=1500)
    auto_publish: bool = False
    channel_id: str = ""
    privacy: Literal["private", "unlisted", "public"] = "private"
    made_for_kids: bool = False


class ImportBody(Options):
    url: str


class Keyframe(BaseModel):
    t: float = Field(ge=0,le=180,allow_inf_nan=False)
    x: float = Field(50,ge=0,le=100,allow_inf_nan=False)
    y: float = Field(50,ge=0,le=100,allow_inf_nan=False)
    zoom: float = Field(1,ge=1,le=3,allow_inf_nan=False)
    cut: bool = False


class ExportBody(BaseModel):
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    title: str = Field(min_length=1, max_length=100)
    format: Literal["9:16", "1:1", "16:9"] = "9:16"
    captions: Literal["karaoke", "clean", "none"] = "karaoke"
    crop: float = Field(50, ge=0, le=100, allow_inf_nan=False)
    crop_y: float = Field(50,ge=0,le=100,allow_inf_nan=False)
    zoom: float = Field(1,ge=1,le=3,allow_inf_nan=False)
    layout: Literal["crop","fit","blur","split"] = "blur"
    quality: Literal[720,1080] = 1080
    split_left: float = Field(20,ge=0,le=100,allow_inf_nan=False)
    split_right: float = Field(80,ge=0,le=100,allow_inf_nan=False)
    keyframes: list[Keyframe] = Field(default_factory=list,max_length=500)
    font_scale: float = Field(1,ge=.65,le=1.5,allow_inf_nan=False)
    caption_bottom: float = Field(22,ge=8,le=65,allow_inf_nan=False)
    caption_color: str = Field("#d3ff5f",pattern=r"^#[0-9a-fA-F]{6}$")
    caption_words: int = Field(5,ge=2,le=8)


class CaptionBody(BaseModel):
    cues: list[dict] = Field(max_length=1500)
    start: float | None = Field(None,ge=0,allow_inf_nan=False)
    end: float | None = Field(None,gt=0,allow_inf_nan=False)


class TranscribeBody(BaseModel):
    model: Literal["base","small"] = "small"
    glossary: str = Field("",max_length=1500)


class TrackBody(BaseModel):
    start: float = Field(ge=0,allow_inf_nan=False)
    end: float = Field(gt=0,allow_inf_nan=False)
    format: Literal["9:16","1:1","16:9"] = "9:16"
    subject: Literal["largest","left","right"] = "largest"


class PublishBody(BaseModel):
    channel_id: str = Field(min_length=1)
    privacy: Literal["private", "unlisted", "public"] = "private"
    made_for_kids: bool = False
    title: str = Field(min_length=1, max_length=100)
    description: str = Field("#Shorts", max_length=5000)


def validate_connection(options):
    if options.auto_publish:
        c = youtube.connection()
        if not c["connected"] or c["channel"]["id"] != options.channel_id:
            raise ValueError("Collega e seleziona il canale YouTube prima di attivare il flusso automatico.")


def task(pid, cid, fn, *args, invalidate=False):
    key = (pid, cid)
    def work():
        try:
            if invalidate:
                publishing.invalidate_clip(pid,cid)
            fn(pid, cid, *args)
        except Exception as e:
            engine.update_clip(pid, cid, status="error", error=str(e)[-1200:])
        finally:
            with BUSY_LOCK:
                latest=next(c for c in engine.read_project(pid)['clips'] if c['id']==cid)
                if latest['status']=='queued':
                    engine.update_clip(pid,cid,status=previous_status)
                engine.release_clip(pid,cid)
    with BUSY_LOCK:
        _,clip=engine.claim_clip(pid,cid)
        previous_status=clip['status']
        try:
            engine.update_clip(pid,cid,status='queued',error=None)
            POOL.submit(work)
        except Exception:
            engine.update_clip(pid,cid,status=previous_status)
            engine.release_clip(pid,cid)
            raise
    return {"queued": True}


@app.get("/api/health")
def health():
    return {"ok": True, "local": True, "paid_services": False, "ffmpeg": bool(engine.FFMPEG),
            "version": VERSION, "application": "cliplab", "app_root": str(engine.ROOT), "data_dir":str(engine.DATA),
            "pid": os.getpid(), "instance_id": os.environ.get("CLIPLAB_INSTANCE", "")}


def request_shutdown():
    app.state.server.should_exit=True


@app.post("/api/shutdown")
def shutdown(request: Request):
    expected = os.environ.get("CLIPLAB_SHUTDOWN_TOKEN", "")
    supplied = request.headers.get("X-ClipLab-Control", "")
    if not expected or not secrets.compare_digest(expected, supplied):
        raise HTTPException(403, "Richiesta di arresto non autorizzata.")
    if not getattr(app.state,'server',None):
        raise HTTPException(503,'Arresto controllato non disponibile in questo avvio.')
    threading.Timer(.3, request_shutdown).start()
    return {"stopping": True}


@app.get("/api/projects")
def projects():
    result = []
    for file in engine.PROJECTS.glob("*/project.json"):
        p = json.loads(file.read_text(encoding='utf-8'))
        result.append({k: p.get(k) for k in ("id", "title", "created", "status", "duration", "progress", "stage")})
    return sorted(result, key=lambda p: p["created"], reverse=True)


@app.get("/api/projects/{pid}")
def project(pid: str):
    return engine.read_project(pid)


@app.post("/api/import/youtube", status_code=202)
def import_youtube(body: ImportBody):
    url = engine.normalize_youtube(body.url)
    validate_connection(body)
    options = body.model_dump(exclude={"url"})
    p = engine.new_project(options)
    engine.update(p["id"], source_url=url)
    POOL.submit(engine.analyze, p["id"], url)
    return p


@app.post("/api/import/file", status_code=202)
async def import_file(file: UploadFile = File(...), options: str = Form("{}")):
    try:
        opts = Options.model_validate_json(options)
    except Exception:
        raise ValueError("Impostazioni del video non valide.")
    validate_connection(opts)
    suffix = __import__("pathlib").Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in (".mp4", ".mov", ".mkv", ".webm", ".m4v"):
        raise ValueError("Usa un file MP4, MOV, MKV, WEBM o M4V.")
    title = __import__("pathlib").Path(file.filename or "Video locale").stem[:150]
    p = engine.new_project(opts.model_dump(), title)
    folder = engine.project_dir(p["id"])
    size = 0
    try:
        with (folder / ("source" + suffix)).open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise ValueError("Il file supera il limite di 2 GB.")
                output.write(chunk)
        if not size:
            raise ValueError("Il file è vuoto.")
        engine.update(p["id"], source_file="source" + suffix)
        POOL.submit(engine.analyze, p["id"])
        return engine.read_project(p["id"])
    except Exception:
        shutil.rmtree(folder)
        raise
    finally:
        await file.close()


@app.post("/api/projects/{pid}/cancel")
def cancel(pid: str):
    engine.cancel_project(pid)
    return {"cancelled": True}


@app.delete("/api/projects/{pid}")
def delete(pid: str):
    p = engine.read_project(pid)
    with BUSY_LOCK:
        if p["status"] in ("queued", "processing") or pid in engine.ANALYZING or any(k[0] == pid for k in BUSY):
            raise HTTPException(409, "Interrompi o attendi l’elaborazione prima di eliminare il progetto.")
        with publishing.database() as c:
            if c.execute("SELECT 1 FROM jobs WHERE pid=? AND status IN ('queued','running','processing')",(pid,)).fetchone():
                raise HTTPException(409,"Annulla prima le pubblicazioni in coda per questo progetto.")
        shutil.rmtree(engine.project_dir(pid))
    return {"deleted": True}


@app.get("/api/projects/{pid}/media/{name}")
def media(pid: str, name: str, download: bool = False):
    folder = engine.project_dir(pid)
    # Only expose media files; never logs, metadata, credentials, symlinks.
    import re
    if not re.fullmatch(r"(?:source\.(?:mp4|mkv|mov|webm|m4v)|poster\.jpg|clip-[a-f0-9]{12}\.(?:mp4|srt))", name):
        raise HTTPException(404)
    path = folder / name
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404)
    mime = "video/mp4" if name.endswith((".mp4", ".m4v")) else "text/plain; charset=utf-8" if name.endswith(".srt") else None
    return FileResponse(path, media_type=mime, filename=name if download else None)


@app.post("/api/projects/{pid}/clips/{cid}/export", status_code=202)
def export(pid: str, cid: str, body: ExportBody):
    p = engine.read_project(pid)
    if body.end > p["duration"] + .01 or not .5 <= body.end - body.start <= 180:
        raise ValueError("Seleziona una clip da 0,5 a 180 secondi entro la durata del video.")
    with BUSY_LOCK:
        draft(pid,cid,body)
        return task(pid, cid, engine.render, body.model_dump())


@app.post("/api/projects/{pid}/clips/{cid}/publish", status_code=202)
def publish(pid: str, cid: str, body: PublishBody):
    with BUSY_LOCK:
        p,clip=editable_clip(pid,cid)
        if clip.get('youtube'):
            raise HTTPException(409,'Questa clip è già stata caricata su YouTube.')
        if not clip["exports"] or clip["exports"][-1].get("edit_revision",0)!=clip.get("edit_revision",0):
            raise ValueError("Riesporta la clip modificata prima di pubblicare.")
        return task(pid, cid, youtube.upload_clip, body.channel_id, body.privacy, body.made_for_kids, body.title, promotion.description(body.description, clip.get("hashtags", [])))


@app.get("/api/youtube")
def youtube_status():
    return youtube.connection()


def editable_clip(pid,cid):
    p=engine.read_project(pid)
    clip=next((c for c in p["clips"] if c["id"]==cid),None)
    if not clip:raise HTTPException(404,"Clip non trovata")
    if p["status"] in ("queued","processing") or pid in engine.ANALYZING or (pid,cid) in BUSY or clip["status"] in ("queued","rendering","uploading","tracking","transcribing"):
        raise HTTPException(409,"Attendi il completamento dell’elaborazione.")
    return p,clip


@app.patch("/api/projects/{pid}/clips/{cid}/draft")
def draft(pid:str,cid:str,body:ExportBody):
    with BUSY_LOCK:
        return save_draft(pid,cid,body)


def save_draft(pid,cid,body):
    p,clip=editable_clip(pid,cid)
    if body.end>p["duration"]+.01 or not .5<=body.end-body.start<=180:
        raise ValueError("Il taglio deve durare da 0,5 a 180 secondi entro il video.")
    settings=body.model_dump()
    settings["keyframes"]=sorted(settings["keyframes"],key=lambda x:x["t"])
    if any(x["t"]>body.end-body.start+.01 for x in settings["keyframes"]):raise ValueError("Un punto di zoom è oltre la fine della clip.")
    if settings!=clip.get("edit"):
        publishing.invalidate_clip(pid,cid)
        engine.update_clip(pid,cid,edit=settings,title=body.title,start=body.start,end=body.end,edit_revision=clip.get("edit_revision",0)+1)
    return {"saved":True}


@app.get("/api/projects/{pid}/clips/{cid}/captions")
def caption_track(pid:str,cid:str):
    p=engine.read_project(pid)
    clip=next((c for c in p["clips"] if c["id"]==cid),None)
    if not clip:raise HTTPException(404)
    return {"cues":captions.track(p,clip,clip["start"],clip["end"]),"revision":clip.get("edit_revision",0),"model":clip.get("asr_model",p["options"].get("model","base"))}


@app.patch("/api/projects/{pid}/clips/{cid}/captions")
def save_caption_track(pid:str,cid:str,body:CaptionBody):
    with BUSY_LOCK:
        return save_captions(pid,cid,body)


def save_captions(pid,cid,body):
    p,clip=editable_clip(pid,cid)
    cues=captions.validate_cues(body.cues,p["duration"])
    start=clip['start'] if body.start is None else body.start
    end=clip['end'] if body.end is None else body.end
    if not 0 <= start < end <= p['duration']+.01:raise ValueError('Intervallo dei sottotitoli non valido.')
    track=captions.store_track(clip,cues,start,end)
    if any(track[k]!=clip.get(k) for k in track):
        publishing.invalidate_clip(pid,cid)
        engine.update_clip(pid,cid,**track,edit_revision=clip.get("edit_revision",0)+1)
    return {"saved":True,"cues":cues}


@app.post("/api/projects/{pid}/clips/{cid}/transcribe",status_code=202)
def transcribe_clip(pid:str,cid:str,body:TranscribeBody):
    return task(pid,cid,engine.retranscribe_clip,body.model,body.glossary,invalidate=True)


@app.post("/api/projects/{pid}/clips/{cid}/track",status_code=202)
def track_clip(pid:str,cid:str,body:TrackBody):
    p,clip=editable_clip(pid,cid)
    if body.end>p["duration"]+.01 or not .5<=body.end-body.start<=180:raise ValueError("Intervallo non valido per il tracking.")
    def track(pid,cid,settings):
        engine.update_clip(pid,cid,status="tracking",error=None)
        import sys,uuid
        config_file=engine.project_dir(pid)/f"track-{uuid.uuid4().hex}.json"
        config_file.write_text(json.dumps(dict(settings,source=str(engine.project_dir(pid)/p["source_file"]),model=str(engine.MODELS/"face_detection_yunet.onnx"))), encoding='utf-8')
        try:
            output=engine.run([sys.executable,engine.ROOT/"framing.py","analyze",config_file],pid,engine.project_dir(pid))
            result=json.loads(output.strip().splitlines()[-1])
        finally:config_file.unlink(missing_ok=True)
        latest=next(c for c in engine.read_project(pid)["clips"] if c["id"]==cid)
        engine.update_clip(pid,cid,tracking=result,status="exported" if latest["exports"] else "suggested")
    return task(pid,cid,track,body.model_dump())


class ScheduleBody(BaseModel):
    pid:str
    clip_ids:list[str]=Field(min_length=1,max_length=40)
    platforms:list[Literal["youtube","tiktok"]]=Field(min_length=1,max_length=2)
    start_at:float=Field(allow_inf_nan=False)
    interval_hours:float=Field(6,ge=.25,le=720,allow_inf_nan=False)
    metadata:dict


class PauseBody(BaseModel):
    paused:bool


@app.get("/api/publishing")
def publishing_queue():return publishing.list_jobs()


@app.post("/api/publishing",status_code=201)
def schedule_publications(body:ScheduleBody):
    return publishing.schedule(body.pid,body.clip_ids,body.platforms,body.start_at,body.interval_hours,body.metadata)


@app.post("/api/publishing/pause")
def pause_publications(body:PauseBody):
    publishing.pause(body.paused)
    return {"paused":body.paused}


@app.delete("/api/publishing/{job_id}")
def cancel_publication(job_id:str):
    publishing.cancel(job_id)
    return {"cancelled":True}


class SuggestionBody(BaseModel):
    id: str = Field(pattern=r"^[0-9a-f]{32}$")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)


@app.get("/api/suggestions")
def suggestion_list():
    items = suggestions.list_items()
    for item in items:
        item["can_resend"] = item["detail"] == suggestions.NO_RECEIPT
    return {"items": items, "via_codex": suggestions.via_codex()}


@app.post("/api/suggestions", status_code=202)
def submit_suggestion(body: SuggestionBody):
    return suggestions.save(body.id, body.title, body.description)


@app.post("/api/suggestions/{key}/retry", status_code=202)
def retry_suggestion(key: str):
    suggestions.retry(key)
    return {"queued": True}


@app.post("/api/suggestions/{key}/resend", status_code=202)
def resend_suggestion(key: str):
    suggestions.resend(key)
    return {"queued": True}


class BundleBody(BaseModel):
    clip_ids: list[str] = Field(min_length=1, max_length=500)


@app.post("/api/projects/{pid}/download/check")
def check_download(pid: str, body: BundleBody):
    with BUSY_LOCK:
        bundles.validate(pid, body.clip_ids)
    return {"ready": True}


@app.get("/api/projects/{pid}/download")
def download_bundle(pid: str, clips: str = Query(min_length=1, max_length=7000)):
    stream = bundles.create(pid, clips.split(","))
    def chunks():
        try:
            while chunk := stream.read(1024 * 1024):
                yield chunk
        finally:
            stream.close()
    return StreamingResponse(chunks(), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="ClipLab-{pid[:8]}.zip"'},
                             background=BackgroundTask(stream.close))


class MetadataBody(BaseModel):
    description: str = Field(max_length=5000)


@app.patch("/api/projects/{pid}/clips/{cid}/metadata")
def save_metadata(pid: str, cid: str, body: MetadataBody):
    with BUSY_LOCK:
        _, clip = editable_clip(pid, cid)
        if clip.get("description") != body.description:
            publishing.invalidate_clip(pid, cid)
            engine.update_clip(pid, cid, description=body.description, hashtags=list(dict.fromkeys(re.findall(r"#[^\W_]+", body.description, re.UNICODE))))
    return {"saved": True}


class PromotionBody(BaseModel):
    replace_title: bool = False


@app.post("/api/projects/{pid}/clips/{cid}/promotion")
def refresh_promotion(pid: str, cid: str, body: PromotionBody):
    p, clip = editable_clip(pid, cid)
    index = next(i for i, c in enumerate(p["clips"]) if c["id"] == cid)
    result = promotion.generate(p, clip, index=index)
    with BUSY_LOCK:
        _, latest = editable_clip(pid, cid)
        if any(latest.get(key) != clip.get(key) for key in ("start", "end", "title", "edit_revision", "description")):
            raise HTTPException(409, "La clip è cambiata. Riaprila e riprova.")
        publishing.invalidate_clip(pid, cid)
        if not body.replace_title:
            result["title"] = latest["title"]
            text = latest.get("description") or latest["title"]
            old_tags = {tag.casefold() for tag in latest.get("hashtags", [])}
            text = re.sub(r"#[^\W_]+", lambda m: "" if m.group().casefold() in old_tags else m.group(), text)
            result["description"] = promotion.description(text.strip(), result["hashtags"])
        elif result["title"] != latest["title"]:
            edit = dict(latest.get("edit") or (latest["exports"][-1]["settings"] if latest["exports"] else {}))
            edit["title"] = result["title"]
            result["edit"] = edit
            result["edit_revision"] = latest.get("edit_revision", 0) + 1
        engine.update_clip(pid, cid, **result)
    return result


class TikTokConfig(BaseModel):
    client_key:str=Field(min_length=1,max_length=200)
    client_secret:str=Field(min_length=1,max_length=300)
    mode:Literal["test","approved"]="test"


@app.get("/api/tiktok")
def tiktok_connection():return tiktok.connection()


@app.post("/api/tiktok/config")
def tiktok_config(body:TikTokConfig):
    tiktok.configure(body.client_key,body.client_secret,body.mode)
    return {"configured":True}


@app.post("/api/tiktok/connect")
def tiktok_connect():return {"url":tiktok.auth_url("http://127.0.0.1:"+os.environ.get("CLIPLAB_PORT","8765"))}


@app.get("/api/tiktok/callback")
def tiktok_callback(state:str="",code:str="",error:str=""):
    if error or not code:raise ValueError("Collegamento TikTok annullato.")
    tiktok.finish_auth(state,code)
    return RedirectResponse("/#settings")


@app.get("/api/tiktok/creator")
def tiktok_creator():return tiktok.creator_info()


@app.delete("/api/tiktok")
def tiktok_disconnect():
    tiktok.disconnect()
    return {"connected":False}


@app.post("/api/youtube/config")
async def youtube_config(file: UploadFile = File(...)):
    raw = await file.read(65537)
    if len(raw) > 65536:
        raise ValueError("Il file JSON è troppo grande.")
    try:
        config = json.loads(raw)
    except Exception:
        raise ValueError("Il file non è un JSON valido.")
    youtube.configure(config)
    return {"configured": True}


@app.post("/api/youtube/connect")
def youtube_connect(request: Request):
    port = os.environ.get("CLIPLAB_PORT", "8765")
    return {"url": youtube.auth_url(f"http://127.0.0.1:{port}")}


@app.get("/api/youtube/callback")
def youtube_callback(state: str = "", code: str = "", error: str = ""):
    try:
        if error or not code:
            raise ValueError("Autorizzazione annullata. Puoi riprovare dalle impostazioni.")
        youtube.finish_auth(state, code)
        return RedirectResponse("/?connected=1#settings")
    except Exception:
        return HTMLResponse("<html lang='it'><title>Collegamento YouTube</title><body style='background:#121512;color:#eee;font:18px system-ui;padding:60px'><h1>Collegamento non completato</h1><p>Il consenso potrebbe essere scaduto oppure l’account non ha un singolo canale selezionato. Torna all’app e riprova.</p><a style='color:#d3ff5f' href='/#settings'>Torna a ClipLab</a></body></html>", status_code=400)


@app.delete("/api/youtube")
def youtube_disconnect():
    youtube.disconnect()
    return {"connected": False}


app.mount("/static", StaticFiles(directory=engine.ROOT / "static"), name="static")


@app.get("/")
def index():
    return HTMLResponse((engine.ROOT / 'static' / 'index.html').read_text(encoding='utf-8').replace('__CLIPLAB_VERSION__',VERSION).replace('__CLIPLAB_LAUNCH_EXT__','cmd' if is_windows() else 'command'),
                        headers={'Cache-Control':'no-store'})


if __name__ == "__main__":
    import uvicorn
    config=uvicorn.Config(app,host='127.0.0.1',port=int(os.environ.get('CLIPLAB_PORT','8765')),access_log=False)
    app.state.server=uvicorn.Server(config)
    app.state.server.run()

