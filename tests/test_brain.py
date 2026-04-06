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


def test_fallback_own_events_log():
    """Own issue/PR activity should LOG, not RESPOND."""
    for etype in ['issue_opened', 'pr_opened']:
        events = [{'event_id': f'evt-{etype}', 'event_type': etype,
                    'actor': 'myaccount', 'account': 'myaccount'}]
        decisions = _fallback_decisions(events)
        assert decisions[0]['action'] == 'LOG', f'Own {etype} should LOG'

    # discussion_created always LOGs
    events = [{'event_id': 'evt-disc', 'event_type': 'discussion_created',
                'actor': 'other', 'account': 'myaccount'}]
    decisions = _fallback_decisions(events)
    assert decisions[0]['action'] == 'LOG'


def test_fallback_unknown_event():
    events = [{'event_id': 'evt-x', 'event_type': 'some_random_type'}]
    decisions = _fallback_decisions(events)
    assert decisions[0]['action'] == 'LOG'
    assert decisions[0]['urgency'] == 'low'


def test_fallback_multiple_events():
    events = [
        {'event_id': 'evt-1', 'event_type': 'push', 'actor': 'me', 'account': 'me'},
        {'event_id': 'evt-2', 'event_type': 'visibility_change', 'actor': 'x', 'account': 'me'},
        {'event_id': 'evt-3', 'event_type': 'issue_opened', 'actor': 'me', 'account': 'me'},
    ]
    decisions = _fallback_decisions(events)
    assert len(decisions) == 3
    assert decisions[1]['action'] == 'ALERT'
    assert decisions[2]['action'] == 'LOG'  # own issue


def test_fallback_empty():
    assert _fallback_decisions([]) == []


def test_fallback_external_issue_responds():
    """External issue should trigger RESPOND with acknowledgment."""
    events = [{'event_id': 'evt-1', 'event_type': 'issue_opened',
                'actor': 'contributor', 'account': 'myaccount',
                'channel': 'myaccount/repo'}]
    decisions = _fallback_decisions(events)
    assert decisions[0]['action'] == 'RESPOND'
    assert 'response_body' in decisions[0]
    assert 'github-agent' in decisions[0]['response_body'].lower()


def test_fallback_external_pr_responds():
    """External PR should trigger RESPOND with acknowledgment."""
    events = [{'event_id': 'evt-1', 'event_type': 'pr_opened',
                'actor': 'contributor', 'account': 'myaccount'}]
    decisions = _fallback_decisions(events)
    assert decisions[0]['action'] == 'RESPOND'
    assert 'response_body' in decisions[0]


def test_fallback_own_issue_no_respond():
    """Own issue should LOG, not RESPOND."""
    events = [{'event_id': 'evt-1', 'event_type': 'issue_opened',
                'actor': 'myaccount', 'account': 'myaccount'}]
    decisions = _fallback_decisions(events)
    assert decisions[0]['action'] == 'LOG'
    assert 'response_body' not in decisions[0]


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
