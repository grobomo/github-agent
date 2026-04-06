# Spec 004: Dashboard & Reporting

## Problem
The agent runs as a background service with logging to files and SQLite. There's no quick way to see:
- Is the agent healthy? When did it last poll?
- What events were detected recently?
- What actions were taken (responses, alerts, dispatches)?
- Are there any errors or repeated failures?

The health endpoint (`/healthz`) provides basic stats but no historical view.

## Design

### Static HTML Report Generator
Generate a self-contained HTML status page (like v1-report) from the SQLite database. No web server needed — just open the file in a browser.

Sections:
1. **Agent Status** — last poll time, uptime, error count, events/hour rate
2. **Recent Events** — last 50 events with type, actor, title, action taken
3. **Action History** — last 20 non-IGNORE actions with details
4. **Error Log** — recent errors from the agent log
5. **Event Volume Chart** — simple SVG bar chart of events per hour (last 24h)

### CLI Integration
```bash
python main.py --account grobomo --report          # generate and open
python main.py --account grobomo --report --output report.html  # custom path
```

### Auto-refresh
The report includes a timestamp and a "Refresh" button that re-runs the generator (via a small inline script that calls the CLI).

## Non-goals
- No live dashboard (no websockets, no server)
- No multi-account merged view (one report per account)
- No authentication (local file only)

## Success criteria
- `python main.py --account grobomo --report` generates a clean HTML file and opens it
- All 5 sections render with real data from the SQLite store
- Report looks professional (styled like v1-report)
- Existing tests still pass (no regressions)
