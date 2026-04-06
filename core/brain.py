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
                          account_info: Optional[dict] = None) -> str:
    """Build the full prompt with context for the LLM."""
    parts = []

    if account_info:
        # Use structured context summary if available (from ContextCache)
        context_summary = None
        if isinstance(account_info, dict):
            context_summary = account_info.pop('context_summary', None)
        parts.append(f"## Account Info\n{json.dumps(account_info, indent=2)}")

    if context_summary:
        parts.append(f"\n{context_summary}")
    elif history:
        parts.append("## Recent Activity (last 24h)")
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
                   account_info: Optional[dict] = None) -> list[dict]:
    """Send events to claude -p for analysis. Returns list of decisions."""
    if not new_events:
        return []

    prompt = _build_context_prompt(new_events, history, account_info)

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
        action = 'LOG'
        urgency = 'low'
        reason = 'LLM unavailable, rule-based fallback'

        if etype in ('visibility_change', 'branch_protection_change',
                     'collaborator_added', 'app_installed'):
            action = 'ALERT'
            urgency = 'high'
            reason = f'Security-sensitive event: {etype}'
        elif etype in ('issue_opened', 'pr_opened', 'discussion_created'):
            action = 'LOG'
            urgency = 'medium'
        elif etype == 'workflow_failure':
            action = 'ALERT'
            urgency = 'medium'
            reason = f'CI failure on {evt.get("channel", "?")}'

        decisions.append({
            'event_id': evt.get('event_id', ''),
            'action': action,
            'reason': reason,
            'urgency': urgency,
        })
    return decisions
