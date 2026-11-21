@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
call "Configura ClipLab.cmd"
if errorlevel 1 goto failed
if not errorlevel 0 goto failed
echo Preparo i modelli gratuiti Small e volti. Il primo download puo richiedere tempo.
".venv\Scripts\python.exe" prepare_models.py --small
if errorlevel 1 goto failed
if not errorlevel 0 goto failed
echo Modelli pronti. Questo comando non aggiorna il codice dell'app.
pause
exit /b 0
:failed
echo Preparazione non completata. Consulta README.txt.
pause
exit /b 1
