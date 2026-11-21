"""Editable captions and readable, single-word highlighting. All timings are source seconds."""
import math
import re
import uuid


def timestamp(seconds, ass=False):
    scale = 100 if ass else 1000
    whole, part = divmod(max(0, round(seconds * scale)), scale)
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{secs:02}.{part:02}" if ass else f"{hours:02}:{minutes:02}:{secs:02},{part:03}"


def words_from_segments(segments):
    result = []
    for segment in segments:
        words = segment.get("words")
        if words:
            result.extend(dict(w) for w in words if w.get("word", "").strip())
        else:
            tokens = segment["text"].split()
            for i, token in enumerate(tokens):
                span = (segment["end"] - segment["start"]) / max(1, len(tokens))
                result.append({"start": segment["start"] + i * span, "end": segment["start"] + (i+1)*span, "word": token})
    return result


def make_cues(segments, start, end, max_words=5, max_chars=30):
    groups, group = [], []
    for word in words_from_segments(segments):
        a, b = max(start, word["start"]), min(end, word["end"])
        if b <= a:
            continue
        word = {"start": round(a, 3), "end": round(b, 3), "word": word["word"].strip()}
        length = len(" ".join(w["word"] for w in group)) + len(word["word"]) + 1
        if group and (len(group) >= max_words or length > max_chars or b-group[0]["start"] > 2.8 or a-group[-1]["end"] > .6):
            groups.append(group)
            group = []
        group.append(word)
        if re.search(r"[.!?…]$", word["word"]):
            groups.append(group)
            group = []
    if group:
        groups.append(group)
    return [{"id": uuid.uuid4().hex[:10], "start": g[0]["start"], "end": g[-1]["end"],
             "text": " ".join(w["word"] for w in g), "words": g} for g in groups]


def estimate_words(text, start, end):
    tokens=text.split()
    if not tokens:return []
    weights=[max(1,len(token)) for token in tokens]
    unit,cursor=(end-start)/sum(weights),start
    words=[]
    for token,weight in zip(tokens,weights):
        next_time=cursor+unit*weight
        words.append({'word':token,'start':cursor,'end':next_time})
        cursor=next_time
    words[-1]['end']=end
    return words


def validate_cues(cues, duration):
    if not isinstance(cues, list) or len(cues) > 1500:
        raise ValueError("La traccia può contenere al massimo 1500 sottotitoli.")
    result, previous = [], 0
    for cue in sorted(cues, key=lambda c: float(c["start"])):
        a, b = float(cue["start"]), float(cue["end"])
        text = re.sub(r"\s+", " ", str(cue["text"])).strip()
        if not text:
            continue
        if not all(math.isfinite(x) for x in (a,b)) or not 0 <= a < b <= duration+.01 or a < previous-.01:
            raise ValueError("I sottotitoli devono avere tempi validi, senza sovrapposizioni.")
        if len(text) > 160:
            raise ValueError("Dividi il sottotitolo: massimo 160 caratteri per blocco.")
        original = cue.get("words") or []
        estimated=bool(cue.get('timing_estimated'))
        if " ".join(w.get("word", "") for w in original) == text and all(a-.01 <= float(w["start"]) < float(w["end"]) <= b+.01 for w in original):
            words = original
        else:
            # A manual rewrite has no forced alignment: distribute timings explicitly.
            words = estimate_words(text,a,b)
            estimated=True
        item={"id": cue.get("id", uuid.uuid4().hex[:10]), "start": a, "end": b, "text": text, "words": words}
        if estimated:item['timing_estimated']=True
        result.append(item)
        previous = b
    return result


def merge_ranges(ranges):
    merged = []
    for a,b in sorted(ranges):
        if b <= a:continue
        if merged and a <= merged[-1][1]:merged[-1][1] = max(b,merged[-1][1])
        else:merged.append([a,b])
    return merged


def uncovered(start, end, ranges):
    cursor = start
    for a,b in merge_ranges(ranges):
        if a > cursor:yield cursor,min(a,end)
        cursor = max(cursor,b)
        if cursor >= end:return
    if cursor < end:yield cursor,end


def slice_cue(cue, start, end):
    a,b = max(start,cue['start']),min(end,cue['end'])
    if b <= a:return None
    partial=a>cue['start'] or b<cue['end']
    original=cue.get('words') or []
    estimated=partial and not original
    if estimated:original=estimate_words(cue['text'],cue['start'],cue['end'])
    candidates=[w for w in original if w['end']>a and w['start']<b]
    if partial and (estimated or cue.get('timing_estimated')):
        selected=[w for w in candidates if a <= (w['start']+w['end'])/2 < b]
        # A cut through a single inferred word has no finer text alignment.
        candidates=selected or sorted(candidates,key=lambda w:min(b,w['end'])-max(a,w['start']),reverse=True)[:1]
    words = [dict(w,start=max(a,w['start']),end=min(b,w['end'])) for w in candidates]
    if partial and not words:return None
    text = ' '.join(w['word'] for w in words) if partial else cue['text']
    result=dict(cue,start=a,end=b,text=text,words=words)
    if estimated:result['timing_estimated']=True
    return result


def saved_ranges(clip):
    if 'caption_ranges' in clip:return clip['caption_ranges']
    # Older projects did not record the edited interval. Infer its spoken span.
    cues = clip.get('caption_cues',[])
    return [[min(c['start'] for c in cues),max(c['end'] for c in cues)]] if cues else [[clip['start'],clip['end']]]


def store_track(clip, cues, start, end):
    """Replace the reviewed region while retaining edits outside it, including silence."""
    reviewed = merge_ranges([[start,end],*[[c['start'],c['end']] for c in cues]])
    retained = []
    for cue in clip.get('caption_cues',[]):
        for a,b in uncovered(cue['start'],cue['end'],reviewed):
            if part:=slice_cue(cue,a,b):retained.append(part)
    return {'caption_cues':sorted(retained+list(cues),key=lambda c:c['start']),
            'caption_ranges':merge_ranges([*(saved_ranges(clip) if 'caption_cues' in clip else []),*reviewed])}


def track(project, clip, start, end, max_words=5):
    if 'caption_cues' not in clip:
        return make_cues(project['segments'],start,end,max_words=max_words)
    cues = [part for cue in clip['caption_cues'] if (part := slice_cue(cue,start,end))]
    # Do not regenerate intentionally deleted captions inside a reviewed interval.
    for a,b in uncovered(start,end,saved_ranges(clip)):
        cues.extend(make_cues(project['segments'],a,b,max_words=max_words))
    return sorted(cues,key=lambda c:c['start'])


def render(cues, start, end, width, height, style="karaoke", font_scale=1, bottom=22, color="#d3ff5f"):
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Colore dei sottotitoli non valido.")
    clean = lambda text: re.sub(r"[{}\\\r\n]", "", text)
    bgr = color[5:7] + color[3:5] + color[1:3]
    size = round(width * (.057 if width < height else .038) * font_scale)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,100,100,0,0,1,{max(2,round(width*.004))},1,2,{round(width*.08)},{round(width*.08)},{round(height*bottom/100)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events, srt = [], []
    for cue in cues:
        a, b = max(start,cue["start"]), min(end,cue["end"])
        if b <= a:
            continue
        srt.append(f"{len(srt)+1}\n{timestamp(a-start)} --> {timestamp(b-start)}\n{cue['text']}\n")
        words = [w for w in cue.get("words", []) if w["end"] > a and w["start"] < b]
        if style != "karaoke" or not words:
            events.append(f"Dialogue: 0,{timestamp(a-start,True)},{timestamp(b-start,True)},Default,,0,0,0,,{clean(cue['text'])}")
            continue
        boundaries = sorted({a,b,*[max(a,min(b,w[k])) for w in words for k in ("start","end")]})
        for left,right in zip(boundaries,boundaries[1:]):
            if right-left < .015:
                continue
            at=(left+right)/2
            display=" ".join(("{\\1c&H"+bgr+"&}"+clean(w["word"])+"{\\1c&HFFFFFF&}" if w["start"] <= at < w["end"] else clean(w["word"])) for w in words)
            events.append(f"Dialogue: 0,{timestamp(left-start,True)},{timestamp(right-start,True)},Default,,0,0,0,,{display}")
    return "\n".join(srt), header+"\n".join(events)
