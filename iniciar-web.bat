@echo off
setlocal
chcp 65001 >nul
title Wendel Dev - Mesa de midia
cd /d "%~dp0"
set "WENDEL_MODE=web"
set "PORT=8000"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
    echo Abrindo http://127.0.0.1:8000
    ".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
    goto :eof
)

echo Execute iniciar.bat primeiro para criar o ambiente virtual.
pause
