# Tasks: 002 Refactor & Harden

## DRY
- [x] T019: Extract github/gh_cli.py — shared gh_command + parse_json, update poller, dispatcher, settings to import from it
- [x] T020: Handle events API 404 gracefully — downgrade to debug log, skip silently for repos without events endpoint
