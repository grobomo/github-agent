@echo off
:: Process guard: skip if agent is already running
tasklist /FI "WINDOWTITLE eq github-agent-service" 2>NUL | find /I "cmd.exe" >NUL && exit /b 0
if exist "C:\Users\joelg\Documents\ProjectsCL1\_grobomo\github-agent\data\agent.lock" (
  for /f %%a in (C:\Users\joelg\Documents\ProjectsCL1\_grobomo\github-agent\data\agent.lock) do tasklist /FI "PID eq %%a" 2>NUL | find /I "python" >NUL && exit /b 0
)
title github-agent-service
cd /d "C:\Users\joelg\Documents\ProjectsCL1\_grobomo\github-agent"
echo %date% %time% Starting agent for grobomo >> "C:\Users\joelg\Documents\ProjectsCL1\_grobomo\github-agent\data\agent.log"
"C:\Users\joelg\AppData\Local\Programs\Python\Python312\python.exe" main.py --account grobomo --interval 10 --full-scan-interval 300 >> "C:\Users\joelg\Documents\ProjectsCL1\_grobomo\github-agent\data\agent.log" 2>&1
