# Tasks: 006 Fix Agent Responsiveness

## Fallback Rules
- [x] T047: Update _fallback_decisions — RESPOND to issue_opened/pr_opened with acknowledgment message

## Service Reliability
- [x] T048: Add lock file management to main.py — create on start, remove on shutdown
- [x] T049: Update service.bat — clean stale lock files, detect crashed processes
- [x] T050: Add DB retry logic — catch "database is locked" and retry instead of crashing

## Tests
- [x] T051: Test fallback RESPOND behavior for issues/PRs
- [x] T052: Test lock file lifecycle

## Tracking
- [x] T053: Update TODO.md
