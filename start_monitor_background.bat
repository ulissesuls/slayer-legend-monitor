@echo off
REM Inicia o Slayer Legend Monitor em segundo plano (sem janela visivel).
REM Os logs sao gravados em monitor.log e monitor.err.log.
REM Para parar: rode stop_monitor.bat (ou use o Gerenciador de Tarefas).

cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
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

REM Verifica se ja esta rodando
tasklist /FI "IMAGENAME eq pythonw.exe" /FO CSV /NH 2>nul | find /I "pythonw.exe" >nul
if %errorlevel%==0 (
    echo [AVISO] Existe um pythonw.exe rodando ^(pode ser outro Monitor^).
    echo Se quiser garantir que nao havera duplicatas, rode stop_monitor.bat antes.
    timeout /t 4 >nul
)

start "" /B ".venv\Scripts\pythonw.exe" monitor.py 1>monitor.log 2>monitor.err.log

echo.
echo  Monitor iniciado em segundo plano.
echo  Logs em: monitor.log  e  monitor.err.log
echo  Para parar, rode: stop_monitor.bat
echo.
timeout /t 3 >nul
