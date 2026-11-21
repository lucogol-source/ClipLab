"""Start ClipLab independently of the terminal or the Codex preview session."""
from __future__ import annotations

import argparse
import errno
import http.client
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import uuid
import webbrowser
from pathlib import Path
from version import VERSION
from filelock import FileLock
from platform_support import process_options

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("CLIPLAB_DATA_DIR",str(ROOT / ".data"))).resolve()
PORT = int(os.environ.get("CLIPLAB_PORT", "8765"))
if not 1024 <= PORT <= 65535:
    raise ValueError("La porta di ClipLab deve essere compresa tra 1024 e 65535.")
URL = f"http://127.0.0.1:{PORT}"
RECORD = DATA / f"server-{PORT}.json"
LOG = DATA / "server.log"


def health(port=None):
    connection = http.client.HTTPConnection("127.0.0.1", port or PORT, timeout=1)
    try:
        connection.request("GET", "/api/health")
        response = connection.getresponse()
        if response.status != 200:
            return None
        return json.loads(response.read(8192))
    except (OSError, ValueError, http.client.HTTPException):
        return None
    finally:
        connection.close()


def owns_server(info):
    return bool(info and info.get("application") == "cliplab" and info.get("app_root") == str(ROOT)
                and info.get('data_dir',str(ROOT/'.data')) == str(DATA))


def port_available(port):
    with socket.socket() as listener:
        try:listener.bind(('127.0.0.1',port))
        except OSError as error:
            if error.errno==errno.EADDRINUSE:return False
            raise
        return True


def select_port():
    global PORT,URL,RECORD
    if PORT!=8765:return
    candidates=(8765,*range(8768,8779))
    states={port:health(port) for port in candidates}
    owned=next((port for port,info in states.items() if owns_server(info) and info.get('instance_id')),None)
    available=owned if owned is not None else next((port for port,info in states.items() if not info and port_available(port)),None)
    if available is None:raise RuntimeError('Nessuna porta locale disponibile per ClipLab (8765, 8768–8778).')
    if any(owns_server(info) and not info.get('instance_id') for info in states.values()):
        os.environ['CLIPLAB_LEGACY_ACTIVE']='1'
    PORT=available
    URL=f'http://127.0.0.1:{PORT}'
    RECORD=DATA/f'server-{PORT}.json'
    os.environ['CLIPLAB_PORT']=str(PORT)


def save_record(record):
    temporary = RECORD.with_suffix(".tmp")
    with open(temporary, "w", opener=lambda p, flags: os.open(p, flags, 0o600)) as output:
        json.dump(record, output)
    temporary.replace(RECORD)


def start(open_browser=True):
    DATA.mkdir(exist_ok=True)
    with FileLock(str(DATA/'start.lock'),timeout=30):
        current = health()
        if current and not owns_server(current):
            raise RuntimeError(f"La porta {PORT} è già usata da un’altra istanza. Chiudila prima di avviare questa copia di ClipLab.")
        if not current:
            instance = uuid.uuid4().hex
            shutdown_token = secrets.token_urlsafe(32)
            environment = dict(os.environ, CLIPLAB_PORT=str(PORT), CLIPLAB_INSTANCE=instance,
                               CLIPLAB_SHUTDOWN_TOKEN=shutdown_token)
            with open(LOG, "ab", buffering=0, opener=lambda p, flags: os.open(p, flags, 0o600)) as output:
                process = subprocess.Popen(
                    [sys.executable, str(ROOT / "server.py")], cwd=ROOT,
                    env=environment, stdin=subprocess.DEVNULL, stdout=output,
                    stderr=subprocess.STDOUT, close_fds=True, **process_options(detached=True),
                )
            save_record({"pid": process.pid, "instance": instance, "shutdown_token": shutdown_token})
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                current = health()
                if owns_server(current) and current.get("instance_id") == instance:
                    break
                if process.poll() is not None:
                    raise RuntimeError(f"Il motore non si è avviato. Il dettaglio è in {LOG}.")
                time.sleep(.2)
            else:
                raise RuntimeError(f"Il motore sta impiegando troppo tempo ad avviarsi. Controlla {LOG}.")
    print(f"ClipLab V{current.get('version',VERSION)} è attivo: {URL}", flush=True)
    print("Puoi chiudere questa finestra. Per fermare il motore usa Ferma ClipLab (.cmd su Windows, .command su Mac).", flush=True)
    if open_browser:
        webbrowser.open(URL)


def stop():
    current = health()
    if not current:
        print("ClipLab è già spento.")
        return
    if not owns_server(current) or not RECORD.exists():
        raise RuntimeError("Il processo attivo non appartiene a questa copia di ClipLab.")
    saved = json.loads(RECORD.read_text(encoding='utf-8'))
    if current.get("instance_id") != saved.get("instance") or current.get("pid") != saved.get("pid"):
        raise RuntimeError("Il motore è stato riavviato da un altro avvio. Non è stato arrestato.")
    if saved.get("shutdown_token"):
        connection = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
        try:
            connection.request("POST", "/api/shutdown", body=b"", headers={"X-ClipLab-Control": saved["shutdown_token"]})
            response = connection.getresponse()
            response.read()
            if response.status != 200:
                raise RuntimeError("Il motore ha rifiutato la richiesta di arresto.")
        finally:
            connection.close()
    else:
        os.kill(saved["pid"], signal.SIGINT)
    print("Arresto richiesto. Le elaborazioni in corso vengono interrotte.")


def main():
    select_port()
    parser = argparse.ArgumentParser(description="Avvio del motore locale ClipLab")
    parser.add_argument("action", nargs="?", choices=("start", "stop", "status"), default="start")
    args = parser.parse_args()
    if args.action == "stop":
        stop()
    elif args.action == "status":
        print("Attivo" if owns_server(health()) else "Spento")
    else:
        start(open_browser=os.environ.get("CLIPLAB_HEADLESS") != "1")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ClipLab: {error}", file=sys.stderr)
        sys.exit(1)
