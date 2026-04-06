# Tasks: 006 Fix Agent Responsiveness

## Fallback Rules
- [ ] T047: Update _fallback_decisions — RESPOND to issue_opened/pr_opened with acknowledgment message

## Service Reliability
- [ ] T048: Add lock file management to main.py — create on start, remove on shutdown
- [ ] T049: Update service.bat — clean stale lock files, detect crashed processes
- [ ] T050: Add DB retry logic — catch "database is locked" and retry instead of crashing

## Tests
- [ ] T051: Test fallback RESPOND behavior for issues/PRs
- [ ] T052: Test lock file lifecycle

## Tracking
- [ ] T053: Update TODO.md
