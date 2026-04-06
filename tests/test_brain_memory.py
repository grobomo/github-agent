"""T060: Tests for enhanced brain prompt with memory injection."""

from core.brain import _build_context_prompt


def test_prompt_includes_account_memory():
    events = [{'event_id': 'e1', 'event_type': 'issue_opened', 'channel': 'gh:o/r',
               'actor': 'alice', 'timestamp': '2024-01-15T10:00:00Z', 'title': 'Bug'}]
    account_memory = {
        'summary': 'Active open-source account with 10 repos',
        'trajectory': 'Focus on CLI tools',
        'repo_relationships': ['repo-a depends on repo-b'],
        'action_log': [{'action': 'RESPOND', 'target': 'issue #5', 'reason': 'auto-ack'}],
    }

    prompt = _build_context_prompt(events, [], account_memory=account_memory)
    assert 'Active open-source account' in prompt
    assert 'Focus on CLI tools' in prompt
    assert 'repo-a depends on repo-b' in prompt
    assert 'RESPOND' in prompt


def test_prompt_includes_repo_memories():
    events = [{'event_id': 'e1', 'event_type': 'pr_opened', 'channel': 'gh:o/r',
               'actor': 'bob', 'timestamp': '2024-01-15', 'title': 'Fix'}]
    repo_memories = {
        'o/r': {
            'purpose': 'API wrapper for GitHub',
            'open_threads': ['Issue #3: Auth bug', 'PR #7: Add caching'],
            'milestones': ['2024-01: v1.0 released'],
            'key_collaborators': ['alice', 'bob'],
        }
    }

    prompt = _build_context_prompt(events, [], repo_memories=repo_memories)
    assert 'API wrapper for GitHub' in prompt
    assert 'Auth bug' in prompt
    assert 'v1.0 released' in prompt
    assert 'alice' in prompt


def test_prompt_without_memory_still_works():
    """Backward compatibility — no memory args should work fine."""
    events = [{'event_id': 'e1', 'event_type': 'push', 'channel': 'gh:o/r',
               'actor': 'me', 'timestamp': '2024-01-15', 'title': 'commit'}]
    history = [{'timestamp': '2024-01-14', 'event_type': 'push',
                'channel': 'gh:o/r', 'actor': 'me', 'title': 'prev commit'}]

    prompt = _build_context_prompt(events, history)
    assert 'New Events to Analyze' in prompt
    assert 'Recent Activity' in prompt


def test_prompt_skips_empty_repo_memories():
    events = [{'event_id': 'e1', 'event_type': 'push', 'channel': 'gh:o/r',
               'actor': 'me', 'timestamp': '2024-01-15', 'title': 'commit'}]
    repo_memories = {
        'o/r': {'purpose': '', 'open_threads': [], 'milestones': [], 'key_collaborators': []},
    }

    prompt = _build_context_prompt(events, [], repo_memories=repo_memories)
    # Empty repo memories should be skipped
    assert 'o/r' not in prompt.split('New Events')[0]


def test_prompt_memory_and_history_combined():
    """Memory + hot cache should both appear in prompt."""
    events = [{'event_id': 'e1', 'event_type': 'issue_opened', 'channel': 'gh:o/r',
               'actor': 'ext', 'timestamp': '2024-01-15', 'title': 'New bug'}]
    history = [{'timestamp': '2024-01-14', 'event_type': 'push',
                'channel': 'gh:o/r', 'actor': 'me', 'title': 'deploy fix'}]
    account_memory = {'summary': 'Test account', 'trajectory': '', 'repo_relationships': [], 'action_log': []}
    repo_memories = {'o/r': {'purpose': 'Main project', 'open_threads': ['Issue #1'], 'milestones': [], 'key_collaborators': []}}

    prompt = _build_context_prompt(events, history,
                                    account_memory=account_memory,
                                    repo_memories=repo_memories)
    assert 'Test account' in prompt
    assert 'Main project' in prompt
    assert 'Recent Activity' in prompt
    assert 'New Events to Analyze' in prompt


def test_prompt_limits_repo_memory_display():
    """Repo memories should limit threads/milestones shown in prompt."""
    events = [{'event_id': 'e1', 'event_type': 'push', 'channel': 'gh:o/r',
               'actor': 'me', 'timestamp': '2024-01-15', 'title': 'commit'}]
    repo_memories = {
        'o/r': {
            'purpose': 'Big repo',
            'open_threads': [f'Thread {i}' for i in range(50)],
            'milestones': [f'Milestone {i}' for i in range(50)],
            'key_collaborators': [f'user{i}' for i in range(50)],
        }
    }

    prompt = _build_context_prompt(events, [], repo_memories=repo_memories)
    # Should show limited threads (10), milestones (5), collaborators (10)
    assert 'Thread 0' in prompt
    assert 'Thread 9' in prompt
    assert 'Thread 10' not in prompt
