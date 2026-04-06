# GitHub Agent — TODO

## Current State
Branch: `main` — all specs merged
Scheduled task: `github-agent-poll` running every 5 min (Windows Task Scheduler)
PRs merged: #1 (spec 001, 18 tasks), #2 (DRY refactor), #3 (events 404), #4 (schtasks fix), #7 (brain resilience)

## Session Handoff
Last session completed:
- T022: Brain catches claude -p timeout, falls back to rule-based decisions
- T023: SQLite busy_timeout=5000 for concurrent scheduled task access
- T024: Live E2E verified — issue #6 created, 11 events detected, fallback pipeline works
- 39 tests pass

## Operational Status
- [x] Polling: scheduled task runs every 5 min
- [x] Store: SQLite + FTS working, concurrent access fixed
- [x] Brain: fallback rules working, claude -p gracefully times out
- [x] Dispatcher: gh comment posting works in dry-run, live mode ready
- [x] Live test: issue #6 detected, 11 events stored, fallback decisions made
- [ ] Continuous mode deployment: `python main.py --account grobomo --interval 60` for near-real-time

## Remaining Tasks

### Spec 002 (Refactor & Harden) — all done
- [x] T019–T024: All complete

### Future Specs
- [ ] Spec 003: Cross-agent integration (share EventStore schema with teams-agent)
- [ ] Spec 004: Dashboard/reporting (HTML status page like v1-report)
- [ ] Spec 005: Webhook receiver (GitHub webhooks for instant notification instead of polling)

## Related Projects
- `_grobomo/hook-monitor/` — hook health monitoring (TODO.md only)
  - Cross-refs: hook-runner/TODO.md (T094), system-monitor/TODO.md (T-HOOK)
