@echo off
:: Resolve project root from script location (scripts\service.bat -> project root)
set "PROJECT_DIR=%~dp0.."
set "LOCKFILE=%PROJECT_DIR%\data\agent.lock"
set "LOGFILE=%PROJECT_DIR%\data\agent.log"

:: Process guard: skip if agent window is already running
tasklist /FI "WINDOWTITLE eq github-agent-service" 2>NUL | find /I "cmd.exe" >NUL && exit /b 0

:: Check lock file — if PID is alive, skip; if stale, clean it up
if exist "%LOCKFILE%" (
  for /f %%a in (%LOCKFILE%) do (
    tasklist /FI "PID eq %%a" 2>NUL | find /I "python" >NUL && exit /b 0
    del "%LOCKFILE%" 2>NUL
    echo %date% %time% Cleaned stale lock (PID %%a) >> "%LOGFILE%"
  )
)

title github-agent-service
cd /d "%PROJECT_DIR%"
echo %date% %time% Starting agent for grobomo >> "%LOGFILE%"
python main.py --account grobomo --interval 10 --full-scan-interval 300 >> "%LOGFILE%" 2>&1
