@echo off
setlocal
chcp 65001 >nul
title Wendel Dev - Gerador de Executavel
cd /d "%~dp0"

echo ==========================================================
echo       WENDEL DEV - GERANDO APLICATIVO PORTATIL
echo ==========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Execute iniciar.bat pelo menos uma vez antes de compilar.
    goto :error
)

echo [1/4] Instalando ferramentas de compilacao...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 goto :error

echo.
echo [2/4] Compilando WendelDev-AI.exe...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean WendelDev-AI.spec
if errorlevel 1 goto :error

echo.
echo [3/4] Copiando documentacao...
copy /Y "README.md" "dist\WendelDev-AI\README.md" >nul
if errorlevel 1 goto :error

echo [4/4] Criando arquivo ZIP para compartilhamento...
if exist "dist\WendelDev-AI-Windows.zip" del /Q "dist\WendelDev-AI-Windows.zip"
powershell.exe -NoProfile -Command "Compress-Archive -Path 'dist\WendelDev-AI\*' -DestinationPath 'dist\WendelDev-AI-Windows.zip' -CompressionLevel Optimal"
if errorlevel 1 goto :error

echo.
echo ==========================================================
echo                  APLICATIVO PRONTO
echo ==========================================================
echo Pasta: dist\WendelDev-AI
echo Compartilhe: dist\WendelDev-AI-Windows.zip
echo.
pause
exit /b 0

:error
echo.
echo [ERRO] Nao foi possivel gerar o aplicativo.
echo Revise a mensagem acima e tente novamente.
pause
exit /b 1
