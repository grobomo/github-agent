"""Repo settings snapshotter — captures security-relevant config for drift detection.

Snapshots: visibility, branch protection rules, collaborators (with roles),
installed apps/webhooks. Compares current vs previous snapshot to detect changes.
"""

import json
import logging
import os
from typing import Optional

from github.poller import gh_command

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'snapshots')


def get_repo_settings(owner: str, repo: str) -> dict:
    """Get basic repo settings (visibility, default branch, etc.)."""
    code, out, err = gh_command([
        'api', f'repos/{owner}/{repo}',
        '--jq', '{visibility,private,default_branch,has_wiki,'
                 'has_issues,has_projects,allow_forking,'
                 'delete_branch_on_merge,archived}',
    ])
    if code != 0:
        logger.error(f'Failed to get settings for {owner}/{repo}: {err}')
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def get_branch_protection(owner: str, repo: str,
                          branch: str = None) -> dict:
    """Get branch protection rules for the default or specified branch."""
    if not branch:
        settings = get_repo_settings(owner, repo)
        branch = settings.get('default_branch', 'main')

    code, out, err = gh_command([
        'api', f'repos/{owner}/{repo}/branches/{branch}/protection',
    ])
    if code != 0:
        if '404' in err or 'Not Found' in err:
            return {'protected': False, 'branch': branch}
        logger.debug(f'Branch protection query failed for {owner}/{repo}: {err}')
        return {'protected': False, 'branch': branch, 'error': err[:200]}
    try:
        raw = json.loads(out)
        return {
            'protected': True,
            'branch': branch,
            'enforce_admins': raw.get('enforce_admins', {}).get('enabled', False),
            'required_reviews': bool(raw.get('required_pull_request_reviews')),
            'required_status_checks': bool(raw.get('required_status_checks')),
            'restrictions': bool(raw.get('restrictions')),
            'allow_force_pushes': raw.get('allow_force_pushes', {}).get('enabled', False),
            'allow_deletions': raw.get('allow_deletions', {}).get('enabled', False),
        }
    except json.JSONDecodeError:
        return {'protected': False, 'branch': branch}


def get_collaborators(owner: str, repo: str) -> list[dict]:
    """Get collaborators with their permission levels."""
    code, out, err = gh_command([
        'api', f'repos/{owner}/{repo}/collaborators',
        '--paginate',
        '--jq', '[.[] | {login, role_name, permissions: .permissions}]',
    ], timeout=30)
    if code != 0:
        logger.debug(f'Collaborators query failed for {owner}/{repo}: {err}')
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def get_installed_apps(owner: str, repo: str) -> list[dict]:
    """Get apps/integrations installed on the repo."""
    code, out, err = gh_command([
        'api', f'repos/{owner}/{repo}/installations',
        '--jq', '[.installations[]? | {id, app_slug, permissions, events}]',
    ], timeout=30)
    if code != 0:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def get_webhooks(owner: str, repo: str) -> list[dict]:
    """Get webhooks configured on the repo."""
    code, out, err = gh_command([
        'api', f'repos/{owner}/{repo}/hooks',
        '--jq', '[.[] | {id, name, active, events, config: {url: .config.url}}]',
    ], timeout=30)
    if code != 0:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def snapshot_repo(owner: str, repo: str) -> dict:
    """Take a full settings snapshot of a repo."""
    return {
        'repo': f'{owner}/{repo}',
        'settings': get_repo_settings(owner, repo),
        'branch_protection': get_branch_protection(owner, repo),
        'collaborators': get_collaborators(owner, repo),
        'apps': get_installed_apps(owner, repo),
        'webhooks': get_webhooks(owner, repo),
    }


def _snapshot_path(owner: str, repo: str) -> str:
    """Path to the stored snapshot file for a repo."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    safe_name = f'{owner}_{repo}'.replace('/', '_')
    return os.path.join(SNAPSHOT_DIR, f'{safe_name}.json')


def save_snapshot(snapshot: dict) -> str:
    """Save snapshot to disk. Returns the file path."""
    repo = snapshot.get('repo', 'unknown')
    parts = repo.split('/', 1)
    owner, name = (parts[0], parts[1]) if len(parts) == 2 else (repo, repo)
    path = _snapshot_path(owner, name)
    with open(path, 'w') as f:
        json.dump(snapshot, f, indent=2)
    return path


def load_snapshot(owner: str, repo: str) -> Optional[dict]:
    """Load the previously saved snapshot, if any."""
    path = _snapshot_path(owner, repo)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def diff_snapshots(old: dict, new: dict) -> list[dict]:
    """Compare two snapshots. Returns list of changes with severity.

    Each change: {field, old_value, new_value, severity, description}
    Severity: critical, high, medium, low
    """
    changes = []

    # Visibility changes (critical)
    old_vis = old.get('settings', {}).get('visibility', '')
    new_vis = new.get('settings', {}).get('visibility', '')
    if old_vis and new_vis and old_vis != new_vis:
        changes.append({
            'field': 'visibility',
            'old_value': old_vis,
            'new_value': new_vis,
            'severity': 'critical',
            'description': f'Repository visibility changed: {old_vis} -> {new_vis}',
        })

    # Branch protection changes (high)
    old_bp = old.get('branch_protection', {})
    new_bp = new.get('branch_protection', {})
    if old_bp.get('protected') and not new_bp.get('protected'):
        changes.append({
            'field': 'branch_protection',
            'old_value': 'enabled',
            'new_value': 'disabled',
            'severity': 'critical',
            'description': f'Branch protection REMOVED on {new_bp.get("branch", "?")}',
        })
    elif old_bp.get('protected') and new_bp.get('protected'):
        for key in ('enforce_admins', 'required_reviews', 'required_status_checks',
                     'restrictions', 'allow_force_pushes', 'allow_deletions'):
            ov = old_bp.get(key)
            nv = new_bp.get(key)
            if ov is not None and nv is not None and ov != nv:
                sev = 'high'
                if key in ('allow_force_pushes', 'allow_deletions') and nv:
                    sev = 'critical'
                if key in ('required_reviews', 'required_status_checks') and not nv:
                    sev = 'high'
                changes.append({
                    'field': f'branch_protection.{key}',
                    'old_value': ov,
                    'new_value': nv,
                    'severity': sev,
                    'description': f'Branch protection {key}: {ov} -> {nv}',
                })

    # Collaborator changes (high for admin, medium otherwise)
    old_collabs = {c.get('login'): c for c in old.get('collaborators', [])}
    new_collabs = {c.get('login'): c for c in new.get('collaborators', [])}

    for login in set(new_collabs) - set(old_collabs):
        role = new_collabs[login].get('role_name', 'unknown')
        sev = 'high' if role == 'admin' else 'medium'
        changes.append({
            'field': 'collaborators',
            'old_value': None,
            'new_value': f'{login} ({role})',
            'severity': sev,
            'description': f'New collaborator added: {login} with {role} access',
        })

    for login in set(old_collabs) - set(new_collabs):
        changes.append({
            'field': 'collaborators',
            'old_value': login,
            'new_value': None,
            'severity': 'medium',
            'description': f'Collaborator removed: {login}',
        })

    for login in set(old_collabs) & set(new_collabs):
        old_role = old_collabs[login].get('role_name', '')
        new_role = new_collabs[login].get('role_name', '')
        if old_role and new_role and old_role != new_role:
            sev = 'high' if new_role == 'admin' else 'medium'
            changes.append({
                'field': 'collaborators',
                'old_value': f'{login} ({old_role})',
                'new_value': f'{login} ({new_role})',
                'severity': sev,
                'description': f'Collaborator {login} role changed: {old_role} -> {new_role}',
            })

    # App installation changes (high)
    old_apps = {a.get('app_slug', a.get('id')): a for a in old.get('apps', [])}
    new_apps = {a.get('app_slug', a.get('id')): a for a in new.get('apps', [])}

    for slug in set(new_apps) - set(old_apps):
        changes.append({
            'field': 'apps',
            'old_value': None,
            'new_value': slug,
            'severity': 'high',
            'description': f'New app installed: {slug}',
        })

    for slug in set(old_apps) - set(new_apps):
        changes.append({
            'field': 'apps',
            'old_value': slug,
            'new_value': None,
            'severity': 'medium',
            'description': f'App removed: {slug}',
        })

    # Webhook changes (medium)
    old_hooks = {h.get('id'): h for h in old.get('webhooks', [])}
    new_hooks = {h.get('id'): h for h in new.get('webhooks', [])}

    for hid in set(new_hooks) - set(old_hooks):
        url = new_hooks[hid].get('config', {}).get('url', '?')
        changes.append({
            'field': 'webhooks',
            'old_value': None,
            'new_value': f'id={hid} url={url}',
            'severity': 'medium',
            'description': f'New webhook added: {url}',
        })

    for hid in set(old_hooks) - set(new_hooks):
        changes.append({
            'field': 'webhooks',
            'old_value': f'id={hid}',
            'new_value': None,
            'severity': 'medium',
            'description': f'Webhook removed: id={hid}',
        })

    # General settings drift (low)
    for key in ('has_wiki', 'has_issues', 'has_projects', 'allow_forking',
                'delete_branch_on_merge', 'archived'):
        ov = old.get('settings', {}).get(key)
        nv = new.get('settings', {}).get(key)
        if ov is not None and nv is not None and ov != nv:
            sev = 'high' if key == 'archived' else 'low'
            changes.append({
                'field': f'settings.{key}',
                'old_value': ov,
                'new_value': nv,
                'severity': sev,
                'description': f'Setting {key}: {ov} -> {nv}',
            })

    return changes


def poll_settings(owner: str, repo: str) -> list[dict]:
    """Take a new snapshot, compare to previous, save, return changes."""
    new_snap = snapshot_repo(owner, repo)
    old_snap = load_snapshot(owner, repo)

    if old_snap is None:
        save_snapshot(new_snap)
        logger.info(f'First snapshot saved for {owner}/{repo}')
        return []

    changes = diff_snapshots(old_snap, new_snap)
    save_snapshot(new_snap)

    if changes:
        logger.warning(
            f'{len(changes)} settings change(s) detected for {owner}/{repo}'
        )
    return changes
