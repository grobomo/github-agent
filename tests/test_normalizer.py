"""T016: Test normalizer — verify all event types convert correctly."""

from github.normalizer import (
    normalize_issue, normalize_issue_comment, normalize_pr,
    normalize_event, normalize_workflow_run, normalize_discussion,
    normalize_notification, normalize_settings_change,
)

ACCOUNT = 'testacct'
REPO = 'testacct/testrepo'


def test_normalize_issue_open():
    raw = {
        'number': 42,
        'title': 'Bug report',
        'body': 'Something is broken',
        'state': 'OPEN',
        'author': {'login': 'alice'},
        'labels': [{'name': 'bug'}],
        'comments': [],
        'createdAt': '2026-04-05T10:00:00Z',
        'updatedAt': '2026-04-05T10:00:00Z',
    }
    r = normalize_issue(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'issue_opened'
    assert r['actor'] == 'alice'
    assert '#42' in r['title']
    assert r['source'] == 'github'
    assert r['channel'] == REPO
    assert r['metadata']['labels'] == ['bug']


def test_normalize_issue_closed():
    raw = {
        'number': 42, 'title': 'Bug', 'state': 'CLOSED',
        'author': {'login': 'alice'}, 'labels': [], 'comments': [],
        'createdAt': '2026-04-05T10:00:00Z',
    }
    r = normalize_issue(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'issue_closed'


def test_normalize_issue_author_string():
    """Handle author as string instead of dict."""
    raw = {
        'number': 1, 'title': 'X', 'state': 'OPEN',
        'author': 'somebot', 'labels': [], 'comments': [],
        'createdAt': '2026-04-05T10:00:00Z',
    }
    r = normalize_issue(raw, ACCOUNT, REPO)
    assert r['actor'] == 'somebot'


def test_normalize_issue_comment():
    raw = {
        'id': 99, 'body': 'I can reproduce this',
        'user': {'login': 'bob'},
        'created_at': '2026-04-05T11:00:00Z',
    }
    r = normalize_issue_comment(raw, ACCOUNT, REPO, 42)
    assert r['event_type'] == 'issue_comment'
    assert r['actor'] == 'bob'
    assert '42' in r['title']


def test_normalize_pr_open():
    raw = {
        'number': 10, 'title': 'Add feature', 'body': 'Implements X',
        'state': 'OPEN', 'author': {'login': 'charlie'},
        'headRefName': 'feature-x', 'reviews': [],
        'createdAt': '2026-04-05T10:00:00Z',
        'updatedAt': '2026-04-05T12:00:00Z',
    }
    r = normalize_pr(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'pr_opened'
    assert r['metadata']['branch'] == 'feature-x'


def test_normalize_pr_merged():
    raw = {
        'number': 10, 'title': 'Add feature', 'state': 'CLOSED',
        'author': {'login': 'charlie'}, 'headRefName': 'feature-x',
        'mergedAt': '2026-04-05T14:00:00Z', 'reviews': [{}],
        'createdAt': '2026-04-05T10:00:00Z',
    }
    r = normalize_pr(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'pr_merged'
    assert r['metadata']['merged'] is True


def test_normalize_pr_closed():
    raw = {
        'number': 10, 'title': 'Nope', 'state': 'CLOSED',
        'author': {'login': 'charlie'}, 'headRefName': 'nope',
        'reviews': [],
        'createdAt': '2026-04-05T10:00:00Z',
    }
    r = normalize_pr(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'pr_closed'


def test_normalize_event_push():
    raw = {
        'id': '123', 'type': 'PushEvent',
        'actor': {'login': 'dave'},
        'payload': {'commits': [{'message': 'fix typo'}]},
        'created_at': '2026-04-05T10:00:00Z',
    }
    r = normalize_event(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'push'
    assert 'fix typo' in r['title']


def test_normalize_event_member():
    raw = {
        'id': '456', 'type': 'MemberEvent',
        'actor': {'login': 'admin'},
        'payload': {'action': 'added', 'member': {'login': 'newuser'}},
        'created_at': '2026-04-05T10:00:00Z',
    }
    r = normalize_event(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'collaborator_added'
    assert 'newuser' in r['title']


def test_normalize_event_public():
    raw = {
        'id': '789', 'type': 'PublicEvent',
        'actor': {'login': 'admin'},
        'payload': {},
        'created_at': '2026-04-05T10:00:00Z',
    }
    r = normalize_event(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'visibility_change'


def test_normalize_workflow_run():
    raw = {
        'databaseId': 555, 'name': 'CI', 'status': 'completed',
        'conclusion': 'failure', 'headBranch': 'main', 'event': 'push',
        'createdAt': '2026-04-05T10:00:00Z',
        'updatedAt': '2026-04-05T10:05:00Z',
    }
    r = normalize_workflow_run(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'workflow_failure'
    assert 'CI' in r['title']
    assert r['metadata']['conclusion'] == 'failure'


def test_normalize_discussion():
    raw = {
        'number': 7, 'title': 'RFC: new feature',
        'body': 'What do you think?',
        'author': {'login': 'eve'},
        'category': {'name': 'Ideas'},
        'comments': {'totalCount': 3},
        'createdAt': '2026-04-05T10:00:00Z',
        'updatedAt': '2026-04-05T12:00:00Z',
    }
    r = normalize_discussion(raw, ACCOUNT, REPO)
    assert r['event_type'] == 'discussion_created'
    assert r['metadata']['category'] == 'Ideas'
    assert r['metadata']['comment_count'] == 3


def test_normalize_notification():
    raw = {
        'id': 'notif-1',
        'repository': {'full_name': 'testacct/testrepo'},
        'subject': {'type': 'Issue', 'title': 'Bug #42', 'url': ''},
        'reason': 'mention',
        'unread': True,
        'updated_at': '2026-04-05T10:00:00Z',
    }
    r = normalize_notification(raw, ACCOUNT)
    assert r['event_type'] == 'notification_issue'
    assert r['metadata']['reason'] == 'mention'


def test_normalize_settings_change():
    change = {
        'field': 'visibility',
        'old_value': 'private',
        'new_value': 'public',
        'severity': 'critical',
        'description': 'Repository visibility changed to public',
    }
    r = normalize_settings_change(change, ACCOUNT, REPO)
    assert 'settings_visibility' in r['event_type']
    assert r['metadata']['severity'] == 'critical'


def test_all_records_have_required_fields():
    """Every normalize function must return all required EventStore fields."""
    required = {'source', 'account', 'channel', 'event_id',
                'event_type', 'actor', 'title', 'body', 'timestamp'}

    records = [
        normalize_issue({'number': 1, 'title': 'X', 'state': 'OPEN',
                        'author': {'login': 'a'}, 'labels': [], 'comments': [],
                        'createdAt': 'T'}, ACCOUNT, REPO),
        normalize_pr({'number': 1, 'title': 'X', 'state': 'OPEN',
                     'author': {'login': 'a'}, 'headRefName': '', 'reviews': [],
                     'createdAt': 'T'}, ACCOUNT, REPO),
        normalize_event({'id': '1', 'type': 'PushEvent',
                        'actor': {'login': 'a'}, 'payload': {'commits': []},
                        'created_at': 'T'}, ACCOUNT, REPO),
        normalize_workflow_run({'databaseId': 1, 'name': 'CI',
                               'createdAt': 'T'}, ACCOUNT, REPO),
        normalize_discussion({'number': 1, 'title': 'X',
                             'author': {'login': 'a'},
                             'createdAt': 'T'}, ACCOUNT, REPO),
        normalize_notification({'id': '1', 'repository': {'full_name': REPO},
                               'subject': {'type': 'Issue', 'title': 'X'},
                               'updated_at': 'T'}, ACCOUNT),
        normalize_settings_change({'field': 'x', 'severity': 'low',
                                  'description': 'X'}, ACCOUNT, REPO),
    ]
    for r in records:
        missing = required - set(r.keys())
        assert not missing, f'{r["event_type"]}: missing {missing}'


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:
        t()
        print(f'  {t.__name__}: OK')
    print(f'ALL {len(tests)} TESTS PASSED')
