"""Install a local Node runtime and diagnose the Windows installation."""
import argparse
import importlib
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import requests

from platform_support import is_windows, process_options
from prepare_models import download

ROOT=Path(__file__).resolve().parent
NODE_BASE='https://nodejs.org/dist/latest-v22.x/'
VC_RUNTIME='https://aka.ms/vc14/vc_redist.x64.exe'


def node_version(executable):
    result=subprocess.run([str(executable),'--version'],capture_output=True,text=True,encoding='utf-8',
                          errors='replace',timeout=10,check=True,**process_options())
    match=re.fullmatch(r'v(\d+)\.\d+\.\d+\s*',result.stdout)
    if not match or int(match[1])<22:raise ValueError('È necessario Node.js 22 o successivo.')
    return result.stdout.strip()


def ensure_node(root=ROOT):
    tools=Path(root)/'.tools';tools.mkdir(parents=True,exist_ok=True)
    node=tools/'node.exe'
    if node.exists():
        try:
            node_version(node)
            return node
        except (OSError,ValueError,subprocess.SubprocessError):pass
    print('Preparo Node.js locale gratuito per i link YouTube…',flush=True)
    response=requests.get(NODE_BASE+'SHASUMS256.txt',timeout=30)
    response.raise_for_status()
    match=re.search(r'^([a-f0-9]{64})\s+(node-v22\.\d+\.\d+-win-x64\.zip)\s*$',response.text,re.M)
    if not match:raise ValueError('Elenco ufficiale Node.js non riconosciuto. Riprova più tardi.')
    digest,filename=match.groups()
    archive_path=tools/'node-runtime.zip'
    download(NODE_BASE+filename,archive_path,digest)
    prefix=filename.removesuffix('.zip')+'/'
    with zipfile.ZipFile(archive_path) as archive:
        # Extract named files only; no archive-controlled destination paths.
        for member,destination in (('node.exe',node),('LICENSE',tools/'NODE-LICENSE.txt')):
            temporary=destination.with_suffix(destination.suffix+'.part')
            with archive.open(prefix+member) as source,temporary.open('wb') as output:
                shutil.copyfileobj(source,output)
            temporary.replace(destination)
    archive_path.unlink()
    node_version(node)
    return node


def diagnose(root=ROOT):
    print('Controllo dei componenti locali:',flush=True)
    for name in ('fastapi','yt_dlp','faster_whisper','ctranslate2','onnxruntime','av','cv2','filelock','googleapiclient'):
        importlib.import_module(name)
        print('  OK '+name,flush=True)
    import imageio_ffmpeg
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    result=subprocess.run([ffmpeg,'-version'],capture_output=True,text=True,encoding='utf-8',errors='replace',
                          check=True,timeout=15,**process_options())
    print('  OK '+result.stdout.splitlines()[0],flush=True)
    print('  OK Node.js '+node_version(Path(root)/'.tools/node.exe'),flush=True)
    print('Diagnostica completata. Nessuna credenziale è stata letta o mostrata.',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if not is_windows() or struct.calcsize('P')!=8:
        raise ValueError('Questa configurazione richiede Python Windows x64.')
    if not args.check:ensure_node()
    diagnose()


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('\nConfigurazione Windows non completata: '+str(error),file=sys.stderr)
        print('Se compare DLL load failed, installa Microsoft Visual C++ Redistributable x64:\n'+VC_RUNTIME,file=sys.stderr)
        print('Poi riapri Avvia ClipLab.cmd. Consulta README.txt.',file=sys.stderr)
        sys.exit(1)
