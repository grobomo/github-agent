# GitHub Agent — TODO

## Current State
Branch: `001-T001-event-store` (pushed to origin)
Spec: `specs/001-core-engine/` — 11 of 18 tasks complete

Core is functional: EventStore, Brain, Dispatcher, Poller, Normalizer, Settings all working.
Live smoke test passes: `python main.py --account grobomo --repos grobomo/github-agent --once --dry-run -v`

## Spec 001 Task Status
See `specs/001-core-engine/tasks.md` for full details.

### Done
- [x] T001: core/store.py — EventStore (SQLite + FTS)
- [x] T002: core/brain.py — LLM analyzer + rule-based fallback
- [x] T003: core/dispatcher.py — action executor (gh, CCC, email)
- [x] T004: github/poller.py — polls all event types via gh_auto
- [x] T005: github/normalizer.py — raw API → event records
- [x] T006: config/accounts.yaml.example
- [x] T007: github/settings.py — settings snapshot
- [x] T008: Settings drift detection (wired into main loop)
- [x] T011: main.py — CLI entry point with poll→analyze→dispatch loop
- [x] T012: scripts/run.sh — multi-account parallel runner
- [x] T014: Health check endpoint (/healthz, /stats)

### Remaining
- [ ] T009: core/context.py — rolling context cache for claude -p
- [ ] T010: Context cache file management
- [ ] T013: scripts/install-cron.sh — cron job setup
- [ ] T015: Test EventStore (formal test file)
- [ ] T016: Test normalizer (formal test file)
- [ ] T017: Test brain fallback
- [ ] T018: Integration test with mock gh output

## Hook Fixes Applied This Session
- **spec-gate.js**: Removed TODO.md fallback — specs/ now mandatory for code writes
- **run-pretooluse.js, run-stop.js, run-userpromptsubmit.js**: Fixed block output to use exit(1) + stderr(reason) + stdout(JSON) pattern
- **hook-editing-gate.js**: Updated exit code guidance to match correct protocol

## Related Projects Created
- `_grobomo/hook-monitor/` — new project for continuous hook health monitoring (TODO.md only, no code yet)
  - Cross-refs added to hook-runner/TODO.md (T094) and system-monitor/TODO.md (T-HOOK)

## Next Session Priority
1. T009-T010: Context cache (makes brain smarter with rolling context files)
2. T013: Cron job setup (makes it self-running)
3. T015-T018: Formal test files
4. Merge branch to main, create PR
5. secret-scan.yml for CI
