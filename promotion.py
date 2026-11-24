"""Local headline suggestions and relevant tags using the public Google Trends RSS."""
import re
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from email.utils import parsedate_to_datetime

import requests
import captions

FEED = "https://trends.google.com/trending/rss?geo=IT"
LOCK = threading.Lock()
CACHE = None
RETRY_AT = 0
STOP = set(("come cosa questo questa questi queste quello quella sono siamo stato stata stati avere aveva "
            "della delle degli dalla dalle allo alla alle nello nella nelle sono anche quindi proprio "
            "perche perché quando tutto tutti sempre molto ancora video parte clip minuti secondi "
            "with this that what when where which have will were your about from they their there "
            "il lo la gli le un uno una di da in con su per tra fra e che non si ma del nel al "
            "the and for you").split())


def words(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return [w for w in re.findall(r"[a-z0-9]+", text) if (len(w) > 2 or w.isdigit()) and w not in STOP]


def hashtag(text):
    return "#" + "".join(re.findall(r"[^\W_]+", text, re.UNICODE))[:45]


def trends():
    global CACHE, RETRY_AT
    with LOCK:
        now = time.time()
        if CACHE and now - CACHE["checked_at"] < 600:
            return dict(CACHE)
        if now < RETRY_AT:
            return {"status":"unavailable", "checked_at":None, "topics":[], "source":FEED}
        try:
            with requests.get(FEED, stream=True, timeout=(3, 5), allow_redirects=False) as response:
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError("Feed non disponibile.")
                payload = bytearray()
                for part in response.iter_content(16384):
                    payload.extend(part)
                    if len(payload) > 512000 or time.time() - now > 10:
                        raise ValueError("Feed troppo grande o lento.")
            if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
                raise ValueError("Formato RSS non valido.")
            channel = ET.fromstring(payload).find("channel")
            if channel is None:
                raise ValueError("Feed RSS incompleto.")
            topics = []
            for item in channel.findall("item")[:100]:
                name = (item.findtext("title") or "").strip()
                date = item.findtext("pubDate") or ""
                try:
                    stamp = parsedate_to_datetime(date).timestamp()
                except (ValueError, TypeError, OverflowError):
                    continue
                if name and 0 <= now - stamp <= 86400:
                    topics.append(name[:160])
            CACHE = {"status":"fresh", "checked_at":now, "topics":topics, "source":FEED}
            return dict(CACHE)
        except (requests.RequestException, ET.ParseError, ValueError, OSError):
            RETRY_AT = time.time() + 120
            return {"status":"unavailable", "checked_at":None, "topics":[], "source":FEED}


def headline(text, source_title, index=0):
    candidates = [re.sub(r"\s+", " ", x).strip(" .!?…:;-") for x in re.split(r"(?<=[.!?])\s+|\n", text)]
    candidates = [x for x in candidates if len(words(x)) >= 3]
    focus = max(candidates, key=lambda x: (bool(re.search(r"\d|perch[eé]|errore|segreto|mai", x.lower())),
                                           min(len(x), 80)), default=source_title)
    focus = re.sub(r"[<>\r\n]", "", focus).strip()
    lead = ("Non te lo aspetti: ", "Il momento da rivedere: ", "Aspetta di vedere questo: ")[index % 3]
    room = 100 - len(lead)
    if len(focus) > room:
        focus = focus[:room-1].rsplit(" ", 1)[0] + "…"
    return (lead + (focus or "Il momento della clip"))[:100]


def generate(project, clip, snapshot=None, index=0):
    snapshot = trends() if snapshot is None else snapshot
    text = " ".join(cue["text"] for cue in captions.make_cues(project.get("segments", []), clip["start"], clip["end"]))
    if not text:
        text = clip.get("text") or ""
    context = project["title"] + " " + text
    tokens = set(words(context))
    relevant = [name for name in snapshot["topics"] if words(name) and set(words(name)).issubset(tokens)]
    tags = ["#Shorts"]
    tags.extend(hashtag(name) for name in relevant[:2])
    # Topic tags remain available offline, without claiming they are trending.
    tags.extend(hashtag(w) for w, _ in Counter(w for w in words(text or project["title"]) if not w.isdigit()).most_common(6))
    unique = {}
    for tag in tags:
        if len(tag) > 1:
            unique.setdefault(tag.casefold(), tag)
    tags = list(unique.values())[:6]
    title = headline(text, project["title"], index)
    if project.get("options", {}).get("mode") == "full":
        suffix = f" · Parte {index+1}"
        title = title[:100-len(suffix)].rstrip() + suffix
    return {"title":title, "hashtags":tags, "description":title + "\n\n" + " ".join(tags),
            "promotion":{"generated_at":time.time(), "trend_checked_at":snapshot["checked_at"],
                         "trend_status":snapshot["status"], "trend_source":snapshot["source"],
                         "trending_hashtags":[hashtag(name) for name in relevant[:2]], "region":"IT"}}


def description(text, tags, limit=5000):
    existing = {x.casefold() for x in re.findall(r"#[^\W_]+", text, re.UNICODE)}
    missing = [tag for tag in tags if tag.casefold() not in existing]
    suffix = " ".join(missing)
    room = max(0, limit - len(suffix) - (2 if suffix else 0))
    return (text[:room].rstrip() + ("\n\n" if suffix and text[:room].strip() else "") + suffix)[:limit]
