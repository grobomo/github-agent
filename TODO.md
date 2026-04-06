# GitHub Agent — TODO

## Current State
Branch: `main` — all specs merged
Scheduled task: `github-agent-poll` running every 5 min (Windows Task Scheduler)
PRs merged: #1 (spec 001, 18 tasks), #2 (DRY refactor), #3 (events 404), #4 (schtasks fix)

## Session Handoff
Last session completed:
- All 18 spec-001 tasks (store, brain, dispatcher, poller, normalizer, settings, context cache, tests, CI)
- Spec 002: T019 (DRY gh_cli), T020 (events 404 fix), T021 (schtasks Git Bash fix)
- Installed Windows scheduled task for 5-min polling
- 39 tests pass, secret-scan CI configured

User asked: "What is your ETA for when I can add a comment in a discussion or issue and have you read and reply in near-real time?"
Answer: The pipeline works end-to-end but needs `claude -p` available for intelligent replies (fallback rules only LOG/ALERT, don't RESPOND). The cron job polls every 5 min. For near-real-time, use continuous mode with shorter interval.

## Operational Status
- [x] Polling: scheduled task runs every 5 min
- [x] Store: SQLite + FTS working
- [x] Brain: fallback rules working, `claude -p` integration ready but needs CLI available
- [x] Dispatcher: gh comment posting works in dry-run, live mode ready
- [ ] Live test: post a GitHub issue comment and verify agent detects + responds
- [ ] Continuous mode deployment: `python main.py --account grobomo --interval 60` for near-real-time

## Remaining Tasks

### Spec 002 (Refactor & Harden) — more tasks possible
- [x] T019: Extract github/gh_cli.py
- [x] T020: Handle events API 404 gracefully
- [x] T021: Fix schtasks path mangling

### Future Specs
- [ ] Spec 003: Cross-agent integration (share EventStore schema with teams-agent)
- [ ] Spec 004: Dashboard/reporting (HTML status page like v1-report)
- [ ] Spec 005: Webhook receiver (GitHub webhooks for instant notification instead of polling)

## Related Projects
- `_grobomo/hook-monitor/` — hook health monitoring (TODO.md only)
  - Cross-refs: hook-runner/TODO.md (T094), system-monitor/TODO.md (T-HOOK)
