@echo off
REM Para o Slayer Legend Monitor que esteja rodando em background.
REM Mata todos os processos pythonw.exe — se voce roda outros scripts
REM Python invisiveis simultaneamente, prefira parar pelo Gerenciador
REM de Tarefas (procure por pythonw.exe rodando monitor.py).

cd /d "%~dp0"

tasklist /FI "IMAGENAME eq pythonw.exe" /FO CSV /NH 2>nul | find /I "pythonw.exe" >nul
if %errorlevel% neq 0 (
    echo Nenhum pythonw.exe rodando — nada para parar.
    timeout /t 3 >nul
    exit /b 0
)

echo Encerrando processo(s) pythonw.exe ...
taskkill /F /IM pythonw.exe >nul 2>&1

if %errorlevel%==0 (
    echo Monitor parado.
) else (
    echo [ERRO] Nao foi possivel parar. Use o Gerenciador de Tarefas manualmente.
)

timeout /t 3 >nul
