# Tasks: 002 Refactor & Harden

## DRY
- [x] T019: Extract github/gh_cli.py — shared gh_command + parse_json, update poller, dispatcher, settings to import from it
- [x] T020: Handle events API 404 gracefully — downgrade to debug log, skip silently for repos without events endpoint
- [x] T021: Fix schtasks path mangling in Git Bash — MSYS_NO_PATHCONV for Windows scheduled task install

## Resilience
- [x] T022: Catch claude -p timeout in brain — fall back to rule-based decisions instead of crashing
- [x] T023: Fix DB locking — add busy_timeout for concurrent scheduled task access
- [x] T024: Live E2E test — create issue, run agent, verify detection + fallback decision pipeline
