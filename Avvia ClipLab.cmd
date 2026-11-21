@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
echo ClipLab - studio di clipping gratuito sul tuo PC Windows
call "Configura ClipLab.cmd"
if errorlevel 1 goto failed
if not errorlevel 0 goto failed
".venv\Scripts\python.exe" prepare_models.py
if errorlevel 1 goto failed
if not errorlevel 0 goto failed
".venv\Scripts\python.exe" launch.py start
if errorlevel 1 goto failed
if not errorlevel 0 goto failed
exit /b 0
:failed
echo.
echo Avvio non completato. Consulta README.txt e conserva il messaggio di errore.
echo Se compare DLL load failed, installa Microsoft Visual C++ Redistributable x64.
echo Link ufficiale: https://aka.ms/vc14/vc_redist.x64.exe
pause
exit /b 1
