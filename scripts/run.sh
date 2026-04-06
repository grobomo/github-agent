#!/usr/bin/env bash
# Run github-agent for all configured accounts in parallel.
# Usage: bash scripts/run.sh [--once] [--dry-run] [--verbose]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Default accounts (override via GITHUB_AGENT_ACCOUNTS env var)
ACCOUNTS="${GITHUB_AGENT_ACCOUNTS:-grobomo joel-ginsberg_tmemu}"

# Parse args to forward
EXTRA_ARGS=("$@")

PIDS=()
for account in $ACCOUNTS; do
    echo "[github-agent] Starting agent for $account"
    python main.py --account "$account" "${EXTRA_ARGS[@]}" &
    PIDS+=($!)
done

# Wait for all or handle SIGTERM/SIGINT
cleanup() {
    echo "[github-agent] Shutting down all agents..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait
    echo "[github-agent] All agents stopped."
}

trap cleanup SIGTERM SIGINT

# Wait for any child to exit
wait -n 2>/dev/null || wait
cleanup
