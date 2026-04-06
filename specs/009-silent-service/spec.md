# Spec 009: Silent Service Deployment

## Problem
The agent currently launches via `cmd.exe start` with a visible window that steals focus. There's no auto-start on login — the user must manually run it. The service needs to run invisibly in the background.

## Solution
1. **Silent launcher**: VBS wrapper that runs `service.bat` with hidden window (WshShell.Run, windowStyle=0)
2. **Scheduled task**: Windows Task Scheduler task that runs the VBS launcher at user logon with process guard (skip if already running)
3. **Install/uninstall script**: `scripts/install-scheduler.sh` to create/remove the scheduled task
