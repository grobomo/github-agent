"""HTML report generator — static dashboard from EventStore data.

Generates a self-contained HTML file with:
1. Agent status (last poll, uptime, error count, events/hour)
2. Recent events table (last 50)
3. Action history (non-IGNORE actions)
4. Event volume chart (SVG bar chart, last 24h)
"""

import json
import os
import webbrowser
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from core.store import EventStore


def _parse_ts(ts: str) -> Optional[datetime]:
    """Parse ISO timestamp string to datetime."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


def query_report_data(store: EventStore, account: str) -> dict:
    """Query all data needed for the report."""
    recent = store.get_recent(account=account, limit=50)
    all_24h = store.get_context_window(account=account, hours=24, limit=1000)
    total = store.count(account=account)

    # Actions taken (non-IGNORE, non-LOG)
    actions = [e for e in recent if e.get('action_taken')
               and json.loads(e['action_taken']).get('action') not in ('IGNORE', 'LOG', None)]

    # Hourly volume for last 24h
    now = datetime.now(timezone.utc)
    hourly = Counter()
    for e in all_24h:
        ts = _parse_ts(e.get('timestamp', ''))
        if ts:
            hour_key = ts.strftime('%Y-%m-%d %H:00')
            hourly[hour_key] += 1

    # Fill in all 25 hours
    hourly_data = []
    for i in range(24, -1, -1):
        hour = (now - timedelta(hours=i)).strftime('%Y-%m-%d %H:00')
        hourly_data.append({'hour': hour, 'label': hour[-5:], 'count': hourly.get(hour, 0)})

    # Event type breakdown
    type_counts = Counter(e.get('event_type', 'unknown') for e in all_24h)

    last_event_ts = recent[0].get('timestamp', '') if recent else 'N/A'

    return {
        'account': account,
        'total_events': total,
        'events_24h': len(all_24h),
        'last_event_ts': last_event_ts,
        'recent_events': recent[:50],
        'actions': actions[:20],
        'hourly_data': hourly_data,
        'type_counts': dict(type_counts.most_common(10)),
        'generated_at': now.strftime('%Y-%m-%d %H:%M:%S UTC'),
    }


def _svg_bar_chart(hourly_data: list[dict], width: int = 750, height: int = 200) -> str:
    """Generate an inline SVG bar chart of events per hour."""
    if not hourly_data:
        return '<p>No data for chart.</p>'

    max_count = max((d['count'] for d in hourly_data), default=1) or 1
    bar_width = width / len(hourly_data)
    padding = 2

    bars = []
    labels = []
    for i, d in enumerate(hourly_data):
        bar_h = (d['count'] / max_count) * (height - 30)
        x = i * bar_width
        y = height - 30 - bar_h
        bars.append(
            f'<rect x="{x + padding}" y="{y}" width="{bar_width - padding * 2}" '
            f'height="{bar_h}" fill="#4a90d9" rx="2">'
            f'<title>{d["hour"]}: {d["count"]} events</title></rect>'
        )
        if i % 4 == 0:
            labels.append(
                f'<text x="{x + bar_width / 2}" y="{height - 5}" '
                f'text-anchor="middle" font-size="11" fill="#666">{d["label"]}</text>'
            )

    return f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  {''.join(bars)}
  {''.join(labels)}
  <line x1="0" y1="{height - 30}" x2="{width}" y2="{height - 30}" stroke="#ccc" stroke-width="1"/>
</svg>'''


def _event_row(e: dict) -> str:
    """Render a single event as a table row."""
    ts = escape(str(e.get('timestamp', ''))[:19])
    etype = escape(str(e.get('event_type', '')))
    actor = escape(str(e.get('actor', '')))
    title = escape(str(e.get('title', '')))[:80]
    channel = escape(str(e.get('channel', '')))
    action = ''
    if e.get('action_taken'):
        try:
            a = json.loads(e['action_taken'])
            action = escape(str(a.get('action', '')))
        except (json.JSONDecodeError, TypeError):
            pass
    return (f'<tr><td>{ts}</td><td><span class="badge badge-{etype}">{etype}</span></td>'
            f'<td>{actor}</td><td>{channel}</td><td>{title}</td>'
            f'<td>{action}</td></tr>')


def _action_row(e: dict) -> str:
    """Render an action history row."""
    ts = escape(str(e.get('timestamp', ''))[:19])
    title = escape(str(e.get('title', '')))[:60]
    action_data = {}
    if e.get('action_taken'):
        try:
            action_data = json.loads(e['action_taken'])
        except (json.JSONDecodeError, TypeError):
            pass
    action = escape(str(action_data.get('action', '')))
    reason = escape(str(action_data.get('reason', '')))[:100]
    return f'<tr><td>{ts}</td><td><span class="badge badge-action">{action}</span></td><td>{title}</td><td>{reason}</td></tr>'


def generate_html(data: dict) -> str:
    """Generate the full HTML report."""
    event_rows = '\n'.join(_event_row(e) for e in data['recent_events'])
    action_rows = '\n'.join(_action_row(e) for e in data['actions'])
    chart_svg = _svg_bar_chart(data['hourly_data'])

    type_badges = ' '.join(
        f'<span class="badge badge-type">{escape(t)}: {c}</span>'
        for t, c in data['type_counts'].items()
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub Agent — {escape(data["account"])}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #f5f6f8; color: #333; padding: 20px; }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 1.6em; margin-bottom: 4px; color: #1a1a2e; }}
  .subtitle {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px;
           box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .card h2 {{ font-size: 1.15em; margin-bottom: 12px; color: #1a1a2e; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
  .stat {{ background: #f8f9fb; border-radius: 6px; padding: 14px; text-align: center; }}
  .stat .value {{ font-size: 1.8em; font-weight: 700; color: #4a90d9; }}
  .stat .label {{ font-size: 0.8em; color: #888; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
  th {{ background: #f8f9fb; padding: 8px 10px; text-align: left; font-weight: 600;
       border-bottom: 2px solid #e8e8e8; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }}
  tr:hover {{ background: #fafbfc; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px;
           font-size: 0.75em; font-weight: 600; }}
  .badge-issue {{ background: #e8f5e9; color: #2e7d32; }}
  .badge-pr {{ background: #e3f2fd; color: #1565c0; }}
  .badge-push {{ background: #fff3e0; color: #e65100; }}
  .badge-notification {{ background: #f3e5f5; color: #7b1fa2; }}
  .badge-settings_change {{ background: #fce4ec; color: #c62828; }}
  .badge-discussion {{ background: #e0f2f1; color: #00695c; }}
  .badge-workflow_run {{ background: #fafafa; color: #616161; }}
  .badge-action {{ background: #e8eaf6; color: #283593; }}
  .badge-type {{ background: #eceff1; color: #455a64; margin: 2px; }}
  .chart-container {{ overflow-x: auto; }}
  .empty {{ color: #999; font-style: italic; padding: 20px; text-align: center; }}
  .footer {{ text-align: center; color: #aaa; font-size: 0.8em; margin-top: 20px; }}
</style>
</head>
<body>
<div class="container">
  <h1>GitHub Agent Dashboard</h1>
  <p class="subtitle">Account: <strong>{escape(data["account"])}</strong> &middot; Generated: {escape(data["generated_at"])}</p>

  <div class="card">
    <h2>Agent Status</h2>
    <div class="stats">
      <div class="stat">
        <div class="value">{data["total_events"]}</div>
        <div class="label">Total Events</div>
      </div>
      <div class="stat">
        <div class="value">{data["events_24h"]}</div>
        <div class="label">Events (24h)</div>
      </div>
      <div class="stat">
        <div class="value">{len(data["actions"])}</div>
        <div class="label">Actions Taken</div>
      </div>
      <div class="stat">
        <div class="value">{escape(str(data["last_event_ts"])[:16])}</div>
        <div class="label">Last Event</div>
      </div>
    </div>
    <div style="margin-top: 12px;">
      {type_badges or '<span class="empty">No event types recorded</span>'}
    </div>
  </div>

  <div class="card">
    <h2>Event Volume (Last 24h)</h2>
    <div class="chart-container">
      {chart_svg}
    </div>
  </div>

  <div class="card">
    <h2>Recent Events</h2>
    {f"""<table>
      <thead><tr><th>Time</th><th>Type</th><th>Actor</th><th>Channel</th><th>Title</th><th>Action</th></tr></thead>
      <tbody>{event_rows}</tbody>
    </table>""" if event_rows else '<p class="empty">No events recorded yet.</p>'}
  </div>

  <div class="card">
    <h2>Action History</h2>
    {f"""<table>
      <thead><tr><th>Time</th><th>Action</th><th>Event</th><th>Reason</th></tr></thead>
      <tbody>{action_rows}</tbody>
    </table>""" if action_rows else '<p class="empty">No actions taken yet.</p>'}
  </div>

  <p class="footer">github-agent &middot; {escape(data["account"])} &middot; {escape(data["generated_at"])}</p>
</div>
</body>
</html>'''


def generate_report(store: EventStore, account: str,
                    output_path: Optional[str] = None,
                    open_browser: bool = True) -> str:
    """Generate HTML report and optionally open in browser. Returns output path."""
    data = query_report_data(store, account)
    html = generate_html(data)

    if not output_path:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        output_path = os.path.join(data_dir, f'{account}-report.html')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    if open_browser:
        webbrowser.open(f'file://{os.path.abspath(output_path)}')

    return output_path
