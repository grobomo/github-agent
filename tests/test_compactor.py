"""T059: Tests for MemoryCompactor — mock LLM, incremental merge, skip unchanged."""

import json
import tempfile
from unittest.mock import patch, MagicMock

from core.store import EventStore
from core.memory import MemoryStore
from core.compactor import MemoryCompactor


def _setup():
    """Create in-memory store, temp memory dir, and compactor."""
    store = EventStore(':memory:')
    mem_dir = tempfile.mkdtemp()
    memory = MemoryStore(memory_dir=mem_dir)
    compactor = MemoryCompactor(store, memory, 'testacct')
    return store, memory, compactor


def _insert_event(store, channel='gh:owner/repo', event_type='issue_opened',
                   actor='someone', title='Test issue', timestamp='2024-01-15T10:00:00Z'):
    import time
    eid = f'{channel}:{event_type}:{timestamp}:{time.monotonic_ns()}'
    store.insert(
        source='github', account='testacct', channel=channel,
        event_id=eid, event_type=event_type, actor=actor,
        title=title, timestamp=timestamp,
    )


def test_compact_repo_skips_when_no_events():
    store, memory, compactor = _setup()
    assert compactor.compact_repo('owner/repo') is False


def test_compact_repo_fallback_creates_memory():
    store, memory, compactor = _setup()
    _insert_event(store, channel='gh:owner/repo', event_type='issue_opened',
                   title='Bug report', actor='alice')
    _insert_event(store, channel='gh:owner/repo', event_type='pr_merged',
                   title='Fix bug', actor='bob')

    # Patch LLM to fail so fallback is used
    with patch.object(compactor, '_call_llm', return_value=None):
        result = compactor.compact_repo('owner/repo')

    assert result is True
    mem = memory.load_repo_memory('testacct', 'owner/repo')
    assert mem['last_compacted_at'] is not None
    assert 'alice' in mem['key_collaborators']
    assert 'bob' in mem['key_collaborators']
    assert any('Bug report' in t for t in mem['open_threads'])
    assert any('Fix bug' in m for m in mem['milestones'])


def test_compact_repo_incremental():
    """Second compaction only processes new events."""
    store, memory, compactor = _setup()
    _insert_event(store, channel='gh:owner/repo', event_type='issue_opened',
                   title='First issue', timestamp='2024-01-10T10:00:00Z')

    with patch.object(compactor, '_call_llm', return_value=None):
        compactor.compact_repo('owner/repo')

    mem = memory.load_repo_memory('testacct', 'owner/repo')
    assert mem['event_count_at_compaction'] == 1

    # Add another event after compaction
    _insert_event(store, channel='gh:owner/repo', event_type='pr_opened',
                   title='New PR', timestamp='2024-01-15T12:00:00Z')

    with patch.object(compactor, '_call_llm', return_value=None):
        compactor.compact_repo('owner/repo')

    mem = memory.load_repo_memory('testacct', 'owner/repo')
    assert mem['event_count_at_compaction'] == 2
    assert any('New PR' in t for t in mem['open_threads'])


def test_compact_repos_multiple():
    store, memory, compactor = _setup()
    _insert_event(store, channel='gh:owner/repo1', title='Event A')
    _insert_event(store, channel='gh:owner/repo2', title='Event B')

    with patch.object(compactor, '_call_llm', return_value=None):
        count = compactor.compact_repos(['owner/repo1', 'owner/repo2', 'owner/empty'])

    assert count == 2  # repo1 and repo2 updated, empty skipped


def test_compact_account_fallback():
    store, memory, compactor = _setup()
    # Pre-populate repo memories
    memory.save_repo_memory('testacct', 'o/r1', {
        'purpose': 'API wrapper',
        'open_threads': ['Issue: Auth bug'],
        'milestones': ['2024-01: Initial release'],
        'pr_themes': ['security'],
    })
    memory.save_repo_memory('testacct', 'o/r2', {
        'purpose': 'CLI tool',
        'open_threads': [],
        'milestones': [],
        'pr_themes': ['ux'],
    })

    with patch.object(compactor, '_call_llm', return_value=None):
        result = compactor.compact_account()

    assert result is True
    acct = memory.load_account_memory('testacct')
    assert acct['last_compacted_at'] is not None
    assert '2' in acct['summary']  # mentions repo count


def test_compact_account_empty():
    store, memory, compactor = _setup()
    assert compactor.compact_account() is False


def test_compact_repo_with_llm_success():
    store, memory, compactor = _setup()
    _insert_event(store, channel='gh:owner/repo', title='Test')

    llm_response = {
        'purpose': 'LLM-generated purpose',
        'key_collaborators': ['alice'],
        'milestones': ['2024-01: Created'],
        'open_threads': [],
        'pr_themes': ['testing'],
        'recent_actions': [],
    }

    with patch.object(compactor, '_call_llm', return_value=llm_response):
        compactor.compact_repo('owner/repo')

    mem = memory.load_repo_memory('testacct', 'owner/repo')
    assert mem['purpose'] == 'LLM-generated purpose'


def test_fallback_closes_threads():
    store, memory, compactor = _setup()
    _insert_event(store, channel='gh:o/r', event_type='issue_opened',
                   title='Bug X', timestamp='2024-01-10T10:00:00Z')

    with patch.object(compactor, '_call_llm', return_value=None):
        compactor.compact_repo('o/r')

    mem = memory.load_repo_memory('testacct', 'o/r')
    assert 'Issue: Bug X' in mem['open_threads']

    # Close the issue
    _insert_event(store, channel='gh:o/r', event_type='issue_closed',
                   title='Bug X', timestamp='2024-01-15T10:00:00Z')

    with patch.object(compactor, '_call_llm', return_value=None):
        compactor.compact_repo('o/r')

    mem = memory.load_repo_memory('testacct', 'o/r')
    assert 'Issue: Bug X' not in mem['open_threads']
    assert any('Bug X' in m for m in mem['milestones'])


def test_compact_repo_handles_error_gracefully():
    store, memory, compactor = _setup()
    _insert_event(store, channel='gh:o/r', title='Test')

    with patch.object(compactor, '_call_llm', side_effect=Exception('boom')):
        # compact_repos catches per-repo errors
        count = compactor.compact_repos(['o/r'])

    assert count == 0
