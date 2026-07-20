@echo off
setlocal
chcp 65001 >nul
title Wendel Dev - Media Downloader + AI
cd /d "%~dp0"

echo ==========================================================
echo          WENDEL DEV - INICIANDO FERRAMENTA
echo ==========================================================
echo.

set "PYTHON_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD goto :python_error

echo [1/3] Python encontrado.

if not exist ".venv\Scripts\python.exe" (
    echo [2/3] Criando ambiente virtual pela primeira vez...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo [2/3] Ambiente virtual pronto.
)

if not exist ".venv\.requirements-ready" (
    echo [3/3] Instalando dependencias. Isso pode levar alguns minutos...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 goto :dependency_error
    type nul > ".venv\.requirements-ready"
) else (
    echo [3/3] Dependencias prontas.
)

echo.
echo Abrindo a ferramenta...
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto :app_error
echo.
pause
exit /b 0

:python_error
echo.
echo [ERRO] Python 3 nao foi encontrado.
echo Instale em: https://www.python.org/downloads/
echo Durante a instalacao, marque "Add Python to PATH".
goto :pause_error

:dependency_error
echo.
echo [ERRO] Falha ao instalar as dependencias.
echo Confira sua conexao com a internet e tente novamente.
goto :pause_error

:app_error
echo.
echo [ERRO] A ferramenta foi encerrada com erro.
goto :pause_error

:error
echo.
echo [ERRO] Nao foi possivel criar o ambiente virtual.

:pause_error
echo.
echo Pressione qualquer tecla para fechar esta janela.
pause
exit /b 1
