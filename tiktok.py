"""Official TikTok Desktop Login Kit + Direct Post, with explicit per-video approval."""
import hashlib
import json
import secrets
import threading
import time
from urllib.parse import urlencode, urlparse

import requests

from engine import project_dir, read_project, update_clip, check_cancel
from youtube import SECRET_DIR, save_secret

CLIENT=SECRET_DIR/"tiktok-client.json"
TOKEN=SECRET_DIR/"tiktok-token.json"
API="https://open.tiktokapis.com/v2"
LOCK=threading.RLock()
PENDING={}
SCOPES="user.info.basic,video.publish"


class PostRejected(ValueError):
    pass


def configure(client_key,client_secret,mode="test"):
    if not client_key.strip() or not client_secret.strip() or mode not in ("test","approved"):
        raise ValueError("Inserisci Client key e Client secret della tua app TikTok Desktop.")
    with LOCK:
        save_secret(CLIENT,{"client_key":client_key.strip(),"client_secret":client_secret.strip(),"mode":mode})
        TOKEN.unlink(missing_ok=True)
        PENDING.clear()


def connection():
    mode=json.loads(CLIENT.read_text(encoding='utf-8')).get("mode","test") if CLIENT.exists() else "test"
    if not TOKEN.exists():return {"configured":CLIENT.exists(),"connected":False,"mode":mode}
    saved=json.loads(TOKEN.read_text(encoding='utf-8'))
    return {"configured":True,"connected":True,"mode":mode,"creator":saved.get("creator",{})}


def auth_url(base):
    if not CLIENT.exists():raise ValueError("Configura prima il client TikTok nelle impostazioni.")
    config=json.loads(CLIENT.read_text(encoding='utf-8'))
    state=secrets.token_urlsafe(30)
    verifier=secrets.token_urlsafe(64)
    redirect=base+"/api/tiktok/callback"
    with LOCK:
        PENDING.clear()
        PENDING[state]={"verifier":verifier,"redirect":redirect,"at":time.time()}
    return "https://www.tiktok.com/v2/auth/authorize/?"+urlencode({"client_key":config["client_key"],"response_type":"code","scope":SCOPES,
            "redirect_uri":redirect,"state":state,"code_challenge":hashlib.sha256(verifier.encode()).hexdigest(),"code_challenge_method":"S256"})


def token_request(data):
    response=requests.post(API+"/oauth/token/",data=data,timeout=30)
    result=response.json()
    if not response.ok or result.get("error"):
        raise ValueError("Autorizzazione TikTok non riuscita. Controlla client, redirect e scope video.publish.")
    return dict(result,expires_at=time.time()+result.get("expires_in",86400))


def finish_auth(state,code):
    with LOCK:pending=PENDING.pop(state,None)
    if not pending or time.time()-pending["at"]>600:raise ValueError("Collegamento TikTok scaduto. Riprova.")
    config=json.loads(CLIENT.read_text(encoding='utf-8'))
    token=token_request({"client_key":config["client_key"],"client_secret":config["client_secret"],"grant_type":"authorization_code",
                         "code":code,"redirect_uri":pending["redirect"],"code_verifier":pending["verifier"]})
    save_secret(TOKEN,token)
    try:return creator_info()
    except Exception:
        TOKEN.unlink(missing_ok=True)
        raise


def access_token():
    with LOCK:
        if not TOKEN.exists():raise ValueError("Collega prima TikTok.")
        token=json.loads(TOKEN.read_text(encoding='utf-8'))
        if token.get("expires_at",0)<time.time()+120:
            config=json.loads(CLIENT.read_text(encoding='utf-8'))
            refreshed=token_request({"client_key":config["client_key"],"client_secret":config["client_secret"],"grant_type":"refresh_token","refresh_token":token["refresh_token"]})
            token.update(refreshed)
            save_secret(TOKEN,token)
        return token["access_token"]


def request(path,body):
    response=requests.post(API+path,json=body,headers={"Authorization":"Bearer "+access_token()},timeout=30)
    data=response.json()
    error=data.get("error",{})
    if not response.ok or error.get("code") not in (None,"ok"):
        code=error.get("code",str(response.status_code))
        raise ValueError(f"TikTok: {code}. "+str(error.get("message","Controlla autorizzazione, quota e approvazione dell’app."))[:250])
    return data.get("data",{})


def creator_info():
    data=request("/post/publish/creator_info/query/",{})
    config=json.loads(CLIENT.read_text(encoding='utf-8'))
    if config.get("mode")!="approved":
        data["privacy_level_options"]=[x for x in data.get("privacy_level_options",[]) if x=="SELF_ONLY"]
    with LOCK:
        token=json.loads(TOKEN.read_text(encoding='utf-8'))
        token["creator"]=data
        save_secret(TOKEN,token)
    return data


def disconnect():
    with LOCK:
        TOKEN.unlink(missing_ok=True)
        PENDING.clear()


def post_status(publish_id):
    result=request("/post/publish/status/fetch/",{"publish_id":publish_id})
    status=result.get("status","")
    if status=="FAILED":raise PostRejected("TikTok ha rifiutato il video: "+str(result.get("fail_reason","non specificato")))
    ids=result.get("publicaly_available_post_id") or result.get("publicly_available_post_id") or []
    return {"publish_id":publish_id,"status":"published" if status=="PUBLISH_COMPLETE" else "processing", "post_id":str(ids[0]) if ids else None}


def validate_post(info,metadata,duration):
    if metadata.get("consent") is not True or metadata.get("music_rights") is not True:
        raise ValueError("Rivedi la clip e conferma l’autorizzazione di pubblicazione e l’uso della musica.")
    privacy=metadata.get("privacy_level")
    if privacy not in info.get("privacy_level_options",[]):raise ValueError("Scegli una visibilità tra quelle consentite dal tuo account TikTok.")
    if duration>info.get("max_video_post_duration_sec",0):raise ValueError("La clip supera la durata consentita dal tuo account TikTok.")
    if metadata.get("brand_content_toggle") and privacy=="SELF_ONLY":raise ValueError("TikTok non consente contenuti sponsorizzati con visibilità Solo io.")


def publish_clip(pid,cid,export_id,metadata):
    p=read_project(pid)
    clip=next(c for c in p["clips"] if c["id"]==cid)
    existing=clip.get("tiktok")
    if existing and existing.get("publish_id"):
        update_clip(pid,cid,status='published' if clip.get('youtube') or existing.get('status')=='published' else 'exported',error=None)
        return existing
    if clip.get("tiktok_uncertain"):raise ValueError("Esito del precedente invio TikTok incerto: verifica l’account prima di riprovare.")
    export=next((e for e in clip["exports"] if e["id"]==export_id),None)
    if not export:raise ValueError("Esporta la clip prima di inviarla a TikTok.")
    settings=export["settings"]
    info=creator_info()
    validate_post(info,metadata,settings["end"]-settings["start"])
    file=project_dir(pid)/export["file"]
    size=file.stat().st_size
    chunk=min(size,32*1024*1024)
    count=max(1,size//chunk)
    post={"title":metadata.get("title",clip["title"])[:1800],"privacy_level":metadata["privacy_level"],
          "disable_comment":bool(info.get("comment_disabled") or not metadata.get("allow_comments")),
          "disable_duet":bool(info.get("duet_disabled") or not metadata.get("allow_duet")),
          "disable_stitch":bool(info.get("stitch_disabled") or not metadata.get("allow_stitch")),
          "brand_content_toggle":bool(metadata.get("brand_content_toggle")),"brand_organic_toggle":bool(metadata.get("brand_organic_toggle")),
          "is_aigc":bool(metadata.get("is_aigc"))}
    attempted=False
    try:
        check_cancel(pid)
        attempted=True
        result=request("/post/publish/video/init/",{"post_info":post,"source_info":{"source":"FILE_UPLOAD","video_size":size,"chunk_size":chunk,"total_chunk_count":count}})
        publish_id=result["publish_id"]
        update_clip(pid,cid,tiktok={"publish_id":publish_id,"status":"uploading","export_id":export_id},status="uploading")
        url=result["upload_url"]
        parsed=urlparse(url)
        if parsed.scheme!="https" or not (parsed.hostname or "").endswith(".tiktokapis.com"):
            raise ValueError("TikTok ha restituito un indirizzo di trasferimento non valido.")
        with file.open("rb") as source:
            for i in range(count):
                check_cancel(pid)
                offset=i*chunk
                payload=source.read(size-offset if i==count-1 else chunk)
                response=requests.put(url,data=payload,headers={"Content-Type":"video/mp4","Content-Length":str(len(payload)),
                    "Content-Range":f"bytes {offset}-{offset+len(payload)-1}/{size}"},timeout=120)
                if response.status_code not in (201,206):raise ValueError(f"Trasferimento TikTok non riuscito (HTTP {response.status_code}).")
        final={"publish_id":publish_id,"status":"processing","export_id":export_id,"creator":info.get("creator_username"),"privacy":metadata["privacy_level"]}
        update_clip(pid,cid,tiktok=final,status="published" if clip.get('youtube') else "exported",error=None)
        return final
    except Exception as error:
        # Never reinitialize a post automatically after a lost response.
        update_clip(pid,cid,tiktok_uncertain=attempted,status="error",error=str(error)[:600])
        raise
