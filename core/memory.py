"""Three-tier memory system for long-term brain context.

Tier 1: Hot Cache (existing ContextCache — 24h events)
Tier 2: Repo Memory (per-repo JSON — purpose, milestones, threads)
Tier 3: Account Memory (cross-repo awareness, action log)

File layout:
  data/memory/{account}/repos/{owner}/{repo}.json  (Tier 2)
  data/memory/{account}/account.json               (Tier 3)
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_DIR = str(Path(__file__).parent.parent / 'data' / 'memory')

REPO_MEMORY_TEMPLATE = {
    'purpose': '',
    'description': '',
    'key_collaborators': [],
    'milestones': [],
    'open_threads': [],
    'pr_themes': [],
    'recent_actions': [],
    'last_compacted_at': None,
    'event_count_at_compaction': 0,
}

ACCOUNT_MEMORY_TEMPLATE = {
    'summary': '',
    'repo_relationships': [],
    'trajectory': '',
    'action_log': [],
    'last_compacted_at': None,
}

MAX_REPO_MEMORY_SIZE = 50_000  # chars — truncate oldest sections beyond this
MAX_ACTION_LOG_ENTRIES = 200
MAX_MILESTONES = 50
MAX_OPEN_THREADS = 30


class MemoryStore:
    """File-based memory store for per-repo and per-account context."""

    def __init__(self, memory_dir: Optional[str] = None):
        self.memory_dir = memory_dir or DEFAULT_MEMORY_DIR
        os.makedirs(self.memory_dir, exist_ok=True)

    def _repo_path(self, account: str, repo_full_name: str) -> str:
        """Get file path for a repo memory. repo_full_name is 'owner/repo'."""
        parts = repo_full_name.split('/', 1)
        if len(parts) == 2:
            owner, repo = parts
        else:
            owner, repo = account, parts[0]
        path = os.path.join(self.memory_dir, account, 'repos', owner, f'{repo}.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def _account_path(self, account: str) -> str:
        path = os.path.join(self.memory_dir, account, 'account.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def load_repo_memory(self, account: str, repo_full_name: str) -> dict:
        """Load repo memory, returning template if not found."""
        path = self._repo_path(account, repo_full_name)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Merge with template to add any new fields
            merged = {**REPO_MEMORY_TEMPLATE, **data}
            return merged
        except (FileNotFoundError, json.JSONDecodeError):
            return dict(REPO_MEMORY_TEMPLATE)

    def save_repo_memory(self, account: str, repo_full_name: str, memory: dict):
        """Save repo memory, enforcing size limits."""
        memory = self._enforce_repo_limits(memory)
        path = self._repo_path(account, repo_full_name)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, default=str)
        logger.debug(f'Saved repo memory: {path}')

    def load_account_memory(self, account: str) -> dict:
        """Load account memory, returning template if not found."""
        path = self._account_path(account)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {**ACCOUNT_MEMORY_TEMPLATE, **data}
        except (FileNotFoundError, json.JSONDecodeError):
            return dict(ACCOUNT_MEMORY_TEMPLATE)

    def save_account_memory(self, account: str, memory: dict):
        """Save account memory, enforcing limits."""
        memory = self._enforce_account_limits(memory)
        path = self._account_path(account)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, default=str)
        logger.debug(f'Saved account memory: {path}')

    def list_repo_memories(self, account: str) -> list[str]:
        """List all repo full names with existing memory files."""
        repos_dir = os.path.join(self.memory_dir, account, 'repos')
        if not os.path.isdir(repos_dir):
            return []
        result = []
        for owner in os.listdir(repos_dir):
            owner_dir = os.path.join(repos_dir, owner)
            if not os.path.isdir(owner_dir):
                continue
            for fname in os.listdir(owner_dir):
                if fname.endswith('.json'):
                    repo = fname[:-5]
                    result.append(f'{owner}/{repo}')
        return sorted(result)

    def append_action(self, account: str, action: dict):
        """Append an action to the account action log."""
        mem = self.load_account_memory(account)
        action['recorded_at'] = datetime.now(timezone.utc).isoformat()
        mem['action_log'].append(action)
        self.save_account_memory(account, mem)

    def get_memories_for_repos(self, account: str,
                                repo_names: list[str]) -> dict[str, dict]:
        """Load memories for specific repos. Returns {repo_name: memory}."""
        result = {}
        for repo in repo_names:
            result[repo] = self.load_repo_memory(account, repo)
        return result

    def _enforce_repo_limits(self, memory: dict) -> dict:
        """Truncate repo memory to stay within size limits."""
        if len(memory.get('milestones', [])) > MAX_MILESTONES:
            memory['milestones'] = memory['milestones'][-MAX_MILESTONES:]
        if len(memory.get('open_threads', [])) > MAX_OPEN_THREADS:
            memory['open_threads'] = memory['open_threads'][-MAX_OPEN_THREADS:]
        if len(memory.get('recent_actions', [])) > MAX_ACTION_LOG_ENTRIES:
            memory['recent_actions'] = memory['recent_actions'][-MAX_ACTION_LOG_ENTRIES:]

        serialized = json.dumps(memory, default=str)
        if len(serialized) > MAX_REPO_MEMORY_SIZE:
            # Trim oldest milestones and threads to fit
            while len(serialized) > MAX_REPO_MEMORY_SIZE and memory.get('milestones'):
                memory['milestones'] = memory['milestones'][1:]
                serialized = json.dumps(memory, default=str)
            while len(serialized) > MAX_REPO_MEMORY_SIZE and memory.get('open_threads'):
                memory['open_threads'] = memory['open_threads'][1:]
                serialized = json.dumps(memory, default=str)
        return memory

    def _enforce_account_limits(self, memory: dict) -> dict:
        """Truncate account memory action log."""
        if len(memory.get('action_log', [])) > MAX_ACTION_LOG_ENTRIES:
            memory['action_log'] = memory['action_log'][-MAX_ACTION_LOG_ENTRIES:]
        return memory
