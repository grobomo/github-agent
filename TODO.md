# GitHub Agent — TODO

## Current State
Branch: `main`
Service: `github-agent-service` running continuously (MINUTE/1 with process guard)
PRs merged: #1-#4, #7-#12 (spec 001 + spec 002 + spec 003 complete)

## Session Handoff
Last session completed:
- T031-T035: Spec 003 publish — README, LICENSE, repo description/topics, pushed to GitHub
- Previous: T019-T030 (spec 002), T001-T018 (spec 001), 39 tests, 12 PRs merged

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

## Spec 003 (Publish & Docs) — complete
- [x] T031: README.md
- [x] T032: MIT LICENSE
- [x] T033: Push all commits to remote
- [x] T034: Set repo description and topics
- [x] T035: Update TODO.md

## Future Specs
- [ ] Spec 004: Cross-agent integration (share EventStore schema with teams-agent)
- [ ] Spec 005: Dashboard/reporting (HTML status page like v1-report)
- [ ] Spec 006: Webhook receiver (GitHub webhooks for instant notification)

## Related Projects
- `_grobomo/hook-monitor/` — hook health monitoring (TODO.md only)
  - Cross-refs: hook-runner/TODO.md (T094), system-monitor/TODO.md (T-HOOK)
