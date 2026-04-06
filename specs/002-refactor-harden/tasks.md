# Tasks: 002 Refactor & Harden

## DRY
- [x] T019: Extract github/gh_cli.py — shared gh_command + parse_json, update poller, dispatcher, settings to import from it
- [x] T020: Handle events API 404 gracefully — downgrade to debug log, skip silently for repos without events endpoint
- [x] T021: Fix schtasks path mangling in Git Bash — MSYS_NO_PATHCONV for Windows scheduled task install

## Resilience
- [x] T022: Catch claude -p timeout in brain — fall back to rule-based decisions instead of crashing
- [x] T023: Fix DB locking — add busy_timeout for concurrent scheduled task access
- [x] T024: Live E2E test — create issue, run agent, verify detection + fallback decision pipeline

## Continuous Mode
- [x] T025: Rename install-cron.sh → install-scheduler.sh (not using cron)
- [x] T026: Fast-poll mode — notifications-only for intervals <30s, full repo scan at configurable longer interval
- [x] T027: Service launcher script with configurable interval for near-real-time polling

## Fixes
- [x] T028: Fix dispatcher email alert — replace broken email_manager CLI call with alerts.jsonl log file
- [x] T029: Update install-scheduler.sh to support continuous service mode as alternative to periodic task
- [x] T030: Fix service mode — use process guard + MINUTE/1 schedule (ONLOGON requires admin)
