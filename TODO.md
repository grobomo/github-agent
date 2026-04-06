# GitHub Agent — TODO

## Current State
Branch: `main`
Service: `github-agent-service` running continuously (MINUTE/1 with process guard)
PRs merged: #1-#4, #7-#24 (specs 001-006, 008-012 complete)
Tests: 90 passing

## Session Handoff
Last session completed:
- Spec 010: Service health monitoring (PR #22) — log rotation, heartbeat, watchdog, circuit breaker
- Spec 011: Code cleanup (PR #23) — removed redundant import
- Spec 012: README update (PR #24) — documented memory, health, watchdog features
- Full code review of all modules — no issues found
- 90 tests passing, 24 PRs merged
- Next: Spec 007a-c (unified brain with Teams integration) — cross-project, needs tmemu/teams-agent
- Or: Spec 008 (webhook receiver) from Future Specs — needs public endpoint infrastructure

## Pending Work (from user feedback)
- [x] Issue #16: Brain needs long-term context — Spec 008 complete (PR #19). Three-tier memory: hot cache + per-repo JSON + account-level memory. Compactor runs after each full scan.
- [x] Clean up stale remote branch `spec-008-long-term-context`
- [x] Install scheduled task so service auto-starts — Spec 009 complete (silent VBS launcher, every 1 min with process guard)

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

## Spec 006 (Fix Responsiveness) — complete
- [x] T047: Fallback rules RESPOND to external issues/PRs
- [x] T048-T049: Lock file management + stale lock cleanup
- [x] T050: DB locked retry instead of crash
- [x] T051-T052: 5 new tests (54 total)
- [x] T053: Task tracking

## Spec 007: Unified Brain Service (NEXT — user requested)
User requirement: ONE brain processing ALL input channels (GitHub + Teams). Deploy as silent background service (no cmd windows, no focus stealing). Both pollers feed into the same EventStore + brain.

Current state:
- github-agent has: core/brain.py (claude -p + fallback rules), core/store.py (SQLite+FTS)
- teams-agent has: lib/classifier.py (ImportanceClassifier), lib/store/db.py (MessageStore)
- They are completely separate — different schemas, different brains, different DBs
- github-agent runs via cmd.exe (visible window), teams-agent runs via RONE K8s

What needs to happen:
- [ ] Spec 007a: Unified EventStore schema that both GH and Teams records fit into (core/store.py already source-agnostic by design)
- [ ] Spec 007b: Single brain service — one process, one DB, one LLM context window spanning ALL sources
- [ ] Spec 007c: Teams poller as input channel — port teams-agent polling into a channel adapter for the unified brain
- [x] Spec 007d: Silent service deployment — done as Spec 009 (VBS launcher, scheduled task, no visible windows)
- [x] Spec 007e: Service health monitoring — done as Spec 010 (PR #22: log rotation, heartbeat, watchdog, circuit breaker)
- [ ] Spec 007f: Tests for unified pipeline, service lifecycle, channel adapters
- [x] Spec 007g: Issue #16 — done as Spec 008 (three-tier memory: hot cache + per-repo JSON + account memory)

Dependencies:
- teams-agent at `_tmemu/teams-agent/` — need to read its store schema and classifier
- msgraph-lib at `~/Documents/ProjectsCL1/msgraph-lib/` — shared token management
- This is a MAJOR refactor — the brain becomes its own service, pollers become plugins

## Future Specs
- [ ] Spec 008: Webhook receiver (GitHub webhooks for instant notification)

## Related Projects
- `_tmemu/teams-agent/` — Teams monitoring agent (separate brain, needs unification)
- `_grobomo/hook-monitor/` — hook health monitoring (TODO.md only)
  - Cross-refs: hook-runner/TODO.md (T094), system-monitor/TODO.md (T-HOOK)
