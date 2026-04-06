# Spec 010: Service Health Monitoring — Tasks

- [x] T066: Log rotation + heartbeat + max-errors circuit breaker
  - Add `RotatingFileHandler` to main.py (5 MB, 3 backups, configurable via CLI flags)
  - Write `data/heartbeat.json` after each poll cycle with pid, account, timestamp, stats, status
  - Add `--max-errors` flag: consecutive error counter, exit code 2 when exceeded
  - Add `--log-max-bytes` and `--log-backup-count` CLI flags

- [x] T067: Watchdog script
  - Create `scripts/watchdog.sh` that checks heartbeat freshness (< 2 min default)
  - If stale: kill PID from heartbeat, delete lock file, log the restart
  - Exit codes: 0=healthy, 1=stale/restarted, 2=no heartbeat file
  - Works on both Windows (Git Bash) and Linux

- [x] T068: Tests for service health features
  - Test log rotation setup (RotatingFileHandler configured correctly)
  - Test heartbeat file write/read cycle
  - Test max-errors circuit breaker (exits after N consecutive errors)
  - Test watchdog logic (fresh heartbeat = healthy, stale = unhealthy)
