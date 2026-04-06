"""Normalizer — converts raw GitHub API responses into EventStore records.

Each normalize_* function takes raw gh output and returns a list of dicts
ready for EventStore.insert().
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_issue(issue: dict, account: str,
                    repo: str) -> dict:
    """Normalize a single issue into an event record."""
    author = issue.get('author', {})
    if isinstance(author, dict):
        actor = author.get('login', 'unknown')
    else:
        actor = str(author) if author else 'unknown'

    number = issue.get('number', 0)
    state = issue.get('state', 'OPEN')
    title = issue.get('title', '')
    body = issue.get('body', '') or ''

    event_type = 'issue_opened' if state == 'OPEN' else 'issue_closed'

    return {
        'source': 'github',
        'account': account,
        'channel': repo,
        'event_id': f'gh:{repo}:issue:{number}',
        'event_type': event_type,
        'actor': actor,
        'title': f'#{number}: {title}',
        'body': body[:4000],
        'metadata': {
            'number': number,
            'state': state,
            'labels': [l.get('name', '') for l in issue.get('labels', [])],
            'comment_count': len(issue.get('comments', [])),
        },
        'timestamp': issue.get('updatedAt', issue.get('createdAt', '')),
    }


def normalize_issue_comment(comment: dict, account: str, repo: str,
                            issue_number: int) -> dict:
    """Normalize an issue comment."""
    user = comment.get('user', {}) or {}
    actor = user.get('login', 'unknown')
    c_id = comment.get('id', 0)

    return {
        'source': 'github',
        'account': account,
        'channel': repo,
        'event_id': f'gh:{repo}:comment:{c_id}',
        'event_type': 'issue_comment',
        'actor': actor,
        'title': f'Comment on #{issue_number}',
        'body': (comment.get('body', '') or '')[:4000],
        'metadata': {
            'number': issue_number,
            'comment_id': c_id,
        },
        'timestamp': comment.get('updated_at',
                                  comment.get('created_at', '')),
    }


def normalize_pr(pr: dict, account: str, repo: str) -> dict:
    """Normalize a pull request."""
    author = pr.get('author', {})
    if isinstance(author, dict):
        actor = author.get('login', 'unknown')
    else:
        actor = str(author) if author else 'unknown'

    number = pr.get('number', 0)
    state = pr.get('state', 'OPEN')
    title = pr.get('title', '')
    body = pr.get('body', '') or ''

    if pr.get('mergedAt'):
        event_type = 'pr_merged'
    elif state == 'CLOSED':
        event_type = 'pr_closed'
    else:
        event_type = 'pr_opened'

    return {
        'source': 'github',
        'account': account,
        'channel': repo,
        'event_id': f'gh:{repo}:pr:{number}',
        'event_type': event_type,
        'actor': actor,
        'title': f'PR #{number}: {title}',
        'body': body[:4000],
        'metadata': {
            'number': number,
            'state': state,
            'branch': pr.get('headRefName', ''),
            'merged': bool(pr.get('mergedAt')),
            'review_count': len(pr.get('reviews', [])),
        },
        'timestamp': pr.get('updatedAt', pr.get('createdAt', '')),
    }


def normalize_event(event: dict, account: str, repo: str) -> dict:
    """Normalize a repo event (push, fork, etc.)."""
    etype = event.get('type', 'Unknown')
    actor = event.get('actor', {}).get('login', 'unknown')
    event_id = event.get('id', '')
    payload = event.get('payload', {})

    # Map GitHub event types to our types
    type_map = {
        'PushEvent': 'push',
        'CreateEvent': 'branch_created',
        'DeleteEvent': 'branch_deleted',
        'ForkEvent': 'fork',
        'WatchEvent': 'star',
        'IssuesEvent': 'issue_' + payload.get('action', 'unknown'),
        'PullRequestEvent': 'pr_' + payload.get('action', 'unknown'),
        'IssueCommentEvent': 'issue_comment',
        'PullRequestReviewEvent': 'pr_review',
        'ReleaseEvent': 'release',
        'MemberEvent': 'collaborator_' + payload.get('action', 'added'),
        'PublicEvent': 'visibility_change',
    }
    event_type = type_map.get(etype, etype.lower())

    title = ''
    if etype == 'PushEvent':
        commits = payload.get('commits', [])
        count = len(commits)
        title = f'{count} commit(s) pushed'
        if commits:
            title += f': {commits[-1].get("message", "")[:80]}'
    elif etype == 'CreateEvent':
        title = f'Created {payload.get("ref_type", "?")} {payload.get("ref", "")}'
    elif etype == 'MemberEvent':
        member = payload.get('member', {}).get('login', '?')
        title = f'Collaborator {payload.get("action", "added")}: {member}'
    elif etype == 'PublicEvent':
        title = 'Repository made public'

    return {
        'source': 'github',
        'account': account,
        'channel': repo,
        'event_id': f'gh:{repo}:event:{event_id}',
        'event_type': event_type,
        'actor': actor,
        'title': title,
        'body': '',
        'metadata': {
            'github_event_type': etype,
            'payload_keys': list(payload.keys())[:10],
        },
        'timestamp': event.get('created_at', ''),
    }


def normalize_workflow_run(run: dict, account: str,
                           repo: str) -> dict:
    """Normalize a workflow run (usually failures)."""
    return {
        'source': 'github',
        'account': account,
        'channel': repo,
        'event_id': f'gh:{repo}:run:{run.get("databaseId", 0)}',
        'event_type': 'workflow_failure',
        'actor': '',
        'title': f'Workflow failed: {run.get("name", "?")}',
        'body': '',
        'metadata': {
            'run_id': run.get('databaseId'),
            'name': run.get('name'),
            'status': run.get('status'),
            'conclusion': run.get('conclusion'),
            'branch': run.get('headBranch'),
            'event': run.get('event'),
        },
        'timestamp': run.get('updatedAt', run.get('createdAt', '')),
    }


def normalize_discussion(disc: dict, account: str,
                         repo: str) -> dict:
    """Normalize a discussion."""
    author = disc.get('author', {}) or {}
    actor = author.get('login', 'unknown')
    number = disc.get('number', 0)

    return {
        'source': 'github',
        'account': account,
        'channel': repo,
        'event_id': f'gh:{repo}:discussion:{number}',
        'event_type': 'discussion_created',
        'actor': actor,
        'title': f'Discussion #{number}: {disc.get("title", "")}',
        'body': (disc.get('body', '') or '')[:4000],
        'metadata': {
            'number': number,
            'category': disc.get('category', {}).get('name', ''),
            'comment_count': disc.get('comments', {}).get('totalCount', 0),
        },
        'timestamp': disc.get('updatedAt', disc.get('createdAt', '')),
    }


def normalize_notification(notif: dict, account: str) -> dict:
    """Normalize a notification."""
    repo = notif.get('repository', {}).get('full_name', '')
    subject = notif.get('subject', {})
    reason = notif.get('reason', '')

    return {
        'source': 'github',
        'account': account,
        'channel': repo,
        'event_id': f'gh:notif:{notif.get("id", "")}',
        'event_type': f'notification_{subject.get("type", "unknown").lower()}',
        'actor': '',
        'title': subject.get('title', ''),
        'body': '',
        'metadata': {
            'reason': reason,
            'subject_type': subject.get('type'),
            'subject_url': subject.get('url', ''),
            'unread': notif.get('unread', False),
        },
        'timestamp': notif.get('updated_at', ''),
    }
