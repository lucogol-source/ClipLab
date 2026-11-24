"""Durable local publishing queue. Only explicitly approved rendered files are sent."""
import json
import sqlite3
import threading
import time
import uuid

import engine
import promotion

DB=engine.DATA/"publishing.sqlite3"
STOP=threading.Event()
WAKE=threading.Event()
THREAD=None
TICK_LOCK=threading.Lock()


def database():
    c=sqlite3.connect(DB,timeout=15)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""CREATE TABLE IF NOT EXISTS jobs(
      id TEXT PRIMARY KEY,batch TEXT NOT NULL,platform TEXT NOT NULL,pid TEXT NOT NULL,cid TEXT NOT NULL,
      export_id TEXT NOT NULL,revision INTEGER NOT NULL,scheduled REAL NOT NULL,spacing REAL NOT NULL,
      status TEXT NOT NULL,payload TEXT NOT NULL,result TEXT,error TEXT,completed REAL,created REAL NOT NULL);
      CREATE INDEX IF NOT EXISTS jobs_due ON jobs(status,scheduled);
      CREATE TABLE IF NOT EXISTS preferences(id INTEGER PRIMARY KEY CHECK(id=1),paused INTEGER NOT NULL DEFAULT 0);
      INSERT OR IGNORE INTO preferences(id,paused) VALUES(1,0);""")
    return c


def list_jobs():
    with database() as c:
        rows=c.execute("SELECT * FROM jobs ORDER BY scheduled DESC LIMIT 300").fetchall()
        paused=bool(c.execute("SELECT paused FROM preferences WHERE id=1").fetchone()[0])
    jobs=[]
    for row in rows:
        job=dict(row)
        job["payload"]=json.loads(job["payload"])
        job["result"]=json.loads(job["result"]) if job["result"] else None
        jobs.append(job)
    return {"jobs":jobs,"paused":paused,"local":True,"requires_mac_awake":True}


def pause(value):
    with database() as c:c.execute("UPDATE preferences SET paused=? WHERE id=1",(bool(value),))
    WAKE.set()


def invalidate_clip(pid,cid):
    with database() as c:
        c.execute("UPDATE jobs SET status='blocked',error=? WHERE pid=? AND cid=? AND status='queued'",
                  ("Clip modificata: riesporta e riprogramma per approvare la nuova versione.",pid,cid))


def schedule(pid,clip_ids,platforms,start_at,interval_hours,metadata):
    if start_at<time.time()-60 or not .25<=interval_hours<=720:
        raise ValueError("Scegli una data futura e un intervallo tra 15 minuti e 30 giorni.")
    if not clip_ids or len(clip_ids)>40 or len(set(clip_ids))!=len(clip_ids):raise ValueError("Seleziona da 1 a 40 clip distinte.")
    if not platforms or any(p not in ("youtube","tiktok") for p in platforms):raise ValueError("Scegli YouTube o TikTok.")
    if metadata.get("approved") is not True:raise ValueError("Conferma di aver rivisto le clip e autorizzato la pubblicazione.")
    if "youtube" in platforms and metadata.get("youtube_privacy","private") not in ("private","public","unlisted"):
        raise ValueError("Visibilità YouTube non valida.")
    import youtube,tiktok
    yt=youtube.connection()
    if "youtube" in platforms and (not yt["connected"] or metadata.get("youtube_channel")!=yt["channel"]["id"]):
        raise ValueError("Collega e seleziona il canale YouTube.")
    tt=tiktok.creator_info() if "tiktok" in platforms else None
    project=engine.read_project(pid)
    records=[]
    batch=uuid.uuid4().hex
    for i,cid in enumerate(clip_ids):
        clip=next((c for c in project["clips"] if c["id"]==cid),None)
        if not clip or not clip["exports"]:raise ValueError("Esporta tutte le clip selezionate prima di programmare.")
        export=clip["exports"][-1]
        revision=clip.get("edit_revision",0)
        if export.get("edit_revision",0)!=revision:raise ValueError("Una clip è stata modificata: riesportala prima di programmare.")
        for platform in set(platforms):
            if clip.get(platform):raise ValueError("Una delle clip è già stata inviata alla piattaforma scelta.")
            payload=dict(metadata,title=metadata.get("titles",{}).get(cid,clip["title"]))
            payload["hashtags"] = clip.get("hashtags", [])
            payload["description"] = promotion.description(metadata.get("description") or clip.get("description", ""),
                                                            payload["hashtags"])
            if platform=="tiktok":tiktok.validate_post(tt,payload,export["settings"]["end"]-export["settings"]["start"])
            records.append((uuid.uuid4().hex,batch,platform,pid,cid,export["id"],revision,start_at+i*interval_hours*3600,
                            interval_hours*3600,"queued",json.dumps(payload),time.time()))
    with database() as c:
        for record in records:
            if c.execute("SELECT 1 FROM jobs WHERE pid=? AND cid=? AND platform=? AND status IN ('queued','running','processing','published','unknown')",(record[3],record[4],record[2])).fetchone():
                raise ValueError("Una clip è già in coda per questa piattaforma.")
        c.executemany("INSERT INTO jobs(id,batch,platform,pid,cid,export_id,revision,scheduled,spacing,status,payload,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",records)
    WAKE.set()
    return {"scheduled":len(records),"batch":batch}


def cancel(job_id):
    with database() as c:
        changed=c.execute("UPDATE jobs SET status='cancelled' WHERE id=? AND status IN ('queued','blocked','failed')",(job_id,)).rowcount
    if not changed:raise ValueError("Il lavoro è già in invio o completato.")


def set_status(job_id,status,result=None,error=None):
    with database() as c:c.execute("UPDATE jobs SET status=?,result=?,error=?,completed=? WHERE id=?",
                (status,json.dumps(result) if result is not None else None,error,time.time() if status in ("published","processing") else None,job_id))


def eligible(job,last_sent,now):
    return job["scheduled"]<=now and (last_sent is None or now>=last_sent+job["spacing"])


def tick():
    if not TICK_LOCK.acquire(blocking=False):return
    try:
        _tick()
    finally:
        TICK_LOCK.release()


def _tick():
    import tiktok
    with database() as c:
        processing=c.execute("SELECT * FROM jobs WHERE status='processing' AND platform='tiktok'").fetchall()
    for row in processing:
        job=dict(row)
        claimed=False
        try:
            engine.claim_clip(job['pid'],job['cid'])
            claimed=True
            import tiktok
            result=tiktok.post_status(json.loads(job["result"])["publish_id"])
            if result["status"]=="published":
                clip=next(x for x in engine.read_project(job["pid"])["clips"] if x["id"]==job["cid"])
                engine.update_clip(job["pid"],job["cid"],tiktok=dict(clip.get("tiktok",{}),**result),status='published',error=None)
                set_status(job["id"],"published",result)
        except engine.ClipBusy:
            continue
        except Exception as error:
            if isinstance(error,tiktok.PostRejected):
                set_status(job["id"],"failed",error=str(error)[:500])
                continue
            # Polling is read-only and may safely resume after a transient failure.
            with database() as c:c.execute("UPDATE jobs SET error=? WHERE id=?",(str(error)[:500],job["id"]))
        finally:
            if claimed:engine.release_clip(job['pid'],job['cid'])
    with database() as c:
        if c.execute("SELECT paused FROM preferences WHERE id=1").fetchone()[0]:return
        rows=c.execute("SELECT * FROM jobs WHERE status='queued' AND scheduled<=? ORDER BY scheduled",(time.time(),)).fetchall()
        candidates=[]
        for row in rows:
            last=c.execute("SELECT MAX(completed) FROM jobs WHERE batch=? AND platform=? AND status IN ('published','processing')",(row["batch"],row["platform"])).fetchone()[0]
            if eligible(row,last,time.time()):candidates.append(dict(row))
    for job in candidates:
        try:
            engine.claim_clip(job['pid'],job['cid'])
        except engine.ClipBusy:
            continue  # Keep the schedule queued while an editor task owns the clip.
        except Exception as error:
            set_status(job['id'],'failed',error=str(error)[:700])
            continue
        try:
            with database() as c:
                if c.execute('SELECT paused FROM preferences WHERE id=1').fetchone()[0]:return
                changed=c.execute("UPDATE jobs SET status='running' WHERE id=? AND status='queued'",(job['id'],)).rowcount
            if not changed:continue
            send(job)
            return
        finally:
            engine.release_clip(job['pid'],job['cid'])


def send(job):
    try:
        project=engine.read_project(job["pid"])
        clip=next(c for c in project["clips"] if c["id"]==job["cid"])
        if clip.get("edit_revision",0)!=job["revision"]:
            set_status(job["id"],"blocked",error="Clip modificata dopo l’approvazione. Riesporta e riprogramma.")
            return
        payload=json.loads(job["payload"])
        if job["platform"]=="youtube":
            import youtube
            result=youtube.upload_clip(job["pid"],job["cid"],payload["youtube_channel"],payload.get("youtube_privacy","private"),
                                       payload.get("made_for_kids",False),payload["title"],payload.get("description","#Shorts"),job["export_id"])
            set_status(job["id"],"published",result)
        else:
            import tiktok
            result=tiktok.publish_clip(job["pid"],job["cid"],job["export_id"],payload)
            set_status(job["id"],result["status"],result)
    except Exception as error:
        try:
            clip=next(c for c in engine.read_project(job["pid"])["clips"] if c["id"]==job["cid"])
            uncertain=clip.get("upload_uncertain") or clip.get("tiktok_uncertain")
        except Exception:uncertain=True
        set_status(job["id"],"unknown" if uncertain else "failed",error=str(error)[:700])


def start():
    global THREAD
    with database() as c:
        c.execute("UPDATE jobs SET status='unknown',error='Invio interrotto dal riavvio: verifica la piattaforma prima di riprogrammare.' WHERE status='running'")
    STOP.clear()
    def loop():
        while not STOP.is_set():
            try:tick()
            except Exception:pass
            WAKE.wait(15)
            WAKE.clear()
    THREAD=threading.Thread(target=loop,name="cliplab-publishing",daemon=True)
    THREAD.start()


def stop():
    STOP.set()
    WAKE.set()
    if THREAD:THREAD.join(timeout=2)
