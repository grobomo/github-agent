# Spec 001: Core Monitoring Engine + GitHub Agent

## Problem
No centralized awareness of GitHub activity across multiple accounts. Events (issues, PRs, discussions, settings changes, repo creation) happen silently. No LLM-driven analysis to detect security risks, route tasks, or maintain situational context.

Teams-agent already solves this for Teams chats. The architecture (poll → store → analyze → route) is proven but tightly coupled to MS Graph. We need:
1. A **shared core engine** that any source (Teams, GitHub, email, etc.) can plug into
2. A **GitHub poller** that covers all event types across all authenticated accounts
3. An **LLM brain** that analyzes events with full historical context and decides actions
4. **One agent per account** for security isolation

## Design

### Core Engine (reusable)
```
Source Poller (GitHub, Teams, etc.)
  │
  ▼
EventStore (SQLite + FTS, source-agnostic schema)
  │
  ▼
Brain (claude -p with context window from EventStore)
  │
  ▼
Dispatcher (RESPOND, DISPATCH, ALERT, IGNORE, LOG)
```

The core engine is source-agnostic. It provides:
- `EventStore` — SQLite with FTS, stores events from any source with common schema
- `Brain` — LLM analyzer that receives new events + historical context, returns decisions
- `Dispatcher` — executes decisions (post comments, dispatch to CCC, email alerts)

### GitHub Poller (source-specific)
Polls via `gh` CLI (through `gh_auto`). Event types:
- Issues: opened, closed, commented, labeled
- PRs: opened, reviewed, merged, CI status
- Discussions: new, commented
- Pushes: new commits
- Settings: visibility changes, branch protection, collaborator adds
- Actions: workflow failures
- Notifications: cross-repo activity feed
- Repo lifecycle: created, deleted, archived, transferred

### Security Model
- One agent process per `gh` account (grobomo, tmemu)
- Each account has its own EventStore database
- Brain sees only events from its own account
- Cross-account correlation happens at a higher level (future)

### Context Cache
Running context cache as JSON files for `claude -p` prompts:
- Last 24h of events per account
- Summary of active issues/PRs across all repos
- Settings snapshot for drift detection
- Rebuilt on each poll cycle from EventStore

### Automation
- Cron job runs poller every 5 minutes
- Brain analyzes unprocessed events after each poll
- Dispatcher executes decisions automatically
- Email alerts for security-sensitive events (settings changes, etc.)

## Relationship to teams-agent
Teams-agent's `lib/store/db.py` and `lib/github.py` are the starting points. The core engine generalizes the store schema. Teams-agent can later be refactored to use the shared core engine, but that's Phase 5 — not blocking.

## Out of Scope (this spec)
- Cross-account correlation
- AWS/K8s deployment
- Webhook receiver (polling first, webhooks later)
- Refactoring teams-agent to use shared core
