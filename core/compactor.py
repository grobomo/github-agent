"""Memory compactor — distills recent events into long-term repo/account memory.

Runs after each full scan. For each repo with new events:
1. Load existing memory
2. Get events since last compaction
3. Use LLM to incrementally merge new events into memory
4. Save updated memory

Falls back to rule-based summarization when LLM is unavailable.
"""

import json
import logging
import subprocess
import tempfile
import os
from datetime import datetime, timezone
from typing import Optional

from core.memory import MemoryStore
from core.store import EventStore

logger = logging.getLogger(__name__)

COMPACTION_PROMPT = """You are a memory compactor for a GitHub monitoring agent.
You maintain a per-repo memory file that captures the essential state of each repository.

Given the CURRENT MEMORY and NEW EVENTS, produce an UPDATED MEMORY JSON object.

Rules:
- Preserve important context from current memory
- Integrate new events: update open_threads, add milestones for significant events
- Close threads that are resolved (merged PRs, closed issues)
- Keep purpose/description updated if new info reveals it
- Add new collaborators if they appear
- Summarize PR themes from recent activity
- Be concise — this memory is prepended to every future analysis prompt
- Return ONLY valid JSON, no markdown fences

Memory schema:
{
  "purpose": "what this repo is for",
  "description": "brief technical description",
  "key_collaborators": ["username1", "username2"],
  "milestones": ["2024-01: Initial release", "2024-03: Added CI"],
  "open_threads": ["Issue #5: bug in parser", "PR #12: add feature X"],
  "pr_themes": ["CI improvements", "documentation"],
  "recent_actions": [{"action": "RESPOND", "target": "issue #5", "reason": "..."}]
}"""

ACCOUNT_PROMPT = """You are a memory compactor for a GitHub monitoring agent.
You maintain an account-level summary that provides cross-repo awareness.

Given ALL REPO MEMORIES for this account, produce an UPDATED ACCOUNT MEMORY JSON.

Rules:
- Summarize the overall account trajectory
- Identify relationships between repos (shared themes, dependencies)
- Note the most active areas of work
- Keep it concise — this is prepended to every analysis prompt
- Return ONLY valid JSON, no markdown fences

Schema:
{
  "summary": "Account-wide summary of all repos and activity",
  "repo_relationships": ["repo-a and repo-b share CI config", ...],
  "trajectory": "Current focus areas and direction"
}"""


class MemoryCompactor:
    """Compacts recent events into long-term memory."""

    def __init__(self, store: EventStore, memory: MemoryStore,
                 account: str, model: Optional[str] = None):
        self.store = store
        self.memory = memory
        self.account = account
        self.model = model  # Optional cheaper model for compaction

    def compact_repo(self, repo_full_name: str) -> bool:
        """Compact events for a single repo. Returns True if updated."""
        mem = self.memory.load_repo_memory(self.account, repo_full_name)
        last_rowid = mem.get('last_compacted_rowid', 0)

        # Get channel name as used in EventStore
        channel = f'gh:{repo_full_name}'
        events = self._get_events_since(channel, last_rowid)

        if not events:
            logger.debug(f'No new events for {repo_full_name}, skipping compaction')
            return False

        logger.info(f'Compacting {len(events)} events for {repo_full_name}')

        updated = self._llm_compact_repo(mem, events, repo_full_name)
        if updated is None:
            updated = self._fallback_compact_repo(mem, events)

        updated['last_compacted_at'] = datetime.now(timezone.utc).isoformat()
        updated['last_compacted_rowid'] = max(e.get('id', 0) for e in events)
        updated['event_count_at_compaction'] = mem.get('event_count_at_compaction', 0) + len(events)
        self.memory.save_repo_memory(self.account, repo_full_name, updated)
        return True

    def compact_repos(self, repo_names: list[str]) -> int:
        """Compact multiple repos. Returns count of updated repos."""
        updated = 0
        for repo in repo_names:
            try:
                if self.compact_repo(repo):
                    updated += 1
            except Exception as e:
                logger.error(f'Failed to compact {repo}: {e}')
        return updated

    def compact_account(self) -> bool:
        """Regenerate account-level summary from all repo memories."""
        repo_names = self.memory.list_repo_memories(self.account)
        if not repo_names:
            return False

        repo_memories = {}
        for name in repo_names:
            mem = self.memory.load_repo_memory(self.account, name)
            # Only include repos with actual content
            if mem.get('purpose') or mem.get('open_threads') or mem.get('milestones'):
                repo_memories[name] = {
                    'purpose': mem.get('purpose', ''),
                    'open_threads': mem.get('open_threads', [])[:5],
                    'milestones': mem.get('milestones', [])[-3:],
                    'pr_themes': mem.get('pr_themes', []),
                }

        if not repo_memories:
            return False

        updated = self._llm_compact_account(repo_memories)
        if updated is None:
            updated = self._fallback_compact_account(repo_memories)

        account_mem = self.memory.load_account_memory(self.account)
        account_mem['summary'] = updated.get('summary', account_mem.get('summary', ''))
        account_mem['repo_relationships'] = updated.get('repo_relationships', [])
        account_mem['trajectory'] = updated.get('trajectory', '')
        account_mem['last_compacted_at'] = datetime.now(timezone.utc).isoformat()
        self.memory.save_account_memory(self.account, account_mem)
        return True

    def _get_events_since(self, channel: str, last_rowid: int = 0) -> list[dict]:
        """Get events for a channel with rowid > last_rowid.

        Uses rowid (monotonically increasing) instead of timestamps to avoid
        issues with same-second inserts or historical event timestamps.
        """
        rows = self.store.conn.execute(
            "SELECT * FROM events WHERE channel = ? AND id > ? "
            "ORDER BY id ASC LIMIT 500",
            (channel, last_rowid),
        ).fetchall()
        return [dict(r) for r in rows]

    def _llm_compact_repo(self, current_memory: dict, events: list[dict],
                           repo_name: str) -> Optional[dict]:
        """Use LLM to merge events into memory. Returns None on failure."""
        event_summaries = []
        for evt in events:
            event_summaries.append(
                f"[{evt.get('timestamp', '?')}] {evt.get('event_type', '?')} "
                f"by {evt.get('actor', '?')}: {evt.get('title', '')}"
            )

        prompt = (
            f"## Current Memory for {repo_name}\n"
            f"```json\n{json.dumps(current_memory, indent=2, default=str)}\n```\n\n"
            f"## New Events ({len(events)} total)\n"
            + '\n'.join(event_summaries)
            + "\n\nProduce the updated memory JSON."
        )

        return self._call_llm(COMPACTION_PROMPT, prompt)

    def _llm_compact_account(self, repo_memories: dict) -> Optional[dict]:
        """Use LLM to generate account summary. Returns None on failure."""
        prompt = (
            f"## Repo Memories for account '{self.account}'\n"
            f"```json\n{json.dumps(repo_memories, indent=2, default=str)}\n```\n\n"
            f"Produce the updated account memory JSON."
        )
        return self._call_llm(ACCOUNT_PROMPT, prompt)

    def _call_llm(self, system: str, prompt: str) -> Optional[dict]:
        """Call claude -p and parse JSON response."""
        try:
            cmd = ['claude', '-p', '--output-format', 'json']
            if self.model:
                cmd.extend(['--model', self.model])
            full_input = f"System: {system}\n\n{prompt}"

            result = subprocess.run(
                cmd, input=full_input, capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                logger.warning(f'claude -p failed for compaction: {result.stderr[:300]}')
                return None

            output = result.stdout.strip()
            parsed = json.loads(output)
            # claude -p with --output-format json wraps in {"result": "..."}
            if isinstance(parsed, dict) and 'result' in parsed:
                inner = parsed['result']
                if isinstance(inner, str):
                    return json.loads(inner)
                return inner
            return parsed
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f'LLM compaction failed: {e}')
            return None

    def _fallback_compact_repo(self, current_memory: dict,
                                events: list[dict]) -> dict:
        """Rule-based compaction when LLM unavailable."""
        mem = dict(current_memory)

        actors = set(mem.get('key_collaborators', []))
        open_threads = list(mem.get('open_threads', []))
        milestones = list(mem.get('milestones', []))
        recent_actions = list(mem.get('recent_actions', []))

        for evt in events:
            etype = evt.get('event_type', '')
            actor = evt.get('actor', '')
            title = evt.get('title', '')
            ts = evt.get('timestamp', '')[:10]  # date only

            if actor:
                actors.add(actor)

            if etype == 'issue_opened':
                thread = f"Issue: {title}"
                if thread not in open_threads:
                    open_threads.append(thread)
            elif etype == 'issue_closed':
                # Try to remove from open threads
                thread = f"Issue: {title}"
                if thread in open_threads:
                    open_threads.remove(thread)
                milestones.append(f"{ts}: Closed issue — {title}")
            elif etype == 'pr_opened':
                thread = f"PR: {title}"
                if thread not in open_threads:
                    open_threads.append(thread)
            elif etype in ('pr_merged', 'pr_closed'):
                thread = f"PR: {title}"
                if thread in open_threads:
                    open_threads.remove(thread)
                if etype == 'pr_merged':
                    milestones.append(f"{ts}: Merged — {title}")
            elif etype == 'workflow_failure':
                milestones.append(f"{ts}: CI failure — {title}")

            action_taken = evt.get('action_taken')
            if action_taken:
                if isinstance(action_taken, str):
                    try:
                        action_taken = json.loads(action_taken)
                    except json.JSONDecodeError:
                        action_taken = {'action': action_taken}
                recent_actions.append(action_taken)

        mem['key_collaborators'] = sorted(actors)
        mem['open_threads'] = open_threads
        mem['milestones'] = milestones
        mem['recent_actions'] = recent_actions
        return mem

    def _fallback_compact_account(self, repo_memories: dict) -> dict:
        """Rule-based account summary when LLM unavailable."""
        repos_with_activity = []
        all_themes = set()

        for name, mem in repo_memories.items():
            purpose = mem.get('purpose', '')
            threads = len(mem.get('open_threads', []))
            if purpose or threads:
                repos_with_activity.append(f"{name}: {purpose or 'no description'} ({threads} open threads)")
            for theme in mem.get('pr_themes', []):
                all_themes.add(theme)

        return {
            'summary': f"{len(repo_memories)} repos tracked. "
                       f"{len(repos_with_activity)} with active context.",
            'repo_relationships': [],
            'trajectory': f"Active themes: {', '.join(sorted(all_themes)[:10])}" if all_themes else '',
        }
