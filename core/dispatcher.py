"""Action dispatcher — executes decisions from the brain.

Routes actions to the appropriate handler:
- RESPOND: post comments via gh CLI
- DISPATCH: write task to CCC bridge
- ALERT: send email via email-manager
- LOG/IGNORE: just record in store
"""

import json
import logging
import os
import subprocess
import sys
from typing import Optional, Callable

from github.gh_cli import gh_command as _gh_command

logger = logging.getLogger(__name__)


class Dispatcher:
    """Executes brain decisions."""

    def __init__(self, store, dry_run: bool = False,
                 gh_func: Optional[Callable] = None,
                 email_func: Optional[Callable] = None):
        self.store = store
        self.dry_run = dry_run
        self._gh = gh_func or _gh_command
        self._email = email_func

    def execute(self, decision: dict, event: dict) -> dict:
        """Execute a single decision. Returns result dict."""
        action = decision.get('action', 'IGNORE')
        event_id = decision.get('event_id', event.get('event_id', ''))

        handler = {
            'IGNORE': self._handle_ignore,
            'LOG': self._handle_log,
            'RESPOND': self._handle_respond,
            'DISPATCH': self._handle_dispatch,
            'ALERT': self._handle_alert,
        }.get(action)

        if not handler:
            logger.warning(f'Unknown action: {action}')
            return {'status': 'unknown_action', 'action': action}

        return handler(decision, event, event_id)

    def _handle_ignore(self, decision, event, event_id):
        self.store.mark_processed(event_id, {'action': 'IGNORE'})
        return {'status': 'ignored'}

    def _handle_log(self, decision, event, event_id):
        self.store.mark_processed(event_id, {
            'action': 'LOG', 'reason': decision.get('reason', ''),
        })
        return {'status': 'logged'}

    def _handle_respond(self, decision, event, event_id):
        body = decision.get('response_body', '')
        if not body:
            logger.warning(f'RESPOND with no body for {event_id}')
            return {'status': 'error', 'detail': 'no response body'}

        channel = event.get('channel', '')
        metadata = event.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}

        number = metadata.get('number')
        if not channel or not number:
            logger.warning(f'Cannot respond: missing channel/number')
            return {'status': 'error', 'detail': 'missing channel or number'}

        if self.dry_run:
            logger.info(f'[DRY RUN] Would respond to {channel}#{number}')
            self.store.mark_actioned(event_id, {
                'action': 'RESPOND', 'dry_run': True,
            })
            return {'status': 'dry_run'}

        code, out, err = self._gh([
            'issue', 'comment', str(number),
            '--repo', channel, '--body', body,
        ])
        if code != 0:
            logger.error(f'Failed to respond to {channel}#{number}: {err}')
            return {'status': 'error', 'detail': err}

        self.store.mark_actioned(event_id, {
            'action': 'RESPOND', 'channel': channel, 'number': number,
        })
        return {'status': 'responded'}

    def _handle_dispatch(self, decision, event, event_id):
        task = decision.get('dispatch_task', '')

        if self.dry_run:
            logger.info(f'[DRY RUN] Would dispatch: {task[:100]}')
            self.store.mark_actioned(event_id, {
                'action': 'DISPATCH', 'dry_run': True,
            })
            return {'status': 'dry_run'}

        bridge_dir = os.path.expanduser(
            '~/Documents/ProjectsCL1/_tmemu/ccc-rone-bridge/inbox'
        )
        os.makedirs(bridge_dir, exist_ok=True)

        safe_id = event_id.replace(':', '-').replace('/', '-')
        task_file = os.path.join(bridge_dir, f'gh-{safe_id}.json')
        task_data = {
            'source': 'github-agent',
            'event_id': event_id,
            'event': {
                'type': event.get('event_type'),
                'channel': event.get('channel'),
                'actor': event.get('actor'),
                'title': event.get('title'),
            },
            'task': task,
            'urgency': decision.get('urgency', 'medium'),
        }

        try:
            with open(task_file, 'w') as f:
                json.dump(task_data, f, indent=2)
            self.store.mark_actioned(event_id, {
                'action': 'DISPATCH', 'task_file': task_file,
            })
            logger.info(f'Dispatched task to {task_file}')
            return {'status': 'dispatched', 'task_file': task_file}
        except Exception as e:
            logger.error(f'Failed to dispatch: {e}')
            return {'status': 'error', 'detail': str(e)}

    def _handle_alert(self, decision, event, event_id):
        subject = decision.get(
            'alert_subject',
            f'GitHub Alert: {event.get("event_type", "unknown")}'
        )
        body = decision.get('alert_body', decision.get('reason', ''))

        if self.dry_run:
            logger.info(f'[DRY RUN] Would email: {subject}')
            self.store.mark_actioned(event_id, {
                'action': 'ALERT', 'dry_run': True,
            })
            return {'status': 'dry_run'}

        try:
            if self._email:
                self._email(subject, body)
            else:
                _send_email_alert(subject, body)
            self.store.mark_actioned(event_id, {
                'action': 'ALERT', 'subject': subject,
            })
            return {'status': 'alerted'}
        except Exception as e:
            logger.error(f'Failed to send alert: {e}')
            return {'status': 'error', 'detail': str(e)}


def _send_email_alert(subject: str, body: str):
    """Send email via email-manager CLI."""
    email_mgr = os.path.expanduser(
        '~/Documents/ProjectsCL1/_grobomo/email-manager'
    )
    subprocess.run(
        [sys.executable, '-m', 'email_manager', 'send',
         '--to', 'self', '--subject', subject, '--body', body],
        cwd=email_mgr, timeout=30,
    )
