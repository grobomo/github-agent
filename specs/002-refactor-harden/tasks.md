# Tasks: 002 Refactor & Harden

## DRY
- [x] T019: Extract github/gh_cli.py — shared gh_command + parse_json, update poller, dispatcher, settings to import from it
- [x] T020: Handle events API 404 gracefully — downgrade to debug log, skip silently for repos without events endpoint
- [x] T021: Fix schtasks path mangling in Git Bash — MSYS_NO_PATHCONV for Windows scheduled task install
