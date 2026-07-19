@echo off
setlocal
title Wendel Dev - YouTube Downloader
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado.
    echo Instale o Python 3.10 ou superior em https://python.org
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [WENDEL DEV] Preparando o ambiente pela primeira vez...
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :error

".venv\Scripts\python.exe" main.py
echo.
pause
exit /b 0

:error
echo.
echo [ERRO] Nao foi possivel preparar a ferramenta.
pause
exit /b 1
