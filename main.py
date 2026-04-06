"""GitHub Agent — monitors GitHub activity across accounts.

One process per account for security isolation.
Poll → normalize → store → brain → dispatch loop.
"""

import argparse
import json
import logging
import os
import signal
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from core.store import EventStore
from core.brain import analyze_events, _fallback_decisions
from core.dispatcher import Dispatcher
from github.poller import GitHubPoller
from github.normalizer import (
    normalize_issue, normalize_pr, normalize_event,
    normalize_workflow_run, normalize_discussion,
    normalize_notification, normalize_settings_change,
)
from github.settings import poll_settings

logger = logging.getLogger(__name__)
_shutdown = threading.Event()


class _HealthHandler(BaseHTTPRequestHandler):
    stats = {}

    def do_GET(self):
        if self.path in ('/healthz', '/stats'):
            data = json.dumps(self.stats, indent=2)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


def _load_config(path: str) -> dict:
    """Load accounts config from YAML."""
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except (FileNotFoundError, ImportError) as e:
        logger.warning(f'Config load failed: {e}')
        return {}


def run_agent(account: str, repos: list[str] = None,
              db_path: str = None, poll_interval: float = 300,
              dry_run: bool = False, once: bool = False,
              health_port: int = 0):
    """Run the agent loop for a single account."""

    if not db_path:
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, f'{account}.db')

    store = EventStore(db_path)
    poller = GitHubPoller(account, repos=repos)
    dispatcher = Dispatcher(store, dry_run=dry_run)

    logger.info(
        f'Starting github-agent for {account}, '
        f'poll_interval={poll_interval}s, dry_run={dry_run}'
    )

    stats = {
        'status': 'ok',
        'account': account,
        'polls': 0,
        'events_stored': 0,
        'actions_taken': 0,
        'errors': 0,
        'start_time': time.time(),
    }

    if health_port:
        _HealthHandler.stats = stats
        server = HTTPServer(('0.0.0.0', health_port), _HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info(f'Health endpoint on :{health_port}')

    def poll_cycle():
        """Single poll → normalize → store → analyze → dispatch cycle."""
        raw = poller.poll_all()
        new_events = []

        # Normalize and store each event type
        for repo_str, issues in raw.get('issues', {}).items():
            for issue in issues:
                record = normalize_issue(issue, account, repo_str)
                if store.insert(**record):
                    new_events.append(record)

        for repo_str, prs in raw.get('prs', {}).items():
            for pr in prs:
                record = normalize_pr(pr, account, repo_str)
                if store.insert(**record):
                    new_events.append(record)

        for repo_str, events in raw.get('events', {}).items():
            for event in events:
                record = normalize_event(event, account, repo_str)
                if store.insert(**record):
                    new_events.append(record)

        for repo_str, runs in raw.get('workflow_failures', {}).items():
            for run in runs:
                record = normalize_workflow_run(run, account, repo_str)
                if store.insert(**record):
                    new_events.append(record)

        for repo_str, discs in raw.get('discussions', {}).items():
            for disc in discs:
                record = normalize_discussion(disc, account, repo_str)
                if store.insert(**record):
                    new_events.append(record)

        for notif in raw.get('notifications', []):
            record = normalize_notification(notif, account)
            if store.insert(**record):
                new_events.append(record)

        stats['polls'] += 1
        stats['events_stored'] += len(new_events)

        if not new_events:
            logger.debug(f'No new events for {account}')
            return

        logger.info(f'{len(new_events)} new events for {account}')

        # Analyze with brain
        history = store.get_context_window(account=account, hours=24)
        decisions = analyze_events(new_events, history, {
            'account': account,
            'total_events': store.count(account=account),
        })

        # Execute decisions
        for decision in decisions:
            eid = decision.get('event_id', '')
            matching = [e for e in new_events if e.get('event_id') == eid]
            event = matching[0] if matching else {}
            try:
                result = dispatcher.execute(decision, event)
                if result.get('status') not in ('ignored', 'logged'):
                    stats['actions_taken'] += 1
                    logger.info(
                        f'Action: {decision.get("action")} on {eid} '
                        f'-> {result.get("status")}'
                    )
            except Exception as e:
                logger.error(f'Dispatch error for {eid}: {e}')
                stats['errors'] += 1

    # Main loop
    if once:
        try:
            poll_cycle()
        except Exception as e:
            logger.error(f'Poll cycle failed: {e}')
        finally:
            store.close()
        return

    signal.signal(signal.SIGTERM, lambda s, f: _shutdown.set())
    signal.signal(signal.SIGINT, lambda s, f: _shutdown.set())

    while not _shutdown.is_set():
        try:
            poll_cycle()
        except Exception as e:
            logger.error(f'Poll cycle error: {e}')
            stats['errors'] += 1
        _shutdown.wait(timeout=poll_interval)

    logger.info(f'Shutting down agent for {account}')
    store.close()


def main():
    parser = argparse.ArgumentParser(
        description='GitHub Agent — monitor GitHub activity'
    )
    parser.add_argument('--account', required=True,
                        help='GitHub account to monitor')
    parser.add_argument('--repos', nargs='*',
                        help='Specific repos (default: discover all)')
    parser.add_argument('--config', default='config/accounts.yaml',
                        help='Path to accounts config')
    parser.add_argument('--db', default=None,
                        help='Path to SQLite database')
    parser.add_argument('--interval', type=float, default=300,
                        help='Poll interval in seconds')
    parser.add_argument('--dry-run', action='store_true',
                        help='Log actions without executing')
    parser.add_argument('--once', action='store_true',
                        help='Run single poll cycle then exit')
    parser.add_argument('--health-port', type=int, default=0,
                        help='Health check port (0 to disable)')
    parser.add_argument('--verbose', '-v', action='store_true')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )

    run_agent(
        account=args.account,
        repos=args.repos,
        db_path=args.db,
        poll_interval=args.interval,
        dry_run=args.dry_run,
        once=args.once,
        health_port=args.health_port,
    )


if __name__ == '__main__':
    main()
