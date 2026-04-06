# GitHub Agent — TODO

## Current State
Branch: `main`
Service: `github-agent-service` running continuously (MINUTE/1 with process guard)
PRs merged: #1-#4, #7-#14 (specs 001-005 complete)

## Session Handoff
Last session completed:
- T042-T046: Spec 005 polish — requirements.txt, README dashboard docs, --auto-report flag
- T036-T041: Spec 004 dashboard — HTML report generator with SVG charts
- T031-T035: Spec 003 publish — README, LICENSE, repo description/topics
- Previous: specs 001-002, 49 tests total

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

## Spec 004 (Dashboard & Reporting) — complete
- [x] T036-T038: core/report.py — HTML report with status, events, actions, SVG chart
- [x] T039: --report and --output CLI flags
- [x] T040: 10 tests for report module
- [x] T041: Task tracking updated

## Spec 005 (Polish & Hardening) — complete
- [x] T042: requirements.txt
- [x] T043: README updated with dashboard docs
- [x] T044: .gitignore already covers data/
- [x] T045: --auto-report flag
- [x] T046: Task tracking

## Future Specs
- [ ] Spec 006: Cross-agent integration (share EventStore schema with teams-agent)
- [ ] Spec 007: Webhook receiver (GitHub webhooks for instant notification)

## Related Projects
- `_grobomo/hook-monitor/` — hook health monitoring (TODO.md only)
  - Cross-refs: hook-runner/TODO.md (T094), system-monitor/TODO.md (T-HOOK)
