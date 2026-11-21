@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
set "CLIPLAB_DIR=%CD%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if /I "%PROCESSOR_ARCHITECTURE%"=="AMD64" goto architecture_ok
if /I "%PROCESSOR_ARCHITEW6432%"=="AMD64" goto architecture_ok
echo Questa versione richiede Windows x64 su processore Intel o AMD.
echo Windows 32 bit e ARM nativo non sono inclusi in questo pacchetto.
exit /b 1
:architecture_ok
if not exist ".venv\Scripts\python.exe" goto install
".venv\Scripts\python.exe" -c "import fastapi,faster_whisper,yt_dlp,imageio_ffmpeg,googleapiclient,cv2,filelock" >nul 2>&1
if errorlevel 1 goto install
if not errorlevel 0 goto install
goto ready
:install
echo Prima installazione: scarico Python e i componenti gratuiti nella cartella di ClipLab.
if not exist ".tools\uv.exe" (
  powershell.exe -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; $tools=Join-Path $env:CLIPLAB_DIR '.tools'; New-Item -ItemType Directory -Force -Path $tools | Out-Null; $zip=Join-Path $tools 'uv.zip'; Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile $zip; Expand-Archive -LiteralPath $zip -DestinationPath $tools -Force; Remove-Item -LiteralPath $zip"
  if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
)
if not exist ".tools\uv.exe" (
  echo Download di uv non completato. Controlla la connessione e riprova.
  exit /b 1
)
set "UV_CACHE_DIR=%CLIPLAB_DIR%\.cache\uv"
set "UV_PYTHON_INSTALL_DIR=%CLIPLAB_DIR%\.runtime"
set "UV_PYTHON_BIN_DIR=%CLIPLAB_DIR%\.tools\bin"
set "UV_PYTHON_PREFERENCE=only-managed"
if not exist "%UV_PYTHON_BIN_DIR%" mkdir "%UV_PYTHON_BIN_DIR%"
".tools\uv.exe" python install 3.12
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
".tools\uv.exe" venv --python 3.12 --allow-existing .venv
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
".tools\uv.exe" pip install --python ".venv\Scripts\python.exe" --only-binary :all: -r requirements-windows.lock.txt
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
:ready
".venv\Scripts\python.exe" windows_setup.py
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
exit /b 0
