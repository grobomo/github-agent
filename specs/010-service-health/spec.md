# Spec 010: Service Health Monitoring

## Problem
The agent runs as a silent background service with no visibility into its health. The log file (`data/agent.log`) grows unbounded. If the agent process hangs (alive but not polling), the scheduled task's process guard won't restart it. There's no way to externally check if the agent is healthy without hitting the optional HTTP health port.

## Solution

### 1. Log rotation
Replace bare file logging with Python's `RotatingFileHandler`. Default: 5 MB per file, 3 backups. Configurable via `--log-max-bytes` and `--log-backup-count`.

### 2. Heartbeat file
After each poll cycle (fast or full), write `data/heartbeat.json` with:
```json
{
  "pid": 12345,
  "account": "grobomo",
  "timestamp": "2026-04-06T12:00:00Z",
  "polls": 42,
  "full_scans": 8,
  "errors": 0,
  "last_full_scan": "2026-04-06T11:55:00Z",
  "status": "ok"
}
```

### 3. Watchdog script
`scripts/watchdog.sh` — run by the existing scheduled task (or a separate one). Checks:
- Heartbeat file exists and is fresh (< 2 minutes old by default)
- Error count hasn't spiked
- If stale: kill the PID from heartbeat, delete lock file, let scheduled task restart

### 4. Max-errors circuit breaker
`--max-errors N` flag on main.py. If consecutive errors exceed N (default: 50), the agent exits with code 2. The scheduled task restarts it on the next cycle, resetting the counter. Prevents infinite error loops from burning API quota.

## Non-goals
- External monitoring (Prometheus, Datadog) — overkill for single-user agent
- Email alerts on health issues — the agent itself handles alerts
