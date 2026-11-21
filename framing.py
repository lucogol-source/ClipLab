"""Local face detection, smooth crop keyframes and streaming video composition."""
import bisect
import math
import subprocess
import time
import json
import sys
from pathlib import Path

import cv2
from platform_support import process_options
import numpy as np


def crop_rect(sw, sh, dw, dh, point):
    zoom = max(1, min(3, float(point.get("zoom",1))))
    scale = max(dw/sw, dh/sh)*zoom
    cw, ch = dw/scale, dh/scale
    x = max(0,min(sw-cw,(sw-cw)*float(point.get("x",50))/100))
    y = max(0,min(sh-ch,(sh-ch)*float(point.get("y",50))/100))
    return x,y,cw,ch


def interpolate(points, t, fallback):
    if not points:
        return fallback
    index=bisect.bisect_right([p["t"] for p in points],t)
    if index==0:return points[0]
    if index>=len(points):return points[-1]
    a,b=points[index-1],points[index]
    ratio=(t-a["t"])/max(.001,b["t"]-a["t"])
    if b.get("cut"):
        return a
    ratio=ratio*ratio*(3-2*ratio)
    return {k:a[k]+(b[k]-a[k])*ratio for k in ("x","y","zoom")}


def analyze_faces(path,start,end,aspect,model,subject="largest",cancel=lambda:None):
    if not Path(model).is_file():
        raise ValueError("Modello volti non disponibile. Esegui Aggiorna ClipLab.command.")
    detector=cv2.FaceDetectorYN.create(str(model),"",(640,360),.75,.3,5000)
    points, previous, next_sample, found = [], None, start, 0
    ratio={"9:16":9/16,"1:1":1,"16:9":16/9}[aspect]
    capture=cv2.VideoCapture(str(path))
    if not capture.isOpened():raise ValueError("Impossibile aprire il video per il tracking.")
    capture.set(cv2.CAP_PROP_POS_MSEC,start*1000)
    try:
        while True:
            cancel()
            ok,image=capture.read()
            if not ok:break
            at=capture.get(cv2.CAP_PROP_POS_MSEC)/1000
            if at<next_sample:continue
            if at>=end:break
            next_sample=at+.5
            sh,sw=image.shape[:2]
            scale=640/sw
            small=cv2.resize(image,(640,max(32,round(sh*scale))))
            detector.setInputSize((small.shape[1],small.shape[0]))
            _,faces=detector.detect(small)
            if faces is None:
                point=dict(previous or {"x":50,"y":50,"zoom":1},t=round(at-start,3))
            else:
                faces=sorted(faces,key=lambda f:f[0]+f[2]/2)
                if subject=="left":face=faces[0]
                elif subject=="right":face=faces[-1]
                else:face=max(faces,key=lambda f:f[2]*f[3])
                x,y,w,h=[float(v)/scale for v in face[:4]]
                base_height=min(sh,sw/ratio)
                crop_height=max(base_height/2,min(base_height,h*3.4))
                zoom=max(1,min(2,base_height/crop_height))
                crop_width=crop_height*ratio
                desired_x=x+w/2-crop_width/2
                desired_y=y+h/2-crop_height*.32
                px=max(0,min(100,desired_x/max(1,sw-crop_width)*100))
                py=max(0,min(100,desired_y/max(1,sh-crop_height)*100))
                point={"x":px,"y":py,"zoom":zoom,"t":round(at-start,3)}
                if previous:
                    point.update({k:previous[k]*.65+point[k]*.35 for k in ("x","y","zoom")})
                found+=1
            previous=point
            points.append({k:round(v,3) for k,v in point.items()})
    finally:capture.release()
    if not points:points=[{"t":0,"x":50,"y":50,"zoom":1}]
    return {"keyframes":points,"faces_detected":found,"method":"YuNet · volto predominante" if subject=="largest" else f"YuNet · volto {subject}",
            "notice":None if found else "Nessun volto trovato: mantenuta l’inquadratura centrale. Non è un riconoscimento del parlante tramite audio."}


def compose(image,width,height,settings,at):
    sh,sw=image.shape[:2]
    layout=settings.get("layout","crop")
    point=interpolate(settings.get("keyframes",[]),at,{"x":settings.get("crop",50),"y":settings.get("crop_y",50),"zoom":settings.get("zoom",1)})
    def cropped(dw,dh,p):
        x,y,w,h=crop_rect(sw,sh,dw,dh,p)
        region=image[round(y):max(round(y)+1,round(y+h)),round(x):max(round(x)+1,round(x+w))]
        return cv2.resize(region,(dw,dh),interpolation=cv2.INTER_LINEAR)
    if layout in ("fit","blur"):
        if layout=="blur":
            bg=cropped(96,round(96*height/width),{"x":50,"y":50,"zoom":1})
            bg=cv2.GaussianBlur(bg,(31,31),0)
            canvas=cv2.resize(bg,(width,height))
        else:canvas=np.zeros((height,width,3),dtype=np.uint8)
        scale=min(width/sw,height/sh)
        w,h=max(1,round(sw*scale)),max(1,round(sh*scale))
        canvas[(height-h)//2:(height-h)//2+h,(width-w)//2:(width-w)//2+w]=cv2.resize(image,(w,h))
        return canvas
    if layout=="split":
        half=height//2
        upper=cropped(width,half,{"x":settings.get("split_left",20),"y":settings.get("crop_y",50),"zoom":settings.get("zoom",1)})
        lower=cropped(width,height-half,{"x":settings.get("split_right",80),"y":settings.get("crop_y",50),"zoom":settings.get("zoom",1)})
        return np.concatenate((upper,lower),axis=0)
    return cropped(width,height,point)


def stream_render(source,output,start,end,width,height,settings,ffmpeg,ass_path,cancel=lambda:None,progress=lambda p:None):
    fps=30
    command=[str(ffmpeg),"-y","-ss",str(start),"-i",str(source),"-f","rawvideo","-pix_fmt","bgr24",
             "-s",f"{width}x{height}","-r",str(fps),"-i","pipe:0","-map","1:v:0","-map","0:a:0?",
             "-t",str(end-start)]
    if ass_path:command += ["-vf",f"ass={Path(ass_path).name}"]
    command += ["-c:v","libx264","-preset","fast","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-movflags","+faststart",str(output)]
    log_path=Path(output).with_suffix(".render.log")
    with log_path.open("wb") as log:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,cwd=Path(output).parent,**process_options())
        try:
            target=start
            capture=cv2.VideoCapture(str(source))
            if not capture.isOpened():raise ValueError("Impossibile aprire il video per il rendering.")
            capture.set(cv2.CAP_PROP_POS_MSEC,start*1000)
            try:
                while True:
                    cancel()
                    ok,next_image=capture.read()
                    if not ok:break
                    image=next_image
                    at=capture.get(cv2.CAP_PROP_POS_MSEC)/1000
                    if at<start-.1:continue
                    if target>=end:break
                    while target<=at+.5/fps and target<end:
                        cancel()
                        process.stdin.write(compose(image,width,height,settings,target-start).tobytes())
                        target += 1/fps
                    progress(min(99,round((target-start)/(end-start)*100)))
                while target<end and 'image' in locals():
                    process.stdin.write(compose(image,width,height,settings,target-start).tobytes())
                    target+=1/fps
            finally:capture.release()
            process.stdin.close()
            if process.wait(timeout=120):
                raise RuntimeError("Rendering non riuscito. " + log_path.read_text(errors="replace", encoding='utf-8')[-700:])
        except Exception:
            process.kill()
            process.wait()
            raise


if __name__=="__main__":
    # Separate OpenCV's FFmpeg libraries from PyAV's libraries on macOS.
    action=sys.argv[1]
    config=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    if action=="analyze":
        result=analyze_faces(config["source"],config["start"],config["end"],config["format"],config["model"],config["subject"])
        print(json.dumps(result),flush=True)
    elif action=="render":
        def progress(value):Path(config["progress_file"]).write_text(str(value), encoding='utf-8')
        stream_render(config["source"],config["output"],config["start"],config["end"],config["width"],config["height"],
                      config["settings"],config["ffmpeg"],config["ass_path"],progress=progress)
