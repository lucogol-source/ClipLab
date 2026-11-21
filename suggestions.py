"""A durable outbox for the private ClipLab issue tracker."""
import json
import os
import sys
import shutil
import sqlite3
import subprocess
import threading
import time
from contextlib import contextmanager, closing
from pathlib import Path

import requests

import engine
from approval import API, OWNER_ID, REPO, issue_content
from platform_support import is_windows, process_options
from version import VERSION

DB = engine.DATA / "suggestions.sqlite3"
STOP = threading.Event()
WAKE = threading.Event()
THREAD = None
LOCK = threading.Lock()
NO_RECEIPT = "Nessuna ricevuta trovata. Controlla tra le issue prima di ripetere l’invio."
AUTH_HELP = "Accedi a GitHub CLI con il tuo account autorizzato al repository."


@contextmanager
def database():
    with closing(sqlite3.connect(DB, timeout=10)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("""CREATE TABLE IF NOT EXISTS suggestions (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
            version TEXT NOT NULL, platform TEXT NOT NULL, created REAL NOT NULL,
            state TEXT NOT NULL DEFAULT 'queued', number INTEGER, account TEXT,
            detail TEXT NOT NULL DEFAULT '', retry_at REAL NOT NULL DEFAULT 0)""")
        yield db


def via_codex():
    return (DB.parent / "suggestions-via-codex").is_file()


def list_items():
    with database() as db:
        return [dict(row) for row in db.execute("SELECT * FROM suggestions ORDER BY created DESC")]


def save(key, title, description):
    title, description = title.strip(), description.strip().replace("\r\n", "\n")
    if not title or not description or any(c in title for c in "\r\n"):
        raise ValueError("Inserisci un titolo su una riga e descrivi la proposta.")
    with database() as db:
        bridge = via_codex()
        db.execute("""INSERT OR IGNORE INTO suggestions
                   (id,title,description,version,platform,created,state,detail) VALUES (?,?,?,?,?,?,?,?)""",
                   (key,title,description,VERSION,"Windows" if is_windows() else "macOS",time.time(),
                    "handoff" if bridge else "queued",
                    "In coda per il prossimo controllo di Codex su questo Mac." if bridge else ""))
        row = db.execute("SELECT * FROM suggestions WHERE id=?", (key,)).fetchone()
        if (row["title"],row["description"]) != (title,description):
            raise ValueError("Questa proposta è già stata salvata con un altro testo.")
    WAKE.set()
    return dict(row)


def credentials():
    binary = shutil.which("gh")
    if not binary:
        paths = ([Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "GitHub CLI/gh.exe"]
                 if is_windows() else [Path("/opt/homebrew/bin/gh"), Path("/usr/local/bin/gh")])
        binary = next((str(p) for p in paths if p.is_file()), None)
    if not binary:
        raise ValueError("Installa GitHub CLI e accedi. La proposta è salvata su questo computer.")
    result = subprocess.run([binary, "auth", "token", "--hostname", "github.com"],
                            capture_output=True, text=True, timeout=8, stdin=subprocess.DEVNULL,
                            env={**os.environ, "GH_PROMPT_DISABLED":"1"}, **process_options())
    token = result.stdout.strip()
    if result.returncode or not token:
        raise ValueError(AUTH_HELP)
    return {"Authorization":"Bearer " + token, "Accept":"application/vnd.github+json"}


def update(key, state, detail="", number=None, account=None, delay=0):
    with database() as db:
        db.execute("""UPDATE suggestions SET state=?, detail=?, number=COALESCE(?,number),
                   account=COALESCE(?,account), retry_at=? WHERE id=?""",
                   (state, detail, number, account, time.time()+delay, key))


def find_receipt(row, headers):
    # A creation can succeed even if the POST response never arrives.
    # Never repeat that POST. Search only issues by the recorded sender.
    params = {"q": f'repo:{REPO} is:issue author:{row["account"]} in:body "{row["id"]}"'}
    response = requests.get("https://api.github.com/search/issues", params=params, headers=headers,
                            timeout=12, allow_redirects=False)
    response.raise_for_status()
    marker = "\nID proposta: " + row["id"] + "\n"
    for item in response.json()["items"]:
        if (item.get("repository_url") == API and marker in (item.get("body") or "").replace("\r\n","\n")
                and item.get("user", {}).get("login") == row["account"]):
            return item["number"]


def deliver(row):
    uncertain = row["state"] == "checking"
    try:
        headers = credentials()
        if uncertain:
            number = find_receipt(row, headers)
            if number:
                update(row["id"], "sent", number=number)
            else:
                update(row["id"], "checking", NO_RECEIPT, delay=180)
            return
        me = requests.get("https://api.github.com/user", headers=headers, timeout=12, allow_redirects=False)
        if me.status_code == 401:
            raise ValueError(AUTH_HELP)
        me.raise_for_status()
        account = me.json()["login"]
        with database() as db:
            claim = db.execute("""UPDATE suggestions SET state='checking',detail=?,account=?,retry_at=?
                               WHERE id=? AND state='queued'""",
                               ("Attendo conferma da GitHub.", account, time.time()+180, row["id"]))
            if not claim.rowcount:
                return
        uncertain = True
        response = requests.post(API + "/issues", json=issue_content(row), headers=headers,
                                 timeout=20, allow_redirects=False)
        if response.status_code == 201:
            number = response.json()["number"]
            if type(number) is not int or number < 1:
                raise ValueError("GitHub non ha restituito il numero della proposta.")
            update(row["id"], "sent", number=number)
        elif response.status_code in (401,403,404,410,422,429):
            update(row["id"], "queued", f"GitHub ha rifiutato l’invio (HTTP {response.status_code}). "
                   "Controlla accesso al repository, permessi sulle issue e limiti dell’account.", delay=300)
        else:
            update(row["id"], "checking", "Risposta incerta. Cerco la proposta su GitHub.", delay=60)
    except (ValueError, KeyError, OSError, requests.RequestException, subprocess.SubprocessError) as exc:
        detail = str(exc) if type(exc) is ValueError and not uncertain else (
            "Verifica della consegna in corso." if uncertain else "GitHub non disponibile. Riprovo automaticamente.")
        update(row["id"], "checking" if uncertain else "queued", detail, delay=60)


def tick():
    with LOCK:
        with database() as db:
            row = db.execute("""SELECT * FROM suggestions WHERE state IN ('queued','checking') AND retry_at<=?
                             ORDER BY retry_at,created LIMIT 1""",(time.time(),)).fetchone()
        if row is not None:
            deliver(row)
        return row is not None


def resend(key):
    with LOCK, database() as db:
        changed = db.execute("""UPDATE suggestions SET
                         state=CASE state WHEN 'bridge_check' THEN 'handoff' ELSE 'queued' END,
                         retry_at=0,detail='' WHERE id=? AND state IN ('checking','bridge_check')
                         AND detail=?""", (key,NO_RECEIPT))
        if not changed.rowcount:
            raise ValueError("Attendi il termine della verifica della consegna.")
    WAKE.set()


def retry(key):
    with database() as db:
        if not db.execute("UPDATE suggestions SET retry_at=0 WHERE id=?", (key,)).rowcount:
            raise FileNotFoundError()
    WAKE.set()


def start():
    global THREAD
    STOP.clear()
    def loop():
        while not STOP.is_set():
            try:
                if tick():
                    continue
            except sqlite3.Error:
                pass
            WAKE.wait(20)
            WAKE.clear()
    THREAD = threading.Thread(target=loop, name="cliplab-suggestions", daemon=True)
    THREAD.start()


def stop():
    STOP.set()
    WAKE.set()
    if THREAD:
        THREAD.join(timeout=2)


def bridge_next():
    """Claim one local submission before transmission. Only the first claimant may POST."""
    if not via_codex():
        return None
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT * FROM suggestions WHERE state IN ('handoff','bridge_check')
                         AND retry_at<=? ORDER BY retry_at,created LIMIT 1""", (time.time(),)).fetchone()
        if row is None:
            return None
        action = "create" if row["state"] == "handoff" else "find"
        db.execute("""UPDATE suggestions SET state='bridge_check',retry_at=?,detail=? WHERE id=?""",
                   (time.time()+300,"Verifica della consegna tramite Codex.",row["id"]))
        return {"action":action, "id":row["id"], "repository":REPO, **issue_content(row)}


def bridge_confirm(key, issue):
    with database() as db:
        row = db.execute("SELECT * FROM suggestions WHERE id=?", (key,)).fetchone()
        number = issue.get("number")
        if (not via_codex() or not row or row["state"] not in ("bridge_check","sent")
                or type(number) is not int or number < 1 or issue.get("url") != f"{API}/issues/{number}"
                or issue.get("user", {}).get("id") != OWNER_ID or "pull_request" in issue
                or "\nID proposta: "+key+"\n" not in (issue.get("body") or "").replace("\r\n","\n")):
            raise ValueError("Ricevuta GitHub non valida.")
        db.execute("UPDATE suggestions SET state='sent',number=?,detail='' WHERE id=?", (number,key))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("bridge-next")
    commands.add_parser("bridge-missing").add_argument("key")
    commands.add_parser("bridge-confirm").add_argument("key")
    args = parser.parse_args()
    if args.action == "bridge-next":
        print(json.dumps(bridge_next(), ensure_ascii=False))
    elif args.action == "bridge-missing":
        with database() as db:
            db.execute("UPDATE suggestions SET detail=? WHERE id=? AND state='bridge_check'", (NO_RECEIPT,args.key))
    else:
        bridge_confirm(args.key, json.load(sys.stdin))
