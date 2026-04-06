"""T017: Test brain fallback — when claude -p unavailable, rule-based decisions work."""

from core.brain import _fallback_decisions, _build_context_prompt


def test_fallback_security_events():
    """Security-sensitive events should trigger ALERT."""
    security_types = [
        'visibility_change', 'branch_protection_change',
        'collaborator_added', 'app_installed',
    ]
    for etype in security_types:
        events = [{'event_id': f'evt-{etype}', 'event_type': etype}]
        decisions = _fallback_decisions(events)
        assert len(decisions) == 1
        assert decisions[0]['action'] == 'ALERT', f'{etype} should be ALERT'
        assert decisions[0]['urgency'] == 'high'


def test_fallback_workflow_failure():
    events = [{'event_id': 'evt-wf', 'event_type': 'workflow_failure',
               'channel': 'repo/x'}]
    decisions = _fallback_decisions(events)
    assert decisions[0]['action'] == 'ALERT'
    assert decisions[0]['urgency'] == 'medium'


def test_fallback_normal_events():
    """Normal events should LOG."""
    normal_types = ['issue_opened', 'pr_opened', 'discussion_created']
    for etype in normal_types:
        events = [{'event_id': f'evt-{etype}', 'event_type': etype}]
        decisions = _fallback_decisions(events)
        assert decisions[0]['action'] == 'LOG'


def test_fallback_unknown_event():
    events = [{'event_id': 'evt-x', 'event_type': 'some_random_type'}]
    decisions = _fallback_decisions(events)
    assert decisions[0]['action'] == 'LOG'
    assert decisions[0]['urgency'] == 'low'


def test_fallback_multiple_events():
    events = [
        {'event_id': 'evt-1', 'event_type': 'push'},
        {'event_id': 'evt-2', 'event_type': 'visibility_change'},
        {'event_id': 'evt-3', 'event_type': 'issue_opened'},
    ]
    decisions = _fallback_decisions(events)
    assert len(decisions) == 3
    assert decisions[1]['action'] == 'ALERT'


def test_fallback_empty():
    assert _fallback_decisions([]) == []


def test_build_prompt_with_context_summary():
    """When account_info has context_summary, it should appear in prompt."""
    new = [{'event_id': 'e1', 'event_type': 'push', 'account': 'a',
            'channel': 'r', 'actor': 'x', 'title': 'commit'}]
    prompt = _build_context_prompt(new, [], {
        'account': 'a',
        'context_summary': '## Active Issues\n- repo: bug #1',
    })
    assert 'Active Issues' in prompt
    assert 'New Events to Analyze' in prompt


def test_build_prompt_raw_history_fallback():
    """Without context_summary, raw history should be used."""
    new = [{'event_id': 'e1', 'event_type': 'push'}]
    history = [{'timestamp': 'T', 'event_type': 'push',
                'channel': 'r', 'actor': 'x', 'title': 'msg'}]
    prompt = _build_context_prompt(new, history, {'account': 'a'})
    assert 'Recent Activity' in prompt


def test_build_prompt_no_history():
    new = [{'event_id': 'e1', 'event_type': 'push'}]
    prompt = _build_context_prompt(new, [], None)
    assert 'New Events to Analyze' in prompt


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:
        t()
        print(f'  {t.__name__}: OK')
    print(f'ALL {len(tests)} TESTS PASSED')
