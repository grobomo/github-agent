"""Tests for core.report — HTML dashboard generation."""

import json
import os
import tempfile

from core.store import EventStore
from core.report import query_report_data, generate_html, generate_report, _svg_bar_chart


def _make_store_with_events(n=10):
    """Create an in-memory store with sample events."""
    store = EventStore(':memory:')
    for i in range(n):
        action = None
        if i == 0:
            action = json.dumps({'action': 'RESPOND', 'reason': 'Answered question'})
        elif i == 1:
            action = json.dumps({'action': 'ALERT', 'reason': 'Visibility changed'})
        store.insert(
            source='github', account='testacct', channel=f'owner/repo-{i % 3}',
            event_id=f'gh:test:issue:{i}', event_type='issue' if i % 2 == 0 else 'pr',
            actor=f'user-{i}', title=f'Test event #{i}',
            body=f'Body of event {i}', timestamp=f'2026-04-06T{10 + i}:00:00Z',
        )
        if action:
            store.mark_actioned(f'gh:test:issue:{i}', json.loads(action))
    return store


def test_query_report_data_basic():
    store = _make_store_with_events(5)
    data = query_report_data(store, 'testacct')
    assert data['account'] == 'testacct'
    assert data['total_events'] == 5
    assert len(data['recent_events']) == 5
    assert len(data['hourly_data']) == 25  # 24h + current hour
    assert 'generated_at' in data
    store.close()


def test_query_report_data_empty():
    store = EventStore(':memory:')
    data = query_report_data(store, 'empty')
    assert data['total_events'] == 0
    assert data['recent_events'] == []
    assert data['actions'] == []
    assert data['last_event_ts'] == 'N/A'
    store.close()


def test_query_report_data_actions():
    store = _make_store_with_events(10)
    data = query_report_data(store, 'testacct')
    # Events 0 (RESPOND) and 1 (ALERT) should appear in actions
    assert len(data['actions']) >= 1
    store.close()


def test_generate_html_structure():
    store = _make_store_with_events(5)
    data = query_report_data(store, 'testacct')
    html = generate_html(data)
    assert '<!DOCTYPE html>' in html
    assert 'GitHub Agent Dashboard' in html
    assert 'testacct' in html
    assert 'Total Events' in html
    assert 'Recent Events' in html
    assert 'Action History' in html
    assert '<svg' in html  # bar chart
    store.close()


def test_generate_html_empty():
    store = EventStore(':memory:')
    data = query_report_data(store, 'empty')
    html = generate_html(data)
    assert 'No events recorded yet.' in html
    assert 'No actions taken yet.' in html
    store.close()


def test_generate_html_escapes_xss():
    store = EventStore(':memory:')
    store.insert(
        source='github', account='testacct', channel='owner/repo',
        event_id='xss:1', event_type='issue',
        actor='<script>alert(1)</script>', title='<img onerror=alert(1)>',
        body='normal', timestamp='2026-04-06T12:00:00Z',
    )
    data = query_report_data(store, 'testacct')
    html = generate_html(data)
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert '<img onerror' not in html
    store.close()


def test_svg_bar_chart():
    hourly = [{'hour': f'2026-04-06 {h:02d}:00', 'label': f'{h:02d}:00', 'count': h}
              for h in range(25)]
    svg = _svg_bar_chart(hourly)
    assert '<svg' in svg
    assert '<rect' in svg
    assert 'events</title>' in svg


def test_svg_bar_chart_empty():
    result = _svg_bar_chart([])
    assert 'No data' in result


def test_generate_report_writes_file():
    store = _make_store_with_events(3)
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, 'test-report.html')
        path = generate_report(store, 'testacct', output_path=out, open_browser=False)
        assert path == out
        assert os.path.exists(out)
        with open(out, encoding='utf-8') as f:
            content = f.read()
        assert 'GitHub Agent Dashboard' in content
        assert 'testacct' in content
    store.close()


def test_type_counts_in_report():
    store = _make_store_with_events(10)
    data = query_report_data(store, 'testacct')
    assert 'issue' in data['type_counts'] or 'pr' in data['type_counts']
    store.close()
