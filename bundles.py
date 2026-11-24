"""Build selected exports on disk, with stable filenames and a metadata sidecar."""
import json
import re
import tempfile
import zipfile

import engine
import promotion


def validate(pid, clip_ids):
    if not clip_ids or len(clip_ids) > 500 or len(set(clip_ids)) != len(clip_ids):
        raise ValueError("Seleziona da 1 a 500 clip distinte.")
    project = engine.read_project(pid)
    if project["status"] in ("queued", "processing"):
        raise ValueError("Attendi il completamento dell’elaborazione.")
    folder = engine.project_dir(pid)
    selected = []
    for cid in clip_ids:
        clip = next((c for c in project["clips"] if c["id"] == cid), None)
        if clip is None:
            raise ValueError("Clip non trovata.")
        if (pid, cid) in engine.BUSY or clip["status"] in ("queued", "rendering", "uploading", "tracking", "transcribing"):
            raise engine.ClipBusy("Una clip selezionata è occupata. Attendi e riprova.")
        if not clip["exports"]:
            raise ValueError("Esporta prima tutte le clip selezionate.")
        export = clip["exports"][-1]
        if export.get("edit_revision", 0) != clip.get("edit_revision", 0):
            raise ValueError("Una clip è stata modificata. Riesportala prima del download.")
        name = export["file"]
        if not re.fullmatch(r"clip-[a-f0-9]{12}\.mp4", name):
            raise ValueError("Esportazione non valida.")
        path = folder / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("MP4 non disponibile. Riesporta la clip.")
        selected.append((clip, export))
    return selected


def create(pid, clip_ids):
    claimed = []
    archive = None
    try:
        with engine.BUSY_LOCK:
            selected = validate(pid, clip_ids)
            for cid in clip_ids:
                engine.claim_clip(pid, cid)
                claimed.append(cid)
        folder = engine.project_dir(pid)
        archive = tempfile.TemporaryFile(mode="w+b", dir=engine.DATA)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
            for index, (clip, export) in enumerate(selected, 1):
                name = export["file"]
                stem = re.sub(r"[^\w -]", "", clip["title"], flags=re.UNICODE).strip(" .")[:70]
                stem = f"{index:03d}-" + (stem or "clip")
                z.write(folder / name, stem + ".mp4")
                srt = name[:-4] + ".srt"
                if (folder / srt).is_file() and not (folder / srt).is_symlink():
                    z.write(folder / srt, stem + ".srt")
                text = promotion.description(clip.get("description", clip["title"]), clip.get("hashtags", []))
                z.writestr(stem + ".txt", clip["title"] + "\n\n" + text)
                z.writestr(stem + ".json", json.dumps({"title":clip["title"], "description":text,
                           "hashtags":clip.get("hashtags", []), "promotion":clip.get("promotion"),
                           "start":export["settings"]["start"], "end":export["settings"]["end"]},
                           ensure_ascii=False, indent=2))
        archive.seek(0)
        return archive
    except OSError as error:
        if archive:
            archive.close()
        raise ValueError("Impossibile preparare lo ZIP. Controlla lo spazio libero sul disco.") from error
    except BaseException:
        if archive:
            archive.close()
        raise
    finally:
        for cid in claimed:
            engine.release_clip(pid, cid)
