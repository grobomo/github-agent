# GitHub Agent — TODO

## Current State
Branch: `main` — all specs merged
Scheduled task: `github-agent-poll` running every 5 min (Windows Task Scheduler)
PRs merged: #1 (spec 001), #2 (DRY refactor), #3 (events 404), #4 (schtasks fix), #7 (brain resilience), #8 (continuous mode)

## Session Handoff
Last session completed:
- T022-T024: Brain timeout resilience, DB busy_timeout, live E2E verified
- T025-T027: Continuous mode — tiered fast/full polling, service launcher, renamed install-scheduler.sh
- Code review pass: all modules clean, no security issues
- 39 tests pass, 9 PRs merged

Known issue: dispatcher email path (`_send_email_alert`) references `python -m email_manager` but email-manager's module is under `src/`, not `email_manager/`. Low priority — alerts not actively sent yet.

## Operational Status
- [x] Polling: scheduled task runs every 5 min (full scan)
- [x] Store: SQLite + FTS working, concurrent access fixed (busy_timeout=5000)
- [x] Brain: fallback rules working, claude -p gracefully times out
- [x] Dispatcher: gh comment posting works in dry-run, live mode ready
- [x] Live test: issue #6 detected, 11 events stored, fallback decisions made
- [x] Continuous mode: tiered fast/full polling implemented (T025-T027)
- [ ] Update scheduled task to use continuous service mode instead of --once every 5min
- [ ] Fix dispatcher email path for ALERT actions

## Spec 002 (Refactor & Harden) — complete
- [x] T019–T027: All complete

## Future Specs
- [ ] Spec 003: Cross-agent integration (share EventStore schema with teams-agent)
- [ ] Spec 004: Dashboard/reporting (HTML status page like v1-report)
- [ ] Spec 005: Webhook receiver (GitHub webhooks for instant notification)
- [ ] Publish: generate docs, README, publish to marketplace

## Related Projects
- `_grobomo/hook-monitor/` — hook health monitoring (TODO.md only)
  - Cross-refs: hook-runner/TODO.md (T094), system-monitor/TODO.md (T-HOOK)
