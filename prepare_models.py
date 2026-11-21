"""Download free local model files without requiring a Hugging Face account."""
import argparse
import hashlib
import os
import re
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('CLIPLAB_DATA_DIR',str(ROOT/'.data'))).resolve()
MODELS=Path(os.environ.get('CLIPLAB_MODELS_DIR',str(DATA/'models'))).resolve()


SMALL_SHA256="3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"


def checksum(path):
    value=hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda:source.read(4*1024*1024),b""):value.update(chunk)
    return value.hexdigest()


def download(url,path,sha256=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.stat().st_size>100:
        if not sha256 or checksum(path)==sha256:return
        path.replace(path.with_suffix(path.suffix+".invalid"))
    session=requests.Session()
    session.mount("https://",HTTPAdapter(max_retries=Retry(total=4,backoff_factor=1,status_forcelist=[429,500,502,503,504])))
    temporary=path.with_suffix(path.suffix+".part")
    for attempt in range(5):
        offset=temporary.stat().st_size if temporary.exists() else 0
        try:
            with session.get(url,headers={"Range":f"bytes={offset}-"} if offset else {},stream=True,timeout=(20,60)) as response:
                if response.status_code==416:
                    total=re.fullmatch(r'bytes \*/(\d+)',response.headers.get('Content-Range',''))
                    size_matches=bool(total and offset==int(total[1]))
                    digest_matches=bool(sha256 and temporary.exists() and checksum(temporary)==sha256)
                    if offset and (digest_matches or (not sha256 and size_matches)):
                        temporary.replace(path)
                        print(f'Pronto: {path.name} (download già completo)',flush=True)
                        return
                    temporary.unlink(missing_ok=True)
                    raise ValueError('Download parziale non valido: riparto da zero.')
                response.raise_for_status()
                resume=offset>0 and response.status_code==206
                if resume and not response.headers.get("Content-Range","").startswith(f"bytes {offset}-"):
                    raise ValueError("Risposta di ripresa del download non valida.")
                expected=int(response.headers.get("Content-Length",0))+(offset if resume else 0)
                with temporary.open("ab" if resume else "wb") as output:
                    for chunk in response.iter_content(1024*1024):output.write(chunk)
                if expected and temporary.stat().st_size!=expected:raise ValueError("Download incompleto: riprova l’aggiornamento.")
            if sha256 and checksum(temporary)!=sha256:
                temporary.unlink(missing_ok=True)
                raise ValueError("Integrità del modello non verificata. Ripeto il download.")
            temporary.replace(path)
            print(f"Pronto: {path.name} ({path.stat().st_size//1024**2} MB)",flush=True)
            return
        except (requests.RequestException,ValueError):
            if attempt==4:raise
            print(f"Riprendo il download di {path.name} senza perdere i dati già ricevuti…",flush=True)
            time.sleep(2)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--small",action="store_true")
    args=parser.parse_args()
    download("https://github.com/opencv/opencv_zoo/raw/refs/heads/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",MODELS/"face_detection_yunet.onnx")
    if args.small:
        for filename in ("config.json","tokenizer.json","vocabulary.txt","model.bin"):
            download("https://huggingface.co/Systran/faster-whisper-small/resolve/main/"+filename,MODELS/"whisper-small"/filename,SMALL_SHA256 if filename=="model.bin" else None)


if __name__=="__main__":main()
