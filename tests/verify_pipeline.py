"""Run with the app running: .venv/bin/python tests/verify_pipeline.py /absolute/path/video.mp4
Uploads only to the LOCAL app, transcribes and exports three formats. Never contacts YouTube.
The test project remains in the library for inspection. Requires the selected Whisper model.
"""
import json
import os
import sys
import time
from pathlib import Path

import av
import requests

BASE = os.environ.get("CLIPLAB_URL", "http://127.0.0.1:8765").rstrip("/") + "/api"


def request(method, path, **kwargs):
    r = requests.request(method, BASE + path, timeout=180, **kwargs)
    r.raise_for_status()
    return r.json()


def wait_project(pid):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        p = request("GET", "/projects/" + pid)
        if p["status"] in ("ready", "error", "cancelled"):
            assert p["status"] == "ready", p.get("error")
            return p
        time.sleep(1)
    raise TimeoutError("Trascrizione oltre i 180 secondi del test")


def main():
    source = Path(sys.argv[1]).resolve()
    with source.open("rb") as f:
        p = request("POST", "/import/file", files={"file": ("Demo - prova locale.mp4", f, "video/mp4")}, data={"options": json.dumps({"count": 1, "duration": 30, "language": "en", "model": "base"})})
    pid = p["id"]
    print("Project:", pid, flush=True)
    p = wait_project(pid)
    assert p["segments"] and p["clips"], "Nessuna trascrizione o proposta"
    print("Transcript:", " ".join(s["text"] for s in p["segments"]), flush=True)
    c = p["clips"][0]
    for aspect, dimensions in (("9:16", (1080, 1920)), ("1:1", (1080, 1080)), ("16:9", (1920, 1080))):
        request("POST", f"/projects/{pid}/clips/{c['id']}/export", json={"title": "Prova locale · sottotitoli e taglio", "start": c["start"], "end": c["end"], "format": aspect, "crop": 50, "captions": "karaoke"})
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            p = request("GET", "/projects/" + pid)
            clip = p["clips"][0]
            if clip["status"] not in ("queued", "rendering"):
                assert clip["status"] == "exported", clip.get("error")
                break
            time.sleep(1)
        else:
            raise TimeoutError("Esportazione oltre il limite del test")
        file = Path(__file__).resolve().parents[1] / ".data/projects" / pid / clip["exports"][-1]["file"]
        with av.open(str(file)) as container:
            stream = container.streams.video[0]
            assert (stream.width, stream.height) == dimensions
            assert container.streams.audio, "Audio perso durante il rendering"
            assert abs(container.duration / av.time_base - (c["end"] - c["start"])) < .3
            next(container.decode(video=0))
        srt = file.with_suffix(".srt").read_text()
        assert "-->" in srt
        print(f"PASS {aspect}: {dimensions[0]}x{dimensions[1]}, audio, duration, decodable frame, SRT", flush=True)
    print("PASS pipeline; view http://127.0.0.1:8765/#project/" + pid, flush=True)


if __name__ == "__main__":
    main()
