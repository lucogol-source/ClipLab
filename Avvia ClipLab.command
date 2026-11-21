#!/bin/zsh
set -eu
setopt NO_BG_NICE
cd -- "$(dirname -- "$0")"
CLIPLAB_DIR="$PWD"
CLIPLAB_PORT="${CLIPLAB_PORT:-8765}"
export CLIPLAB_PORT
print '\nClipLab · studio di clipping gratuito sul tuo Mac\n'
if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c 'import fastapi, faster_whisper, yt_dlp, imageio_ffmpeg, googleapiclient, cv2' >/dev/null 2>&1; then
  print 'Prima configurazione: scarico Python e i componenti gratuiti nella cartella di ClipLab.'
  CLIPLAB_UV="$(command -v uv || true)"
  if [[ -z "$CLIPLAB_UV" && -x "$HOME/.local/bin/uv" ]]; then
    CLIPLAB_UV="$HOME/.local/bin/uv"
  fi
  if [[ -z "$CLIPLAB_UV" ]]; then
    mkdir -p .tools
    if [[ "$(uname -m)" == arm64 ]]; then CLIPLAB_ARCH=aarch64; else CLIPLAB_ARCH=x86_64; fi
    /usr/bin/curl -fL --retry 2 "https://github.com/astral-sh/uv/releases/latest/download/uv-$CLIPLAB_ARCH-apple-darwin.tar.gz" -o .tools/uv.tar.gz
    /usr/bin/tar -xzf .tools/uv.tar.gz -C .tools
    CLIPLAB_UV="$CLIPLAB_DIR/.tools/uv-$CLIPLAB_ARCH-apple-darwin/uv"
  fi
  export UV_CACHE_DIR="$CLIPLAB_DIR/.cache/uv"
  export UV_PYTHON_INSTALL_DIR="$CLIPLAB_DIR/.runtime"
  export UV_PYTHON_BIN_DIR="$CLIPLAB_DIR/.tools/bin"
  mkdir -p "$UV_PYTHON_BIN_DIR"
  "$CLIPLAB_UV" python install 3.12
  "$CLIPLAB_UV" venv --python 3.12 --allow-existing .venv
  "$CLIPLAB_UV" pip install --python .venv/bin/python -r requirements.lock.txt
fi
.venv/bin/python prepare_models.py
exec .venv/bin/python launch.py start
