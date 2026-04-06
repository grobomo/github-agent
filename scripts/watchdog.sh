#!/usr/bin/env bash
# Watchdog for github-agent — checks heartbeat freshness.
#
# Exit codes:
#   0 = healthy (heartbeat is fresh)
#   1 = stale heartbeat (killed process, cleaned lock)
#   2 = no heartbeat file found
#
# Usage:
#   bash scripts/watchdog.sh                    # default: 120s staleness threshold
#   STALE_SECONDS=60 bash scripts/watchdog.sh   # custom threshold
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HEARTBEAT="$PROJECT_DIR/data/heartbeat.json"
LOCKFILE="$PROJECT_DIR/data/agent.lock"
LOGFILE="$PROJECT_DIR/data/agent.log"
STALE_SECONDS="${STALE_SECONDS:-120}"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] $*" | tee -a "$LOGFILE"
}

if [[ ! -f "$HEARTBEAT" ]]; then
    log "No heartbeat file found at $HEARTBEAT"
    exit 2
fi

# Parse timestamp from heartbeat JSON (portable: node or python)
TIMESTAMP=$(node -p "JSON.parse(require('fs').readFileSync('$(cygpath -w "$HEARTBEAT" 2>/dev/null || echo "$HEARTBEAT")','utf-8')).timestamp" 2>/dev/null \
    || python -c "import json; print(json.load(open(r'''$HEARTBEAT''')).get('timestamp',''))" 2>/dev/null \
    || echo "")

if [[ -z "$TIMESTAMP" ]]; then
    log "Could not parse timestamp from heartbeat"
    exit 2
fi

# Convert ISO timestamp to epoch seconds
HEARTBEAT_EPOCH=$(python -c "
from datetime import datetime, timezone
ts = '$TIMESTAMP'
# Handle both Z suffix and +00:00
ts = ts.replace('Z', '+00:00')
dt = datetime.fromisoformat(ts)
print(int(dt.timestamp()))
" 2>/dev/null || echo "0")

NOW_EPOCH=$(date +%s)
AGE=$((NOW_EPOCH - HEARTBEAT_EPOCH))

if [[ "$AGE" -lt "$STALE_SECONDS" ]]; then
    # Read status from heartbeat
    STATUS=$(node -p "JSON.parse(require('fs').readFileSync('$(cygpath -w "$HEARTBEAT" 2>/dev/null || echo "$HEARTBEAT")','utf-8')).status" 2>/dev/null || echo "unknown")
    POLLS=$(node -p "JSON.parse(require('fs').readFileSync('$(cygpath -w "$HEARTBEAT" 2>/dev/null || echo "$HEARTBEAT")','utf-8')).polls" 2>/dev/null || echo "?")
    ERRORS=$(node -p "JSON.parse(require('fs').readFileSync('$(cygpath -w "$HEARTBEAT" 2>/dev/null || echo "$HEARTBEAT")','utf-8')).errors" 2>/dev/null || echo "?")
    echo "healthy: age=${AGE}s status=$STATUS polls=$POLLS errors=$ERRORS"
    exit 0
fi

# Stale heartbeat — kill the process
log "Stale heartbeat: age=${AGE}s (threshold=${STALE_SECONDS}s)"

PID=$(node -p "JSON.parse(require('fs').readFileSync('$(cygpath -w "$HEARTBEAT" 2>/dev/null || echo "$HEARTBEAT")','utf-8')).pid" 2>/dev/null || echo "")

if [[ -n "$PID" && "$PID" != "undefined" ]]; then
    if tasklist.exe /FI "PID eq $PID" 2>/dev/null | grep -qi "python"; then
        log "Killing stale agent process PID=$PID"
        taskkill.exe /PID "$PID" /F 2>/dev/null || kill "$PID" 2>/dev/null || true
    elif kill -0 "$PID" 2>/dev/null; then
        log "Killing stale agent process PID=$PID"
        kill "$PID" 2>/dev/null || true
    else
        log "PID $PID already dead"
    fi
fi

# Clean lock file
if [[ -f "$LOCKFILE" ]]; then
    rm -f "$LOCKFILE"
    log "Removed stale lock file"
fi

log "Agent will restart on next scheduled task cycle"
exit 1
