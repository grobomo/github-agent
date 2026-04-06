#!/usr/bin/env bash
# Run github-agent as a continuous service with near-real-time polling.
#
# Fast polls (notifications only) every POLL_INTERVAL seconds.
# Full repo scans every FULL_SCAN_INTERVAL seconds.
#
# Usage:
#   bash scripts/service.sh                    # defaults: 10s fast, 300s full
#   POLL_INTERVAL=3 bash scripts/service.sh    # 3s fast polls
#   bash scripts/service.sh --dry-run          # no actions executed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

POLL_INTERVAL="${POLL_INTERVAL:-10}"
FULL_SCAN_INTERVAL="${FULL_SCAN_INTERVAL:-300}"
ACCOUNTS="${GITHUB_AGENT_ACCOUNTS:-grobomo}"
EXTRA_ARGS=("$@")

PIDS=()
for account in $ACCOUNTS; do
    echo "[github-agent] Starting service for $account (fast=${POLL_INTERVAL}s, full=${FULL_SCAN_INTERVAL}s)"
    python main.py \
        --account "$account" \
        --interval "$POLL_INTERVAL" \
        --full-scan-interval "$FULL_SCAN_INTERVAL" \
        --health-port 0 \
        "${EXTRA_ARGS[@]}" &
    PIDS+=($!)
done

cleanup() {
    echo "[github-agent] Shutting down all agents..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait
    echo "[github-agent] All agents stopped."
}

trap cleanup SIGTERM SIGINT

wait -n 2>/dev/null || wait
cleanup
