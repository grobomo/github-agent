# GitHub Agent

Monitors all GitHub activity across multiple accounts. Polls issues, PRs, discussions, notifications, workflow runs, and settings changes. Uses LLM analysis (claude -p) with full historical context to decide actions: respond, dispatch tasks, send alerts, or log.

## Architecture

```
GitHub API (via gh_auto CLI)
  │
  ▼
GitHubPoller (per-account, discovers repos automatically)
  ├── Issues, PRs, Discussions, Notifications
  ├── Repo events (pushes, forks, stars)
  ├── Workflow runs (failures)
  └── Settings snapshots (drift detection)
  │
  ▼
Normalizer (converts to common event format)
  │
  ▼
EventStore (SQLite + FTS, source-agnostic)
  │
  ▼
Brain (claude -p with 24h context window, rule-based fallback)
  │
  ▼
Dispatcher (RESPOND via gh, DISPATCH to CCC, ALERT via email, LOG)
```

## Running

```bash
# Single account, single poll, dry run
python main.py --account grobomo --once --dry-run -v

# Single account, continuous
python main.py --account grobomo --interval 300

# All accounts in parallel
bash scripts/run.sh

# With health endpoint
python main.py --account grobomo --health-port 8081
```

## Key Files

- `core/store.py` — EventStore (SQLite + FTS)
- `core/brain.py` — LLM analyzer + rule-based fallback
- `core/dispatcher.py` — Action executor
- `github/poller.py` — GitHub API polling via gh_auto
- `github/normalizer.py` — Raw API → EventStore records
- `github/settings.py` — Settings snapshot + drift detection
- `main.py` — CLI entry point

## Design Decisions

- **One process per account** for security isolation
- **gh_auto** for all GitHub API calls (handles account switching)
- **SQLite WAL mode** for concurrent reads during polling
- **Rule-based fallback** when claude CLI unavailable
- **Settings drift detection** with severity levels (critical/high/medium/low)

## Shared Core Engine

`core/` is source-agnostic — designed for reuse by teams-agent and future agents. The schema, brain, and dispatcher don't know about GitHub specifically.
