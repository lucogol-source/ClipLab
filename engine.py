"""Local media pipeline. No paid APIs or remote inference."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import av
import imageio_ffmpeg
from platform_support import ffmpeg_tool, is_windows, process_options

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("CLIPLAB_DATA_DIR",str(ROOT / ".data"))).resolve()
PROJECTS = DATA / "projects"
MODELS = Path(os.environ.get("CLIPLAB_MODELS_DIR",str(DATA / "models"))).resolve()
TOOLS = DATA / "tools"
for folder in (PROJECTS, MODELS, TOOLS):
    folder.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODELS / "hub"))
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FFMPEG_LINK = ffmpeg_tool(FFMPEG,TOOLS)
LOCK = threading.RLock()
MODEL_LOCK = threading.Lock()
MODEL_CACHE = {}
EVENTS: dict[str, threading.Event] = {}
BUSY: set[tuple[str, str]] = set()
BUSY_LOCK = threading.RLock()
ANALYZING: set[str] = set()
MAX_SECONDS = 2 * 3600


class Cancelled(Exception):
    pass


class ClipBusy(ValueError):
    pass


def claim_clip(pid, cid):
    """Reserve a clip for both interactive tasks and scheduled publishers."""
    with BUSY_LOCK:
        p = read_project(pid)
        clip = next((c for c in p['clips'] if c['id'] == cid), None)
        if clip is None:
            raise ValueError('Clip non trovata')
        if (pid,cid) in BUSY or pid in ANALYZING or p.get('status') in ('queued','processing') or clip.get('status') in ('queued','rendering','uploading','tracking','transcribing'):
            raise ClipBusy('Clip già in elaborazione. Attendi il completamento.')
        if not any(key[0] == pid for key in BUSY):
            EVENTS[pid] = threading.Event()
        BUSY.add((pid,cid))
        return p, clip


def release_clip(pid, cid):
    with BUSY_LOCK:
        BUSY.discard((pid,cid))
        if not any(key[0] == pid for key in BUSY):
            EVENTS.pop(pid, None)


def cancel_project(pid):
    with BUSY_LOCK:
        p = read_project(pid)
        if p.get('status') in ('queued','processing') or pid in ANALYZING or any(key[0] == pid for key in BUSY):
            EVENTS.setdefault(pid, threading.Event()).set()


def project_dir(pid: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", pid):
        raise ValueError("Progetto non valido")
    path = PROJECTS / pid
    if not path.is_dir():
        raise FileNotFoundError("Progetto non trovato")
    return path


def read_project(pid: str) -> dict:
    with LOCK:
        return json.loads((project_dir(pid) / "project.json").read_text(encoding='utf-8'))


def write_project(project: dict):
    with LOCK:
        path = project_dir(project["id"]) / "project.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(path)


def update(pid: str, **changes):
    with LOCK:
        p = read_project(pid)
        p.update(changes)
        write_project(p)
        return p


def update_clip(pid: str, cid: str, **changes):
    with LOCK:
        p = read_project(pid)
        clip = next((c for c in p["clips"] if c["id"] == cid), None)
        if clip is None:
            raise ValueError("Clip non trovata")
        clip.update(changes)
        write_project(p)
        return clip


def new_project(options: dict, title="Nuovo video") -> dict:
    pid = uuid.uuid4().hex
    (PROJECTS / pid).mkdir()
    p = {"id": pid, "title": title, "created": time.time(), "status": "queued",
         "stage": "In coda", "progress": 0, "options": options,
         "clips": [], "segments": [], "duration": 0, "error": None}
    write_project(p)
    EVENTS[pid] = threading.Event()
    return p


def check_cancel(pid):
    event = EVENTS.get(pid)
    if event is not None and event.is_set():
        raise Cancelled("Elaborazione interrotta")


def normalize_youtube(value: str) -> str:
    try:
        u = urlparse(value.strip())
        if u.scheme not in ("https", "http") or u.username or u.password or u.port:
            raise ValueError()
        host = (u.hostname or "").lower()
        if host == "youtu.be":
            video_id = u.path.strip("/")
        elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            parts = u.path.strip("/").split("/")
            video_id = parse_qs(u.query).get("v", [""])[0] if u.path == "/watch" else (parts[1] if len(parts) == 2 and parts[0] in ("shorts", "live", "embed") else "")
        else:
            raise ValueError()
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError()
        return f"https://www.youtube.com/watch?v={video_id}"
    except (ValueError, TypeError):
        raise ValueError("Incolla il link di un singolo video YouTube valido.")


def run(args, pid=None, cwd=None, timeout=3600, on_poll=None):
    with subprocess.Popen([str(a) for a in args], cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', **process_options()) as proc:
        started = time.monotonic()
        while True:
            try:
                output, _ = proc.communicate(timeout=0.4)
                break
            except subprocess.TimeoutExpired:
                if on_poll:on_poll()
                if (pid and (event := EVENTS.get(pid)) is not None and event.is_set()) or time.monotonic() - started > timeout:
                    proc.kill()
                    proc.communicate()
                    if pid:
                        check_cancel(pid)
                    raise RuntimeError("Tempo di elaborazione superato.")
        if proc.returncode:
            # Keep detailed diagnostics local; UI gets a bounded useful error.
            if cwd:
                (Path(cwd) / "last-error.log").write_text(output[-12000:], encoding='utf-8')
            raise RuntimeError(output[-1800:].strip() or "Operazione video non riuscita")
        return output


def probe(path: Path) -> dict:
    with av.open(str(path)) as c:
        video = next(iter(c.streams.video), None)
        if video is None:
            raise ValueError("Il file non contiene una traccia video.")
        duration = float(c.duration / av.time_base) if c.duration else float((video.duration or 0) * video.time_base)
        if not math.isfinite(duration) or duration <= 0 or duration > MAX_SECONDS:
            raise ValueError("Scegli un video di durata compresa tra 1 secondo e 2 ore.")
        return {"duration": round(duration, 3), "width": video.width, "height": video.height,
                "has_audio": bool(c.streams.audio)}


def javascript_runtime() -> dict:
    """Finder launches don't inherit the user's nvm/Homebrew shell configuration."""
    home = Path.home()
    candidates = [str(ROOT / ".tools" / ('node.exe' if is_windows() else 'node')), shutil.which("node"),
                  "/opt/homebrew/bin/node", "/usr/local/bin/node", str(home / ".local/bin/node")]
    if is_windows():
        candidates += [str(Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'nodejs'/'node.exe'),
                       str(Path(os.environ.get('LOCALAPPDATA',str(home/'AppData/Local')))/'Programs/nodejs/node.exe')]
    candidates += [str(path) for path in sorted((home / ".nvm/versions/node").glob("*/bin/node"), reverse=True)]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return {"node": {"path": candidate}}
    deno = shutil.which("deno")
    return {"deno": {"path": deno}} if deno else {}


def download(pid: str, url: str) -> Path:
    import yt_dlp
    folder = project_dir(pid)

    def progress(d):
        check_cancel(pid)
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            pct = min(1, d.get("downloaded_bytes", 0) / total) if total else 0
            update(pid, stage="Scaricamento da YouTube", progress=4 + round(pct * 20))

    def duration_filter(info, *, incomplete):
        if info.get("is_live"):
            return "Le dirette in corso non sono supportate. Usa una registrazione."
        if (info.get("duration") or 0) > MAX_SECONDS:
            return "Il video supera il limite di 2 ore."
        if (info.get("filesize") or info.get("filesize_approx") or 0) > 2 * 1024**3:
            return "Il video supera il limite di 2 GB."

    runtime = javascript_runtime()
    options = {"format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b[height<=1080]",
               "outtmpl": str(folder / "source.%(ext)s"), "merge_output_format": "mp4",
               "ffmpeg_location": str(FFMPEG_LINK), "noplaylist": True,
               "quiet": True, "no_warnings": True, "cachedir": str(DATA / "yt-cache"),
               "progress_hooks": [progress], "match_filter": duration_filter,
               "socket_timeout": 30, "retries": 3, "max_filesize": 2 * 1024**3}
    if runtime:
        options["js_runtimes"] = runtime
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
    if not info:
        raise ValueError("Video non disponibile o oltre i limiti di durata/dimensione.")
    paths = [p for p in folder.glob("source.*") if p.suffix in (".mp4", ".mkv", ".webm", ".mov")]
    if not paths:
        raise ValueError("YouTube non ha restituito un video scaricabile. Puoi caricare il file originale.")
    path = max(paths, key=lambda p: p.stat().st_size)
    update(pid, title=info.get("title", "Video YouTube"), source_url=url, source_file=path.name,
           channel=info.get("uploader", "YouTube"))
    return path


def transcript(pid: str, path: Path, meta: dict) -> tuple[list, str]:
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    from faster_whisper import WhisperModel
    p = read_project(pid)
    size = p["options"].get("model", "base")
    update(pid, stage=f"Preparazione Whisper {size} · primo utilizzo: download modello", progress=28)
    with MODEL_LOCK:
        check_cancel(pid)
        if size not in MODEL_CACHE:
            local_model=MODELS/f"whisper-{size}"
            if size=="small" and (local_model/"model.bin").exists() and (local_model/"model.bin").stat().st_size!=483546902:
                raise ValueError("Download Whisper Small incompleto. Esegui Aggiorna ClipLab.command per riprenderlo.")
            MODEL_CACHE[size] = WhisperModel(str(local_model) if (local_model/"model.bin").exists() else size, device="cpu", compute_type="int8",
                                            cpu_threads=min(8, os.cpu_count() or 4), download_root=str(MODELS))
        model = MODEL_CACHE[size]
    language = p["options"].get("language", "auto")
    segments, info = model.transcribe(str(path), language=None if language == "auto" else language,
                                     beam_size=5, word_timestamps=True, vad_filter=True,
                                     initial_prompt=p["options"].get("glossary") or None,
                                     condition_on_previous_text=True)
    result = []
    for s in segments:
        check_cancel(pid)
        if s.no_speech_prob > 0.85 or not s.text.strip():
            continue
        result.append({"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
                       "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word.strip()} for w in (s.words or [])]})
        update(pid, stage="Trascrizione locale", progress=min(88, 30 + round(s.end / meta["duration"] * 58)))
    return result, info.language


HOOKS = ("perché", "come", "segreto", "errore", "incredibile", "scoperto", "attenzione", "verità", "ecco", "immagina", "why", "how", "secret", "mistake", "imagine", "never", "actually")
STOP = set("il lo la i gli le un uno una di a da in con su per tra fra e che è non si ma del della the a an and to of is it in that you for on this".split())


def propose_clips(segments: list, duration: float, target=45, count=4) -> list:
    """Transparent local ranking: hooks, speech density and sentence boundaries."""
    if not segments:
        return []
    candidates = []
    for i, first in enumerate(segments):
        start = max(0.0, first["start"] - 0.12)
        if duration - start < min(10, duration * 0.5):
            continue
        selected = []
        for s in segments[i:]:
            if s["start"] >= start + target * 1.2:
                break
            selected.append(s)
            elapsed = s["end"] - start
            if elapsed >= target * 0.75 and (re.search(r"[.!?…]$", s["text"]) or elapsed >= target):
                break
        end = min(duration, start + min(180, target * 1.2), selected[-1]["end"] + 0.15)
        text = " ".join(s["text"] for s in selected)
        words = re.findall(r"\w+", text.lower())
        content = {w for w in words if w not in STOP}
        speech = sum(max(0, min(s["end"], end) - s["start"]) for s in selected)
        density = min(1, speech / max(1, end - start))
        hook = sum(1 for w in HOOKS if re.search(r"\b" + w + r"\b", first["text"].lower()))
        score = 28 + min(18, len(content) / 2) + 22 * density + min(16, hook * 7) + (6 if "?" in text else 0) + (5 if re.search(r"\d", text) else 0)
        score -= abs((end - start) - target) / target * 12
        candidates.append({"start": round(start, 2), "end": round(end, 2), "text": text,
                           "score": round(max(1, min(99, score))), "keywords": content})
    chosen = []
    for c in sorted(candidates, key=lambda c: c["score"], reverse=True):
        if any(max(0, min(c["end"], x["end"]) - max(c["start"], x["start"])) > min(c["end"] - c["start"], x["end"] - x["start"]) * 0.25 for x in chosen):
            continue
        chosen.append(c)
        if len(chosen) >= count:
            break
    result = []
    for c in chosen:
        title = re.split(r"(?<=[.!?])\s", c["text"])[0]
        if len(title) > 85:
            title = title[:82].rsplit(" ", 1)[0] + "…"
        result.append({"id": uuid.uuid4().hex[:12], "title": title, "start": c["start"], "end": c["end"],
                       "score": c["score"], "text": c["text"], "status": "suggested", "exports": [],
                       "reason": "Apertura, densità del parlato e fine frase. Punteggio editoriale, non previsione di visualizzazioni."})
    return result


def split_full_video(segments, duration, target, title):
    """Cover the source in consecutive editable parts, including silence."""
    boundaries = [0.0]
    while boundaries[-1] + target < duration:
        boundaries.append(boundaries[-1] + target)
    # Keep the final part editable when only a fraction of a second remains.
    if len(boundaries) > 1 and duration - boundaries[-1] < .5:
        boundaries[-1] = duration - .5
    boundaries.append(duration)
    clips = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:]), 1):
        suffix = f" · Parte {index}"
        text = " ".join(s["text"] for s in segments if s["end"] > start and s["start"] < end)
        clips.append({"id": uuid.uuid4().hex[:12], "title": title[:100-len(suffix)] + suffix,
                      "start": start, "end": end, "score": None, "text": text,
                      "status": "suggested", "exports": [],
                      "reason": "Parte consecutiva del video completo."})
    return clips


def analyze(pid: str, url=None):
    with BUSY_LOCK:
        ANALYZING.add(pid)
    try:
        update(pid, status="processing", stage="Importazione", progress=2, error=None)
        check_cancel(pid)
        p = read_project(pid)
        path = download(pid, url) if url else project_dir(pid) / p["source_file"]
        check_cancel(pid)
        meta = probe(path)
        update(pid, **meta, source_file=path.name)
        run([FFMPEG, "-y", "-ss", min(2, meta["duration"] / 3), "-i", path, "-frames:v", "1", "-vf", "scale=640:-2", project_dir(pid) / "poster.jpg"], pid, project_dir(pid), 120)
        if meta["has_audio"]:
            segments, language = transcript(pid, path, meta)
        else:
            segments, language = [], ""
        check_cancel(pid)
        p = read_project(pid)
        if p["options"].get("mode", "highlights") == "full":
            clips = split_full_video(segments, meta["duration"], p["options"]["duration"], p["title"])
        else:
            clips = propose_clips(segments, meta["duration"], p["options"]["duration"], p["options"]["count"])
        notice = None if segments else "Non è stato riconosciuto parlato. Le clip sono modificabili, con sottotitoli disponibili soltanto dove c’è una trascrizione."
        if not clips:
            end = min(meta["duration"], p["options"]["duration"])
            clips = [{"id": uuid.uuid4().hex[:12], "title": p["title"][:100], "start": 0, "end": end,
                      "score": None, "text": "", "status": "suggested", "exports": [],
                      "reason": "Clip iniziale da modificare manualmente: nessun parlato riconosciuto."}]
            notice = "Non è stato riconosciuto parlato. Puoi tagliare il video manualmente; non ci sono sottotitoli."
        update(pid, status="ready", stage="Clip pronte", progress=100, segments=segments, language=language, clips=clips, notice=notice)
        if p["options"].get("auto_publish"):
            update(pid, status="processing", stage="Esportazione e caricamento automatico", progress=100)
            from youtube import upload_clip
            failures = []
            for clip in clips:
                check_cancel(pid)
                try:
                    render(pid, clip["id"], {"start": clip["start"], "end": clip["end"], "title": clip["title"],
                                       "format": p["options"]["format"], "captions": p["options"]["captions"], "crop": 50})
                    upload_clip(pid, clip["id"], p["options"]["channel_id"], p["options"]["privacy"],
                            p["options"].get("made_for_kids", False), clip["title"], "#Shorts")
                except Cancelled:
                    raise
                except Exception as error:
                    check_cancel(pid)  # Upload clients may wrap cancellation errors.
                    failures.append({"clip_id":clip['id'],"error":str(error)[-1200:]})
                    update_clip(pid,clip['id'],status='error',error=str(error)[-1200:])
            update(pid, status="ready", stage="Flusso completato con errori" if failures else "Flusso completato",
                   auto_publish_errors=failures, notice=f"{len(failures)} clip non completate: consulta i dettagli delle singole clip." if failures else notice)
    except Cancelled:
        update(pid, status="cancelled", stage="Interrotto")
    except Exception as e:
        message = str(e)
        if "Sign in" in message or "bot" in message.lower() or "403" in message:
            message = "YouTube ha bloccato il download. Carica il file originale dalla scheda File locale. Dettaglio: " + message[-250:]
        update(pid, status="error", stage="Operazione non completata", error=message[-1600:])
    finally:
        with BUSY_LOCK:
            ANALYZING.discard(pid)
            if not any(key[0] == pid for key in BUSY):
                EVENTS.pop(pid, None)


def caption_groups(segments, start, end):
    words = []
    for s in segments:
        if s["end"] <= start or s["start"] >= end:
            continue
        source = s.get("words") or [{"start": s["start"], "end": s["end"], "word": s["text"]}]
        for w in source:
            a, b = max(start, w["start"]), min(end, w["end"])
            if b > a and w["word"].strip():
                words.append({"start": a - start, "end": b - start, "word": w["word"].strip()})
    groups, current = [], []
    for w in words:
        if current and (len(current) >= 5 or len(" ".join(x["word"] for x in current)) + len(w["word"]) > 34 or w["start"] - current[-1]["end"] > 0.7):
            groups.append(current)
            current = []
        current.append(w)
        if re.search(r"[.!?]$", w["word"]):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def stamp(seconds, ass=False):
    # Round the total first so carry from 59.999 seconds remains valid.
    scale = 100 if ass else 1000
    total = max(0, round(seconds * scale))
    whole, frac = divmod(total, scale)
    h, rest = divmod(whole, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02}:{s:02}.{frac:02}" if ass else f"{h:02}:{m:02}:{s:02},{frac:03}"


def subtitles(segments, start, end, style, width, height):
    groups = caption_groups(segments, start, end)
    srt = []
    ass = [f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,{round(width * (0.066 if width < height else 0.041))},&H005FFFD3,&H00FFFFFF,&H00141414,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,{round(width*.07)},{round(width*.07)},{round(height*.16)},1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for i, group in enumerate(groups, 1):
        a, b = group[0]["start"], group[-1]["end"]
        text = " ".join(w["word"] for w in group)
        srt.append(f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n")
        clean = lambda t: re.sub(r"[{}\\\r\n]", "", t)
        if style == "karaoke":
            pieces = []
            cursor = a
            for w in group:
                gap = max(0, round((w["start"] - cursor) * 100))
                if gap:
                    pieces.append("{\\k" + str(gap) + "} ")
                pieces.append("{\\k" + str(max(1, round((w["end"] - w["start"]) * 100))) + "}" + clean(w["word"]))
                cursor = w["end"]
            display = " ".join(pieces)
        else:
            display = "{\\1c&HFFFFFF&}" + clean(text)
        ass.append(f"Dialogue: 0,{stamp(a, True)},{stamp(b, True)},Default,,0,0,0,,{display}")
    return "\n".join(srt), "\n".join(ass)


def retranscribe_clip(pid, cid, model_size="small", glossary=""):
    import captions
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    from faster_whisper import WhisperModel
    p=read_project(pid)
    clip=next(c for c in p["clips"] if c["id"]==cid)
    start,end=clip["start"],clip["end"]
    folder=project_dir(pid)
    audio=folder/f"caption-audio-{cid}.wav"
    update_clip(pid,cid,status="transcribing",error=None)
    try:
        run([FFMPEG,"-y","-ss",start,"-i",folder/p["source_file"],"-t",end-start,"-vn","-ac","1","-ar","16000",audio],pid,folder)
        with MODEL_LOCK:
            if model_size not in MODEL_CACHE:
                local_model=MODELS/f"whisper-{model_size}"
                if model_size=="small" and (local_model/"model.bin").exists() and (local_model/"model.bin").stat().st_size!=483546902:
                    raise ValueError("Download Whisper Small incompleto. Esegui Aggiorna ClipLab.command per riprenderlo.")
                MODEL_CACHE[model_size]=WhisperModel(str(local_model) if (local_model/"model.bin").exists() else model_size,device="cpu",compute_type="int8",cpu_threads=min(8,os.cpu_count() or 4),download_root=str(MODELS))
            model=MODEL_CACHE[model_size]
        segments,info=model.transcribe(str(audio),language=p.get("language") or None,beam_size=5,
                                       word_timestamps=True,vad_filter=True,initial_prompt=glossary or p["options"].get("glossary") or None,
                                       condition_on_previous_text=True)
        shifted=[]
        for s in segments:
            check_cancel(pid)
            if s.no_speech_prob>.85:continue
            shifted.append({"start":s.start+start,"end":s.end+start,"text":s.text.strip(),"words":[{"start":w.start+start,"end":w.end+start,"word":w.word.strip(),"probability":round(w.probability,3)} for w in s.words or []]})
        if not shifted:
            raise ValueError("Non è stato riconosciuto parlato. La traccia precedente è conservata.")
        latest=next(c for c in read_project(pid)["clips"] if c["id"]==cid)
        track = captions.store_track(latest,captions.make_cues(shifted,start,end),start,end)
        update_clip(pid,cid,**track,asr_model=model_size,
                    edit_revision=latest.get("edit_revision",0)+1,status="exported" if latest["exports"] else "suggested",error=None)
    except Exception as e:
        update_clip(pid,cid,status="error",error=str(e)[-1000:])
        raise
    finally:
        audio.unlink(missing_ok=True)


def render(pid, cid, settings):
    settings = {"layout": "blur", **settings}
    import captions
    p = read_project(pid)
    clip = next(c for c in p["clips"] if c["id"] == cid)
    start, end = float(settings["start"]), float(settings["end"])
    if not all(math.isfinite(x) for x in (start, end)) or start < 0 or end > p["duration"] + .01 or not 0.5 <= end - start <= 180:
        raise ValueError("La clip deve durare da 0,5 a 180 secondi e restare entro il video.")
    aspect = settings.get("format", "9:16")
    quality=settings.get("quality",1080)
    width, height = {"9:16": (1080,1920) if quality==1080 else (720,1280), "1:1": (quality,quality), "16:9": (1920,1080) if quality==1080 else (1280,720)}[aspect]
    crop = float(settings.get("crop", 50))
    if not math.isfinite(crop) or not 0 <= crop <= 100:
        raise ValueError("Inquadratura non valida")
    style = settings.get("captions", "karaoke")
    folder, eid = project_dir(pid), uuid.uuid4().hex[:12]
    output = folder / f"clip-{eid}.mp4"
    cues=captions.track(p,clip,start,end,settings.get("caption_words",5))
    srt, ass = captions.render(cues,start,end,width,height,style,settings.get("font_scale",1),settings.get("caption_bottom",22),settings.get("caption_color","#d3ff5f"))
    (folder / f"clip-{eid}.srt").write_text(srt, encoding='utf-8')
    (folder / f"clip-{eid}.ass").write_text(ass, encoding='utf-8')
    zoom=settings.get("zoom",1)
    y=settings.get("crop_y",50)/100
    vf = f"scale={math.ceil(width*zoom)}:{math.ceil(height*zoom)}:force_original_aspect_ratio=increase,crop={width}:{height}:(iw-ow)*{crop/100:.4f}:(ih-oh)*{y:.4f},setsar=1"
    if style != "none" and srt:
        vf += f",ass=clip-{eid}.ass"
    update_clip(pid, cid, status="rendering", render_progress=0, error=None)
    try:
        if settings.get("keyframes") or settings.get("layout","crop")!="crop":
            last_progress=[-1]
            progress_file=folder/f"progress-{eid}.txt"
            def progress():
                try:value=int(progress_file.read_text(encoding='utf-8'))
                except (FileNotFoundError,ValueError):return
                if value//10!=last_progress[0]:
                    last_progress[0]=value//10
                    update_clip(pid,cid,render_progress=value)
            config_file=folder/f"render-{eid}.json"
            config_file.write_text(json.dumps({"source":str(folder/p["source_file"]),"output":str(output),"start":start,"end":end,"width":width,"height":height,
                "settings":settings,"ffmpeg":FFMPEG,"ass_path":str(folder/f"clip-{eid}.ass") if style!="none" and srt else None,"progress_file":str(progress_file)}), encoding='utf-8')
            try:run([sys.executable,ROOT/"framing.py","render",config_file],pid,folder,on_poll=progress)
            finally:
                config_file.unlink(missing_ok=True)
                progress_file.unlink(missing_ok=True)
        else:
            run([FFMPEG, "-y", "-ss", start, "-i", folder / p["source_file"], "-t", end-start,
             "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "21",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", output], pid, folder)
        record = {"id": eid, "file": output.name, "srt": f"clip-{eid}.srt", "created": time.time(), "settings": settings,
                  "edit_revision":clip.get("edit_revision",0),"watermark":False,"width":width,"height":height}
        # Use the latest clip state so export history is retained.
        latest = next(c for c in read_project(pid)["clips"] if c["id"] == cid)
        update_clip(pid, cid, title=settings.get("title", clip["title"]), start=start, end=end,
                    status="exported", render_progress=100, exports=latest["exports"] + [record], error=None)
        return record
    except Exception as e:
        output.unlink(missing_ok=True)
        update_clip(pid, cid, status="error", error=str(e)[-1000:])
        raise

