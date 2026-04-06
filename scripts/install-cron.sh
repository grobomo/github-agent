#!/usr/bin/env bash
# Install periodic polling for github-agent.
#
# Linux/macOS: installs a cron job (every 5 min)
# Windows (Git Bash): creates a Windows Scheduled Task via schtasks
#
# Usage:
#   bash scripts/install-cron.sh              # install
#   bash scripts/install-cron.sh --remove     # uninstall
#   bash scripts/install-cron.sh --status     # check if installed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TASK_NAME="github-agent-poll"
INTERVAL_MIN=5
PYTHON="python"
RUN_CMD="$PYTHON $PROJECT_DIR/main.py"
LOG_FILE="$PROJECT_DIR/data/cron.log"

# Accounts to poll
ACCOUNTS="${GITHUB_AGENT_ACCOUNTS:-grobomo joel-ginsberg_tmemu}"

ACTION="${1:-install}"

is_windows() {
    [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]
}

install_cron() {
    if is_windows; then
        install_windows
    else
        install_unix
    fi
}

install_unix() {
    CRON_LINE="*/$INTERVAL_MIN * * * * cd $PROJECT_DIR && bash scripts/run.sh --once >> $LOG_FILE 2>&1"

    # Check if already installed
    if crontab -l 2>/dev/null | grep -qF "$TASK_NAME"; then
        echo "Cron job already installed. Use --remove first to reinstall."
        return 0
    fi

    # Add with marker comment
    (crontab -l 2>/dev/null; echo "# $TASK_NAME"; echo "$CRON_LINE") | crontab -
    echo "Installed cron job: every $INTERVAL_MIN minutes"
    echo "Log: $LOG_FILE"
}

install_windows() {
    # Build the command for each account
    WIN_PROJECT_DIR="$(cygpath -w "$PROJECT_DIR" 2>/dev/null || echo "$PROJECT_DIR")"
    WIN_PYTHON="$(cygpath -w "$(which python)" 2>/dev/null || echo "python")"
    WIN_LOG="$(cygpath -w "$LOG_FILE" 2>/dev/null || echo "$LOG_FILE")"

    # Create a wrapper batch file that runs all accounts
    BATCH_FILE="$PROJECT_DIR/scripts/poll.bat"
    {
        echo "@echo off"
        echo "cd /d \"$WIN_PROJECT_DIR\""
        for account in $ACCOUNTS; do
            echo "\"$WIN_PYTHON\" main.py --account $account --once >> \"$WIN_LOG\" 2>&1"
        done
    } > "$BATCH_FILE"

    WIN_BATCH="$(cygpath -w "$BATCH_FILE" 2>/dev/null || echo "$BATCH_FILE")"

    # Remove existing task if any
    # MSYS_NO_PATHCONV prevents Git Bash from mangling /flags as file paths
    MSYS_NO_PATHCONV=1 schtasks.exe /Delete /TN "$TASK_NAME" /F 2>/dev/null || true

    # Create scheduled task (every 5 minutes)
    MSYS_NO_PATHCONV=1 schtasks.exe /Create \
        /TN "$TASK_NAME" \
        /TR "\"$WIN_BATCH\"" \
        /SC MINUTE \
        /MO "$INTERVAL_MIN" \
        /F

    echo "Installed Windows Scheduled Task: $TASK_NAME (every $INTERVAL_MIN min)"
    echo "Batch: $BATCH_FILE"
    echo "Log: $LOG_FILE"
}

remove_cron() {
    if is_windows; then
        MSYS_NO_PATHCONV=1 schtasks.exe /Delete /TN "$TASK_NAME" /F 2>/dev/null && \
            echo "Removed task: $TASK_NAME" || \
            echo "Task not found: $TASK_NAME"
    else
        if crontab -l 2>/dev/null | grep -qF "$TASK_NAME"; then
            crontab -l | grep -v "$TASK_NAME" | grep -vF "scripts/run.sh" | crontab -
            echo "Removed cron job: $TASK_NAME"
        else
            echo "Cron job not found: $TASK_NAME"
        fi
    fi
}

status_cron() {
    if is_windows; then
        MSYS_NO_PATHCONV=1 schtasks.exe /Query /TN "$TASK_NAME" 2>/dev/null && \
            echo "Status: INSTALLED" || \
            echo "Status: NOT INSTALLED"
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
    install|--install)  install_cron ;;
    remove|--remove)    remove_cron ;;
    status|--status)    status_cron ;;
    *)
        echo "Usage: $0 [install|--remove|--status]"
        exit 1
        ;;
esac
