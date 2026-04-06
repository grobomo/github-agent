# GitHub Agent

Monitors all GitHub activity across multiple accounts. Polls issues, PRs, discussions, notifications, workflow runs, and settings changes. Uses LLM analysis (`claude -p`) with full historical context to decide actions: respond, dispatch tasks, send alerts, or log.

## How it works

```
GitHub API (via gh CLI)
  │
  ▼
GitHubPoller (per-account, auto-discovers repos)
  ├── Issues, PRs, Discussions, Notifications
  ├── Repo events (pushes, forks, stars)
  ├── Workflow runs (failures)
  └── Settings snapshots (drift detection)
  │
  ▼
Normalizer → EventStore (SQLite + FTS)
  │
  ▼
Brain (LLM analysis with 24h context window)
  │
  ▼
Dispatcher (comment via gh, dispatch to CCC, alert via email, log)
```

The brain classifies each event as one of:

| Action | Description |
|--------|-------------|
| **IGNORE** | Routine activity, no action needed |
| **LOG** | Interesting but not actionable — stored for context |
| **RESPOND** | Post a comment on the issue/PR/discussion |
| **DISPATCH** | Send a task to the CCC dispatcher for deeper work |
| **ALERT** | Email notification — something urgent or security-sensitive |

Security-sensitive events (visibility changes, branch protection removal, admin access grants, leaked secrets) always trigger ALERT.

## Quick start

```bash
# Prerequisites: gh CLI authenticated, Python 3.12+
pip install -r requirements.txt  # optional: only pyyaml for config file support

# Single account, single poll, dry run
python main.py --account grobomo --once --dry-run -v

# Continuous monitoring (10s notification checks, 5min full scans)
python main.py --account grobomo --interval 10 --full-scan-interval 300

# With health endpoint
python main.py --account grobomo --interval 10 --health-port 8081
```

## Running as a service

```bash
# Install as scheduled task (Windows) or cron (Linux)
bash scripts/install-scheduler.sh

# Check status
bash scripts/install-scheduler.sh --status

# Remove
bash scripts/install-scheduler.sh --remove
```

The service uses tiered polling: fast notification checks every 10 seconds, full repo scans every 5 minutes. A process guard prevents duplicate instances.

## Dashboard

Generate a self-contained HTML status page from the SQLite database:

```bash
# Generate report and open in browser
python main.py --account grobomo --report

# Custom output path
python main.py --account grobomo --report --output status.html
```

The dashboard includes:
- Agent status cards (total events, 24h activity, actions taken)
- Event volume chart (SVG bar chart, last 24h by hour)
- Recent events table with type badges
- Action history (responses, alerts, dispatches)

## Project structure

```
main.py                    # CLI entry point + agent loop
core/
  store.py                 # EventStore — SQLite + FTS + WAL mode
  brain.py                 # LLM analyzer + rule-based fallback
  dispatcher.py            # Action executor (gh comment, email, CCC)
  context.py               # Context cache for brain prompts
  report.py                # HTML dashboard report generator
github/
  poller.py                # GitHub API polling via gh CLI
  normalizer.py            # Raw API → EventStore records
  settings.py              # Settings snapshot + drift detection
  gh_cli.py                # gh CLI wrapper
scripts/
  service.sh               # Continuous service launcher (Linux/Git Bash)
  service.bat              # Continuous service launcher (Windows)
  install-scheduler.sh     # Install/remove OS scheduled task
  run.sh                   # Run all accounts in parallel
tests/                     # 49 tests covering all modules
```

## Design decisions

- **One process per account** — security isolation between accounts
- **SQLite WAL mode** — concurrent reads during polling, busy_timeout for resilience
- **Rule-based fallback** — when `claude` CLI is unavailable, built-in rules handle common patterns (own pushes → IGNORE, security events → ALERT)
- **Settings drift detection** — snapshots repo settings each cycle, alerts on security-relevant changes with severity levels (critical/high/medium/low)
- **Source-agnostic core** — `core/` knows nothing about GitHub specifically, designed for reuse by other agents (Teams, Slack, etc.)

## Configuration

Create `config/accounts.yaml` to define accounts:

```yaml
accounts:
  grobomo:
    repos: []  # empty = auto-discover all repos
  another-account:
    repos:
      - owner/specific-repo
```

Or pass repos directly via CLI: `--repos owner/repo1 owner/repo2`

## License

MIT
