@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if not exist ".venv\Scripts\python.exe" (
  echo Esegui prima Avvia ClipLab.cmd.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" windows_setup.py --check
pause
