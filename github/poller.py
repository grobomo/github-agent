"""GitHub poller — polls all event types via gh CLI.

Uses gh_auto for account-aware authentication. Covers:
- Issues (opened, closed, commented, labeled)
- PRs (opened, reviewed, merged, CI status)
- Discussions (new, commented)
- Notifications (cross-repo activity feed)
- Repo events (pushes, forks, stars)
- Settings snapshots (for drift detection, separate module)
- Actions workflow runs (failures)
"""

import json
import logging
from typing import Optional

from github.gh_cli import gh_command, parse_json as _parse_json

logger = logging.getLogger(__name__)


def list_repos(account: str, limit: int = 200) -> list[dict]:
    """List all repos for a GitHub account."""
    code, out, err = gh_command([
        'repo', 'list', account,
        '--json', 'name,owner,isPrivate,updatedAt,description',
        '--limit', str(limit),
    ])
    if code != 0:
        logger.error(f'Failed to list repos for {account}: {err}')
        return []
    return _parse_json(out)


def get_notifications(since: Optional[str] = None) -> list[dict]:
    """Get GitHub notifications (cross-repo activity feed)."""
    args = ['api', 'notifications', '--paginate']
    if since:
        args.extend(['--field', f'since={since}'])
    code, out, err = gh_command(args, timeout=60)
    if code != 0:
        logger.error(f'Failed to get notifications: {err}')
        return []
    return _parse_json(out)


def get_issues(owner: str, repo: str, state: str = 'all',
               since: Optional[str] = None,
               limit: int = 50) -> list[dict]:
    """Get issues for a repo."""
    args = [
        'issue', 'list', '--repo', f'{owner}/{repo}',
        '--state', state,
        '--json', 'number,title,body,author,createdAt,updatedAt,'
                  'comments,labels,state',
        '--limit', str(limit),
    ]
    code, out, err = gh_command(args)
    if code != 0:
        logger.error(f'Failed to get issues for {owner}/{repo}: {err}')
        return []
    return _parse_json(out)


def get_issue_comments(owner: str, repo: str,
                       issue_number: int) -> list[dict]:
    """Get comments on an issue."""
    code, out, err = gh_command([
        'api', f'repos/{owner}/{repo}/issues/{issue_number}/comments',
    ])
    if code != 0:
        logger.error(
            f'Failed to get comments for {owner}/{repo}#{issue_number}: {err}'
        )
        return []
    return _parse_json(out)


def get_prs(owner: str, repo: str, state: str = 'all',
            limit: int = 50) -> list[dict]:
    """Get pull requests for a repo."""
    args = [
        'pr', 'list', '--repo', f'{owner}/{repo}',
        '--state', state,
        '--json', 'number,title,body,author,createdAt,updatedAt,'
                  'comments,reviews,state,mergedAt,headRefName',
        '--limit', str(limit),
    ]
    code, out, err = gh_command(args)
    if code != 0:
        logger.error(f'Failed to get PRs for {owner}/{repo}: {err}')
        return []
    return _parse_json(out)


def get_repo_events(owner: str, repo: str,
                    per_page: int = 30) -> list[dict]:
    """Get recent events for a repo (pushes, forks, etc.)."""
    code, out, err = gh_command([
        'api', f'repos/{owner}/{repo}/events',
        '--field', f'per_page={per_page}',
    ])
    if code != 0:
        logger.error(f'Failed to get events for {owner}/{repo}: {err}')
        return []
    return _parse_json(out)


def get_workflow_runs(owner: str, repo: str,
                     status: str = 'failure',
                     limit: int = 10) -> list[dict]:
    """Get recent workflow runs (default: failures only)."""
    args = [
        'run', 'list', '--repo', f'{owner}/{repo}',
        '--json', 'databaseId,name,status,conclusion,createdAt,'
                  'updatedAt,headBranch,event',
        '--limit', str(limit),
    ]
    if status:
        args.extend(['--status', status])
    code, out, err = gh_command(args)
    if code != 0:
        logger.error(f'Failed to get runs for {owner}/{repo}: {err}')
        return []
    return _parse_json(out)


def get_discussions(owner: str, repo: str,
                    limit: int = 20) -> list[dict]:
    """Get discussions for a repo (if enabled)."""
    # gh doesn't have a native discussions list command,
    # use GraphQL via gh api
    query = """query($owner: String!, $repo: String!, $first: Int!) {
      repository(owner: $owner, name: $repo) {
        discussions(first: $first, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            number
            title
            body
            author { login }
            createdAt
            updatedAt
            comments { totalCount }
            category { name }
          }
        }
      }
    }"""
    code, out, err = gh_command([
        'api', 'graphql',
        '-f', f'query={query}',
        '-f', f'owner={owner}',
        '-f', f'repo={repo}',
        '-F', f'first={limit}',
    ], timeout=30)
    if code != 0:
        # Discussions may not be enabled
        if 'not found' in err.lower() or 'disabled' in err.lower():
            return []
        logger.debug(f'Discussions not available for {owner}/{repo}')
        return []
    try:
        data = json.loads(out)
        return (data.get('data', {}).get('repository', {})
                .get('discussions', {}).get('nodes', []))
    except (json.JSONDecodeError, AttributeError):
        return []


def post_comment(owner: str, repo: str, number: int,
                 body: str) -> bool:
    """Post a comment on an issue or PR."""
    code, out, err = gh_command([
        'issue', 'comment', str(number),
        '--repo', f'{owner}/{repo}',
        '--body', body,
    ])
    if code != 0:
        logger.error(f'Failed to comment on {owner}/{repo}#{number}: {err}')
        return False
    return True


class GitHubPoller:
    """Polls GitHub repos for all event types."""

    def __init__(self, account: str, repos: Optional[list[str]] = None):
        """
        Args:
            account: GitHub account name (e.g., 'grobomo')
            repos: Specific repos to monitor. If None, discovers all.
        """
        self.account = account
        self._explicit_repos = repos
        self._repos: list[str] = []

    def discover_repos(self) -> list[str]:
        """Discover all repos from the account."""
        raw = list_repos(self.account)
        repos = []
        for r in raw:
            owner = r.get('owner', {}).get('login', self.account)
            name = r.get('name', '')
            if name:
                repos.append(f'{owner}/{name}')
        self._repos = repos
        logger.info(f'Discovered {len(repos)} repos for {self.account}')
        return repos

    @property
    def repos(self) -> list[str]:
        if self._explicit_repos:
            return self._explicit_repos
        if not self._repos:
            self.discover_repos()
        return self._repos

    def poll_issues(self, owner: str, repo: str) -> list[dict]:
        """Poll issues + comments for a repo. Returns raw API data."""
        return get_issues(owner, repo)

    def poll_prs(self, owner: str, repo: str) -> list[dict]:
        return get_prs(owner, repo)

    def poll_events(self, owner: str, repo: str) -> list[dict]:
        return get_repo_events(owner, repo)

    def poll_workflow_failures(self, owner: str, repo: str) -> list[dict]:
        return get_workflow_runs(owner, repo, status='failure')

    def poll_discussions(self, owner: str, repo: str) -> list[dict]:
        return get_discussions(owner, repo)

    def poll_notifications(self) -> list[dict]:
        return get_notifications()

    def poll_all(self) -> dict:
        """Poll everything. Returns dict keyed by event type."""
        results = {
            'issues': {},
            'prs': {},
            'events': {},
            'workflow_failures': {},
            'discussions': {},
            'notifications': [],
        }

        results['notifications'] = self.poll_notifications()

        for repo_str in self.repos:
            parts = repo_str.split('/', 1)
            if len(parts) != 2:
                continue
            owner, repo = parts
            try:
                results['issues'][repo_str] = self.poll_issues(owner, repo)
                results['prs'][repo_str] = self.poll_prs(owner, repo)
                results['events'][repo_str] = self.poll_events(owner, repo)
                results['workflow_failures'][repo_str] = (
                    self.poll_workflow_failures(owner, repo)
                )
                results['discussions'][repo_str] = (
                    self.poll_discussions(owner, repo)
                )
            except Exception as e:
                logger.error(f'Failed to poll {repo_str}: {e}')

        return results
