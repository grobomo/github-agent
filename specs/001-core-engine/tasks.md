# Tasks: 001 Core Engine + GitHub Agent

## Foundation
- [x] T001: Create core/store.py — EventStore with SQLite + FTS, source-agnostic schema (events table with source, account, channel, event_id, event_type, actor, title, body, metadata, processed flag)
- [x] T002: Create core/brain.py — LLM analyzer using claude -p, builds context prompt from EventStore, returns action decisions (IGNORE/LOG/RESPOND/DISPATCH/ALERT)
- [x] T003: Create core/dispatcher.py — executes brain decisions: post comments via gh, dispatch to CCC bridge, email alerts via email-manager
- [x] T004: Create github/poller.py — polls all event types via gh_auto CLI (issues, PRs, discussions, pushes, notifications, settings, actions)
- [x] T005: Create github/normalizer.py — converts raw gh API responses into EventStore-compatible records
- [x] T006: Create config/accounts.yaml — lists monitored accounts with event filters and poll intervals

## Settings & Security Monitoring
- [x] T007: Create github/settings.py — snapshot repo settings (visibility, branch protection, collaborators, apps), detect drift between polls
- [x] T008: Settings drift detection — compare current snapshot to previous, generate ALERT events for security-sensitive changes

## Context Cache
- [ ] T009: Create core/context.py — builds rolling context cache from EventStore for claude -p prompts (last 24h events, active issues/PRs summary, settings state)
- [ ] T010: Context cache file management — write/read JSON cache files, rebuild on each poll cycle

## Main Entry Point
- [x] T011: Create main.py — CLI entry point with --account flag, runs poll→store→analyze→dispatch loop with graceful shutdown
- [x] T012: Create scripts/run.sh — wrapper that runs one agent per account in parallel

## Automation
- [ ] T013: Create scripts/install-cron.sh — installs cron jobs for periodic polling (every 5 min per account)
- [x] T014: Health check endpoint — HTTP /healthz and /stats like teams-agent

## Testing
- [ ] T015: Test EventStore — insert, dedup, search, context window, prune
- [ ] T016: Test normalizer — verify all event types convert correctly
- [ ] T017: Test brain fallback — when claude -p unavailable, rule-based decisions work
- [ ] T018: Integration test — end-to-end poll→store→analyze with mock gh output
