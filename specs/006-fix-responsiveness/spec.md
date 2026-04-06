# Spec 006: Fix Agent Responsiveness

## Problem
The agent failed to respond to issues created on the repo:
1. **Service crashed** — "database is locked" errors killed the process, no auto-restart
2. **Fallback rules too passive** — issue_opened is classified as LOG (not RESPOND), so even when detected, no comment is posted
3. **No lock file management** — main.py doesn't create/clean agent.lock, so the process guard in service.bat can't properly detect crashed vs running processes

## Fixes
1. **Fallback rules**: RESPOND to issue_opened/pr_opened on own repos with an acknowledgment
2. **Lock file**: main.py creates agent.lock on start, removes on clean shutdown, service.bat checks for stale locks
3. **DB resilience**: increase busy_timeout, add retry logic around poll cycles that hit DB locks
4. **Service restart**: service.bat should clean stale lock files and restart crashed processes

## Success criteria
- Create an issue on grobomo/github-agent → agent posts an acknowledgment comment within 60s
- Service auto-recovers from "database is locked" errors
- Stale lock files don't prevent service restart
