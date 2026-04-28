@echo off
REM Inicia o Slayer Legend Monitor com janela de console visivel.
REM Use este modo se quiser ver os logs em tempo real.
REM Para parar: Ctrl+C ou feche a janela.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado.
    echo Rode os passos de instalacao do README primeiro.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERRO] Arquivo .env nao encontrado.
    echo Copie .env.example para .env e preencha as credenciais.
    pause
    exit /b 1
)

echo ==========================================
echo  Slayer Legend Monitor — janela de logs
echo  Pressione Ctrl+C para parar.
echo ==========================================
echo.

".venv\Scripts\python.exe" monitor.py
pause
