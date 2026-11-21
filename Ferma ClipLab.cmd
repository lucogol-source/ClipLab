@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if not exist ".venv\Scripts\python.exe" (
  echo ClipLab non e ancora installato in questa cartella.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" launch.py stop
if errorlevel 1 pause
