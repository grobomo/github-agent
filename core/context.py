"""Rolling context cache for LLM prompts.

Builds structured context from EventStore for claude -p:
- Active issues/PRs (open, with recent activity)
- Event summary by type (last 24h)
- Settings state (last known per repo)
- Recent actions taken (what the agent already did)

Keeps context under a token budget by summarizing older events.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from core.store import EventStore

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = str(Path(__file__).parent.parent / 'data' / 'context')


class ContextCache:
    """Builds and caches rolling context for LLM analysis."""

    def __init__(self, store: EventStore, account: str,
                 cache_dir: Optional[str] = None,
                 context_hours: int = 24,
                 max_events: int = 200):
        self.store = store
        self.account = account
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.context_hours = context_hours
        self.max_events = max_events
        os.makedirs(self.cache_dir, exist_ok=True)

    @property
    def cache_file(self) -> str:
        return os.path.join(self.cache_dir, f'{self.account}.json')

    def build(self) -> dict:
        """Build structured context from EventStore.

        Returns dict with keys: active_items, event_summary,
        settings_state, recent_actions, raw_recent.
        """
        events = self.store.get_context_window(
            account=self.account,
            hours=self.context_hours,
            limit=self.max_events,
        )

        context = {
            'account': self.account,
            'window_hours': self.context_hours,
            'total_events': len(events),
            'active_items': self._extract_active_items(events),
            'event_summary': self._summarize_by_type(events),
            'settings_state': self._extract_settings(events),
            'recent_actions': self._extract_actions(events),
        }

        return context

    def build_and_save(self) -> dict:
        """Build context and write to cache file."""
        context = self.build()
        self.save(context)
        return context

    def save(self, context: dict):
        """Write context to JSON cache file."""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(context, f, indent=2, default=str)
        logger.debug(f'Context cache saved: {self.cache_file}')

    def load(self) -> Optional[dict]:
        """Load context from cache file. Returns None if missing."""
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def build_prompt_context(self) -> str:
        """Build a formatted string for inclusion in LLM prompts.

        This replaces the raw event list with structured context.
        """
        ctx = self.build()
        parts = []

        # Active issues and PRs
        if ctx['active_items']:
            parts.append('## Active Issues & PRs')
            for item in ctx['active_items']:
                status = item.get('state', 'open')
                parts.append(
                    f"- [{status}] {item['channel']}: {item['title']} "
                    f"(by {item['actor']}, {item['event_count']} events)"
                )

        # Event summary
        if ctx['event_summary']:
            parts.append(f"\n## Activity Summary (last {self.context_hours}h)")
            for etype, info in sorted(ctx['event_summary'].items(),
                                       key=lambda x: -x[1]['count']):
                parts.append(
                    f"- {etype}: {info['count']} events "
                    f"(repos: {', '.join(info['channels'][:5])})"
                )

        # Settings state
        if ctx['settings_state']:
            parts.append('\n## Settings Changes')
            for change in ctx['settings_state'][-10:]:
                parts.append(
                    f"- {change['channel']}: {change['title']} "
                    f"({change.get('timestamp', '?')})"
                )

        # Recent agent actions
        if ctx['recent_actions']:
            parts.append('\n## Recent Agent Actions')
            for action in ctx['recent_actions'][-10:]:
                parts.append(
                    f"- {action['action']} on {action['channel']}: "
                    f"{action.get('reason', 'N/A')}"
                )

        return '\n'.join(parts) if parts else '(No recent activity)'

    def _extract_active_items(self, events: list[dict]) -> list[dict]:
        """Find open issues/PRs with recent activity."""
        items = {}  # channel+title -> aggregated info
        for evt in events:
            etype = evt.get('event_type', '')
            if etype not in ('issue_opened', 'issue_comment', 'issue_closed',
                             'pr_opened', 'pr_comment', 'pr_merged',
                             'pr_closed', 'pr_review'):
                continue

            key = f"{evt.get('channel', '')}:{evt.get('title', '')}"
            if key not in items:
                items[key] = {
                    'channel': evt.get('channel', ''),
                    'title': evt.get('title', ''),
                    'actor': evt.get('actor', ''),
                    'state': 'open',
                    'event_count': 0,
                    'last_activity': evt.get('timestamp', ''),
                }
            items[key]['event_count'] += 1
            items[key]['last_activity'] = evt.get('timestamp', '')

            if etype in ('issue_closed', 'pr_closed', 'pr_merged'):
                items[key]['state'] = 'closed'

        return sorted(items.values(),
                      key=lambda x: x.get('last_activity', ''),
                      reverse=True)

    def _summarize_by_type(self, events: list[dict]) -> dict:
        """Group events by type with counts and affected channels."""
        summary = {}
        for evt in events:
            etype = evt.get('event_type', 'unknown')
            if etype not in summary:
                summary[etype] = {'count': 0, 'channels': set()}
            summary[etype]['count'] += 1
            summary[etype]['channels'].add(evt.get('channel', ''))

        # Convert sets to sorted lists for JSON serialization
        for info in summary.values():
            info['channels'] = sorted(info['channels'])
        return summary

    def _extract_settings(self, events: list[dict]) -> list[dict]:
        """Extract settings change events."""
        return [
            {
                'channel': evt.get('channel', ''),
                'title': evt.get('title', ''),
                'timestamp': evt.get('timestamp', ''),
                'metadata': evt.get('metadata'),
            }
            for evt in events
            if evt.get('event_type', '').startswith(('settings_', 'visibility_',
                                                      'branch_protection_'))
        ]

    def _extract_actions(self, events: list[dict]) -> list[dict]:
        """Extract events where the agent already took action."""
        actions = []
        for evt in events:
            action_taken = evt.get('action_taken')
            if not action_taken:
                continue
            if isinstance(action_taken, str):
                try:
                    action_taken = json.loads(action_taken)
                except (json.JSONDecodeError, TypeError):
                    action_taken = {'action': action_taken}
            actions.append({
                'channel': evt.get('channel', ''),
                'event_type': evt.get('event_type', ''),
                'action': action_taken.get('action', 'unknown'),
                'reason': action_taken.get('reason', ''),
                'timestamp': evt.get('timestamp', ''),
            })
        return actions
