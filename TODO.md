# GitHub Agent — TODO

## Current State
Branch: `001-T001-event-store` (all 18 tasks complete)
Spec: `specs/001-core-engine/` — 18 of 18 tasks complete
Status: Ready for PR to main

Core is functional: EventStore, Brain, Dispatcher, Poller, Normalizer, Settings, Context Cache all working.
39 tests pass. CI secret-scan configured.

Live smoke test: `python main.py --account grobomo --repos grobomo/github-agent --once --dry-run -v`

## Spec 001 Task Status
All complete — see `specs/001-core-engine/tasks.md`

### Done
- [x] T001: core/store.py — EventStore (SQLite + FTS)
- [x] T002: core/brain.py — LLM analyzer + rule-based fallback
- [x] T003: core/dispatcher.py — action executor (gh, CCC, email)
- [x] T004: github/poller.py — polls all event types via gh_auto
- [x] T005: github/normalizer.py — raw API → event records
- [x] T006: config/accounts.yaml.example
- [x] T007: github/settings.py — settings snapshot
- [x] T008: Settings drift detection (wired into main loop)
- [x] T009: core/context.py — rolling context cache for LLM prompts
- [x] T010: Context cache file management (integrated into main loop)
- [x] T011: main.py — CLI entry point with poll→analyze→dispatch loop
- [x] T012: scripts/run.sh — multi-account parallel runner
- [x] T013: scripts/install-cron.sh — cron/schtasks installer
- [x] T014: Health check endpoint (/healthz, /stats)
- [x] T015: Test EventStore (11 tests)
- [x] T016: Test normalizer (15 tests)
- [x] T017: Test brain fallback (9 tests)
- [x] T018: Integration test (4 tests)

## Next Steps (post-merge)
- [ ] Spec 002: Cross-agent integration (share EventStore schema with teams-agent)
- [ ] Spec 003: Dashboard/reporting (HTML status page like v1-report)
- [ ] Install cron job on actual machine (`bash scripts/install-cron.sh`)
- [ ] Production deployment documentation

## Related Projects
- `_grobomo/hook-monitor/` — hook health monitoring (TODO.md only)
  - Cross-refs: hook-runner/TODO.md (T094), system-monitor/TODO.md (T-HOOK)
