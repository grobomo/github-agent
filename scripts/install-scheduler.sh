#!/usr/bin/env bash
# Install github-agent as a scheduled task or continuous service.
#
# Modes:
#   periodic (default): runs --once every INTERVAL_MIN minutes via scheduler
#   service: runs continuously with fast polling (notifications every 10s, full scan every 5min)
#
# Usage:
#   bash scripts/install-scheduler.sh                     # periodic (every 5 min)
#   bash scripts/install-scheduler.sh --mode service      # continuous service
#   bash scripts/install-scheduler.sh --remove            # uninstall
#   bash scripts/install-scheduler.sh --status            # check if installed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TASK_NAME="github-agent-poll"
SERVICE_TASK_NAME="github-agent-service"
INTERVAL_MIN=5
POLL_INTERVAL="${POLL_INTERVAL:-10}"
FULL_SCAN_INTERVAL="${FULL_SCAN_INTERVAL:-300}"
PYTHON="python"
LOG_FILE="$PROJECT_DIR/data/agent.log"

# Accounts to poll
ACCOUNTS="${GITHUB_AGENT_ACCOUNTS:-grobomo}"

# Parse args
MODE="periodic"
ACTION="install"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)     MODE="$2"; shift 2 ;;
        --remove)   ACTION="remove"; shift ;;
        --status)   ACTION="status"; shift ;;
        install|--install) ACTION="install"; shift ;;
        *)          echo "Unknown arg: $1"; exit 1 ;;
    esac
done

is_windows() {
    [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]
}

install_periodic() {
    if is_windows; then
        WIN_PROJECT_DIR="$(cygpath -w "$PROJECT_DIR" 2>/dev/null || echo "$PROJECT_DIR")"
        WIN_PYTHON="$(cygpath -w "$(which python)" 2>/dev/null || echo "python")"
        WIN_LOG="$(cygpath -w "$LOG_FILE" 2>/dev/null || echo "$LOG_FILE")"

        BATCH_FILE="$PROJECT_DIR/scripts/poll.bat"
        {
            echo "@echo off"
            echo "cd /d \"$WIN_PROJECT_DIR\""
            for account in $ACCOUNTS; do
                echo "\"$WIN_PYTHON\" main.py --account $account --once >> \"$WIN_LOG\" 2>&1"
            done
        } > "$BATCH_FILE"

        WIN_BATCH="$(cygpath -w "$BATCH_FILE" 2>/dev/null || echo "$BATCH_FILE")"

        MSYS_NO_PATHCONV=1 schtasks.exe /Delete /TN "$TASK_NAME" /F 2>/dev/null || true

        MSYS_NO_PATHCONV=1 schtasks.exe /Create \
            /TN "$TASK_NAME" \
            /TR "\"$WIN_BATCH\"" \
            /SC MINUTE \
            /MO "$INTERVAL_MIN" \
            /F

        echo "Installed periodic task: $TASK_NAME (every $INTERVAL_MIN min)"
        echo "Batch: $BATCH_FILE"
        echo "Log: $LOG_FILE"
    else
        CRON_LINE="*/$INTERVAL_MIN * * * * cd $PROJECT_DIR && bash scripts/run.sh --once >> $LOG_FILE 2>&1"
        if crontab -l 2>/dev/null | grep -qF "$TASK_NAME"; then
            echo "Cron job already installed. Use --remove first to reinstall."
            return 0
        fi
        (crontab -l 2>/dev/null; echo "# $TASK_NAME"; echo "$CRON_LINE") | crontab -
        echo "Installed cron job: every $INTERVAL_MIN minutes"
        echo "Log: $LOG_FILE"
    fi
}

install_service() {
    if is_windows; then
        WIN_PROJECT_DIR="$(cygpath -w "$PROJECT_DIR" 2>/dev/null || echo "$PROJECT_DIR")"
        WIN_PYTHON="$(cygpath -w "$(which python)" 2>/dev/null || echo "python")"
        WIN_LOG="$(cygpath -w "$LOG_FILE" 2>/dev/null || echo "$LOG_FILE")"

        BATCH_FILE="$PROJECT_DIR/scripts/service.bat"
        {
            echo "@echo off"
            echo "cd /d \"$WIN_PROJECT_DIR\""
            for account in $ACCOUNTS; do
                echo "start /b \"$WIN_PYTHON\" main.py --account $account --interval $POLL_INTERVAL --full-scan-interval $FULL_SCAN_INTERVAL >> \"$WIN_LOG\" 2>&1"
            done
            echo "pause >nul"
        } > "$BATCH_FILE"

        WIN_BATCH="$(cygpath -w "$BATCH_FILE" 2>/dev/null || echo "$BATCH_FILE")"

        # Remove old periodic task and any previous service task
        MSYS_NO_PATHCONV=1 schtasks.exe /Delete /TN "$TASK_NAME" /F 2>/dev/null || true
        MSYS_NO_PATHCONV=1 schtasks.exe /Delete /TN "$SERVICE_TASK_NAME" /F 2>/dev/null || true

        # Create task that starts on user logon
        MSYS_NO_PATHCONV=1 schtasks.exe /Create \
            /TN "$SERVICE_TASK_NAME" \
            /TR "\"$WIN_BATCH\"" \
            /SC ONLOGON \
            /F

        echo "Installed continuous service: $SERVICE_TASK_NAME (starts on logon)"
        echo "  Fast poll: every ${POLL_INTERVAL}s (notifications only)"
        echo "  Full scan: every ${FULL_SCAN_INTERVAL}s"
        echo "  Batch: $BATCH_FILE"
        echo "  Log: $LOG_FILE"
        echo ""
        echo "To start now: MSYS_NO_PATHCONV=1 schtasks.exe /Run /TN $SERVICE_TASK_NAME"
    else
        echo "Service mode on Linux: use systemd or run scripts/service.sh directly."
        echo "  Example: nohup bash scripts/service.sh >> $LOG_FILE 2>&1 &"
    fi
}

remove_all() {
    if is_windows; then
        MSYS_NO_PATHCONV=1 schtasks.exe /Delete /TN "$TASK_NAME" /F 2>/dev/null && \
            echo "Removed: $TASK_NAME" || true
        MSYS_NO_PATHCONV=1 schtasks.exe /Delete /TN "$SERVICE_TASK_NAME" /F 2>/dev/null && \
            echo "Removed: $SERVICE_TASK_NAME" || true
    else
        if crontab -l 2>/dev/null | grep -qF "$TASK_NAME"; then
            crontab -l | grep -v "$TASK_NAME" | grep -vF "scripts/run.sh" | crontab -
            echo "Removed cron job: $TASK_NAME"
        else
            echo "Cron job not found: $TASK_NAME"
        fi
    fi
}

show_status() {
    if is_windows; then
        echo "=== Periodic Task ==="
        MSYS_NO_PATHCONV=1 schtasks.exe /Query /TN "$TASK_NAME" 2>/dev/null && \
            echo "Status: INSTALLED" || echo "Status: NOT INSTALLED"
        echo ""
        echo "=== Service Task ==="
        MSYS_NO_PATHCONV=1 schtasks.exe /Query /TN "$SERVICE_TASK_NAME" 2>/dev/null && \
            echo "Status: INSTALLED" || echo "Status: NOT INSTALLED"
    else
        if crontab -l 2>/dev/null | grep -qF "$TASK_NAME"; then
            echo "Status: INSTALLED"
            crontab -l | grep -A1 "$TASK_NAME"
        else
            echo "Status: NOT INSTALLED"
        fi
    fi
}

mkdir -p "$PROJECT_DIR/data"

case "$ACTION" in
    install)
        if [[ "$MODE" == "service" ]]; then
            install_service
        else
            install_periodic
        fi
        ;;
    remove)  remove_all ;;
    status)  show_status ;;
esac
