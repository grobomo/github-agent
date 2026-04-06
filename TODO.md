# GitHub Agent — TODO

## Current State
Branch: `main`
Service: `github-agent-service` running continuously (MINUTE/1 with process guard)
PRs merged: #1-#4, #7-#11 (spec 001 + spec 002 complete)

## Session Handoff
Last session completed:
- T022-T024: Brain timeout resilience, DB busy_timeout, live E2E verified
- T025-T027: Continuous mode — tiered fast/full polling, service launcher
- T028: Fixed dispatcher email alert (was calling nonexistent module)
- T029-T030: Service mode installer with process guard (non-admin Windows compatible)
- Installed continuous service: 10s notifications, 300s full scan
- Code review: all modules clean, 39 tests pass, 11 PRs merged

## Operational Status
- [x] Continuous service: `github-agent-service` (MINUTE/1 + process guard)
- [x] Tiered polling: notifications every 10s, full repo scan every 5min
- [x] Store: SQLite + FTS + WAL + busy_timeout
- [x] Brain: fallback rules working, claude -p gracefully times out
- [x] Dispatcher: gh comment, alerts.jsonl, CCC bridge all working
- [x] Live E2E: issue #6 detected across 55+ repos
- [x] CI: secret-scan on all PRs

## Spec 002 (Refactor & Harden) — complete
- [x] T019–T030: All complete

## Future Specs
- [ ] Spec 003: Cross-agent integration (share EventStore schema with teams-agent)
- [ ] Spec 004: Dashboard/reporting (HTML status page like v1-report)
- [ ] Spec 005: Webhook receiver (GitHub webhooks for instant notification)
- [ ] Publish: generate docs, README, publish to marketplace via publish-project skill

## Related Projects
- `_grobomo/hook-monitor/` — hook health monitoring (TODO.md only)
  - Cross-refs: hook-runner/TODO.md (T094), system-monitor/TODO.md (T-HOOK)
