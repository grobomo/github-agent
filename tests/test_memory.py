"""T058: Tests for MemoryStore — CRUD, file I/O, schema validation, limits."""

import json
import os
import tempfile

from core.memory import (
    MemoryStore, REPO_MEMORY_TEMPLATE, ACCOUNT_MEMORY_TEMPLATE,
    MAX_MILESTONES, MAX_ACTION_LOG_ENTRIES,
)


def _make_store():
    d = tempfile.mkdtemp()
    return MemoryStore(memory_dir=d), d


def test_load_repo_memory_returns_template_when_missing():
    store, _ = _make_store()
    mem = store.load_repo_memory('acct', 'owner/repo')
    assert mem['purpose'] == ''
    assert mem['milestones'] == []
    assert mem['last_compacted_at'] is None


def test_save_and_load_repo_memory():
    store, _ = _make_store()
    mem = store.load_repo_memory('acct', 'owner/repo')
    mem['purpose'] = 'Test repo'
    mem['milestones'] = ['2024-01: Created']
    store.save_repo_memory('acct', 'owner/repo', mem)

    loaded = store.load_repo_memory('acct', 'owner/repo')
    assert loaded['purpose'] == 'Test repo'
    assert loaded['milestones'] == ['2024-01: Created']


def test_load_account_memory_returns_template():
    store, _ = _make_store()
    mem = store.load_account_memory('acct')
    assert mem['summary'] == ''
    assert mem['action_log'] == []


def test_save_and_load_account_memory():
    store, _ = _make_store()
    mem = store.load_account_memory('acct')
    mem['summary'] = 'Active account'
    store.save_account_memory('acct', mem)

    loaded = store.load_account_memory('acct')
    assert loaded['summary'] == 'Active account'


def test_list_repo_memories():
    store, _ = _make_store()
    store.save_repo_memory('acct', 'owner/repo1', {'purpose': 'one'})
    store.save_repo_memory('acct', 'owner/repo2', {'purpose': 'two'})
    store.save_repo_memory('acct', 'other/repo3', {'purpose': 'three'})

    repos = store.list_repo_memories('acct')
    assert repos == ['other/repo3', 'owner/repo1', 'owner/repo2']


def test_list_repo_memories_empty():
    store, _ = _make_store()
    assert store.list_repo_memories('nonexistent') == []


def test_append_action():
    store, _ = _make_store()
    store.append_action('acct', {'action': 'RESPOND', 'target': 'issue #1'})
    store.append_action('acct', {'action': 'ALERT', 'target': 'security'})

    mem = store.load_account_memory('acct')
    assert len(mem['action_log']) == 2
    assert mem['action_log'][0]['action'] == 'RESPOND'
    assert 'recorded_at' in mem['action_log'][0]


def test_get_memories_for_repos():
    store, _ = _make_store()
    store.save_repo_memory('acct', 'o/r1', {'purpose': 'one'})
    store.save_repo_memory('acct', 'o/r2', {'purpose': 'two'})

    result = store.get_memories_for_repos('acct', ['o/r1', 'o/r2', 'o/missing'])
    assert result['o/r1']['purpose'] == 'one'
    assert result['o/r2']['purpose'] == 'two'
    assert result['o/missing']['purpose'] == ''  # template for missing


def test_enforce_milestone_limit():
    store, _ = _make_store()
    mem = store.load_repo_memory('acct', 'o/r')
    mem['milestones'] = [f'item-{i}' for i in range(MAX_MILESTONES + 20)]
    store.save_repo_memory('acct', 'o/r', mem)

    loaded = store.load_repo_memory('acct', 'o/r')
    assert len(loaded['milestones']) <= MAX_MILESTONES


def test_enforce_action_log_limit():
    store, _ = _make_store()
    mem = store.load_account_memory('acct')
    mem['action_log'] = [{'action': f'a{i}'} for i in range(MAX_ACTION_LOG_ENTRIES + 50)]
    store.save_account_memory('acct', mem)

    loaded = store.load_account_memory('acct')
    assert len(loaded['action_log']) <= MAX_ACTION_LOG_ENTRIES


def test_repo_memory_merges_new_template_fields():
    """Existing memory files get new fields from template on load."""
    store, d = _make_store()
    # Save a minimal dict (simulating an old format)
    path = store._repo_path('acct', 'o/r')
    with open(path, 'w') as f:
        json.dump({'purpose': 'old'}, f)

    loaded = store.load_repo_memory('acct', 'o/r')
    assert loaded['purpose'] == 'old'
    assert 'milestones' in loaded  # new field from template
    assert loaded['milestones'] == []


def test_repo_without_slash_uses_account_as_owner():
    store, _ = _make_store()
    store.save_repo_memory('acct', 'simple-repo', {'purpose': 'test'})
    loaded = store.load_repo_memory('acct', 'simple-repo')
    assert loaded['purpose'] == 'test'
