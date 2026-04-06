"""LLM-based event analyzer — the agent brain.

Receives batches of new events + historical context, produces decisions:
- IGNORE: no action needed
- LOG: record for context (informational)
- RESPOND: post a comment/reply
- DISPATCH: send task to CCC dispatcher
- ALERT: email the user (urgent)

Uses claude -p for analysis with running context from EventStore.
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a GitHub environment monitor. You analyze GitHub events across
multiple accounts and repos, maintaining full situational awareness.

For each new event, decide the appropriate action based on:
1. The event itself (what happened)
2. Historical context (what's been happening across all repos/accounts)
3. Patterns (is this part of an ongoing situation?)
4. Urgency (does this need immediate attention?)

Actions:
- IGNORE: Routine activity, no action needed (most common for your own pushes/commits)
- LOG: Interesting but not actionable — record for context
- RESPOND: Post a comment on the issue/PR/discussion
- DISPATCH: Send a task to the CCC dispatcher for deeper work
- ALERT: Email the user — something urgent or security-sensitive

Security-sensitive events that should ALWAYS trigger ALERT:
- Repository visibility changed (public <-> private)
- Branch protection removed or weakened
- New collaborator added with admin access
- Secrets or tokens appearing in commits
- Unexpected bot/app installations

Return a JSON array with one entry per new event:
[{
  "event_id": "...",
  "action": "IGNORE|LOG|RESPOND|DISPATCH|ALERT",
  "reason": "brief explanation",
  "response_body": "text to post (only for RESPOND)",
  "dispatch_task": "task description (only for DISPATCH)",
  "alert_subject": "email subject (only for ALERT)",
  "alert_body": "email body (only for ALERT)",
  "urgency": "low|medium|high|critical"
}]"""


def _build_context_prompt(new_events: list[dict],
                          history: list[dict],
                          account_info: Optional[dict] = None,
                          account_memory: Optional[dict] = None,
                          repo_memories: Optional[dict] = None) -> str:
    """Build the full prompt with context for the LLM.

    Args:
        new_events: Events to analyze
        history: Recent events (Tier 1 hot cache)
        account_info: Account metadata
        account_memory: Tier 3 account-level memory
        repo_memories: Tier 2 per-repo memories {repo_name: memory_dict}
    """
    parts = []
    context_summary = None

    # Tier 3: Account-level memory (cross-repo awareness)
    if account_memory and account_memory.get('summary'):
        parts.append("## Account Overview (long-term memory)")
        parts.append(account_memory['summary'])
        if account_memory.get('trajectory'):
            parts.append(f"Trajectory: {account_memory['trajectory']}")
        if account_memory.get('repo_relationships'):
            parts.append("Repo relationships:")
            for rel in account_memory['repo_relationships'][:10]:
                parts.append(f"  - {rel}")
        # Recent actions from long-term log
        action_log = account_memory.get('action_log', [])
        if action_log:
            parts.append(f"\nRecent agent actions ({len(action_log)} total):")
            for act in action_log[-10:]:
                parts.append(f"  - {act.get('action', '?')} on {act.get('target', '?')}: {act.get('reason', '')}")

    # Tier 2: Per-repo memories (only for repos touched by new events)
    if repo_memories:
        parts.append("\n## Repo Context (long-term memory)")
        for repo_name, mem in repo_memories.items():
            if not mem.get('purpose') and not mem.get('open_threads'):
                continue
            parts.append(f"\n### {repo_name}")
            if mem.get('purpose'):
                parts.append(f"Purpose: {mem['purpose']}")
            if mem.get('open_threads'):
                parts.append(f"Open threads: {', '.join(mem['open_threads'][:10])}")
            if mem.get('milestones'):
                parts.append(f"Recent milestones: {', '.join(mem['milestones'][-5:])}")
            if mem.get('key_collaborators'):
                parts.append(f"Collaborators: {', '.join(mem['key_collaborators'][:10])}")

    if account_info:
        # Use structured context summary if available (from ContextCache)
        if isinstance(account_info, dict):
            context_summary = account_info.pop('context_summary', None)
        parts.append(f"\n## Account Info\n{json.dumps(account_info, indent=2)}")

    # Tier 1: Hot cache (recent events)
    if context_summary:
        parts.append(f"\n{context_summary}")
    elif history:
        parts.append("\n## Recent Activity (last 24h)")
        for evt in history[-100:]:
            parts.append(
                f"- [{evt.get('timestamp', '?')}] "
                f"{evt.get('event_type', '?')} on {evt.get('channel', '?')} "
                f"by {evt.get('actor', '?')}: {evt.get('title', '')}"
            )

    parts.append("\n## New Events to Analyze")
    for evt in new_events:
        parts.append(f"\n### Event: {evt.get('event_id', '?')}")
        parts.append(f"- Type: {evt.get('event_type', '?')}")
        parts.append(f"- Account: {evt.get('account', '?')}")
        parts.append(f"- Channel: {evt.get('channel', '?')}")
        parts.append(f"- Actor: {evt.get('actor', '?')}")
        parts.append(f"- Time: {evt.get('timestamp', '?')}")
        parts.append(f"- Title: {evt.get('title', '')}")
        if evt.get('body'):
            parts.append(f"- Body: {evt['body'][:1000]}")
        if evt.get('metadata'):
            meta = evt['metadata']
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    pass
            if meta:
                parts.append(f"- Metadata: {json.dumps(meta, indent=2)[:500]}")

    parts.append("\nAnalyze each new event and return JSON array of decisions.")
    return '\n'.join(parts)


def analyze_events(new_events: list[dict], history: list[dict],
                   account_info: Optional[dict] = None,
                   account_memory: Optional[dict] = None,
                   repo_memories: Optional[dict] = None) -> list[dict]:
    """Send events to claude -p for analysis. Returns list of decisions."""
    if not new_events:
        return []

    prompt = _build_context_prompt(new_events, history, account_info,
                                   account_memory, repo_memories)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                      encoding='utf-8') as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        cmd = ['claude', '-p', '--output-format', 'json']
        full_input = f"System: {SYSTEM_PROMPT}\n\n{prompt}"

        result = subprocess.run(
            cmd, input=full_input, capture_output=True, text=True, timeout=120,
        )

        if result.returncode != 0:
            logger.error(f'claude -p failed: {result.stderr[:500]}')
            return _fallback_decisions(new_events)

        output = result.stdout.strip()
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict) and 'result' in parsed:
                decisions = json.loads(parsed['result'])
            elif isinstance(parsed, list):
                decisions = parsed
            else:
                decisions = [parsed]
            return decisions
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f'Failed to parse LLM output: {e}')
            return _fallback_decisions(new_events)
    except subprocess.TimeoutExpired:
        logger.warning('claude -p timed out, using fallback rules')
        return _fallback_decisions(new_events)
    except FileNotFoundError:
        logger.warning('claude CLI not found, using fallback rules')
        return _fallback_decisions(new_events)
    finally:
        os.unlink(prompt_file)


def _fallback_decisions(events: list[dict]) -> list[dict]:
    """When LLM is unavailable, apply rule-based fallbacks."""
    decisions = []
    for evt in events:
        etype = evt.get('event_type', '')
        actor = evt.get('actor', '')
        account = evt.get('account', '')
        action = 'LOG'
        urgency = 'low'
        reason = 'LLM unavailable, rule-based fallback'
        response_body = None

        if etype in ('visibility_change', 'branch_protection_change',
                     'collaborator_added', 'app_installed'):
            action = 'ALERT'
            urgency = 'high'
            reason = f'Security-sensitive event: {etype}'
        elif etype == 'issue_opened' and actor != account:
            action = 'RESPOND'
            urgency = 'medium'
            reason = f'New issue from {actor} (auto-acknowledge)'
            response_body = (
                'Thanks for opening this issue! The github-agent detected it '
                'automatically. A maintainer will review it shortly.'
            )
        elif etype == 'pr_opened' and actor != account:
            action = 'RESPOND'
            urgency = 'medium'
            reason = f'New PR from {actor} (auto-acknowledge)'
            response_body = (
                'Thanks for this PR! The github-agent detected it automatically. '
                'A maintainer will review it shortly.'
            )
        elif etype in ('issue_opened', 'pr_opened', 'discussion_created'):
            action = 'LOG'
            urgency = 'low' if actor == account else 'medium'
            reason = f'Own activity, no response needed' if actor == account else reason
        elif etype == 'workflow_failure':
            action = 'ALERT'
            urgency = 'medium'
            reason = f'CI failure on {evt.get("channel", "?")}'

        decision = {
            'event_id': evt.get('event_id', ''),
            'action': action,
            'reason': reason,
            'urgency': urgency,
        }
        if response_body:
            decision['response_body'] = response_body
        decisions.append(decision)
    return decisions
