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
from core.context import ContextCache
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
              full_scan_interval: float = 300,
              dry_run: bool = False, once: bool = False,
              health_port: int = 0, auto_report: bool = False):
    """Run the agent loop for a single account.

    When poll_interval < full_scan_interval, fast cycles poll only
    notifications (one API call). Full repo scans run every
    full_scan_interval seconds.
    """

    if not db_path:
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, f'{account}.db')

    store = EventStore(db_path)
    poller = GitHubPoller(account, repos=repos)
    dispatcher = Dispatcher(store, dry_run=dry_run)
    context_cache = ContextCache(store, account)

    logger.info(
        f'Starting github-agent for {account}, '
        f'poll_interval={poll_interval}s, '
        f'full_scan_interval={full_scan_interval}s, '
        f'dry_run={dry_run}'
    )

    stats = {
        'status': 'ok',
        'account': account,
        'polls': 0,
        'full_scans': 0,
        'events_stored': 0,
        'actions_taken': 0,
        'errors': 0,
        'start_time': time.time(),
        'last_full_scan': 0,
    }

    if health_port:
        _HealthHandler.stats = stats
        server = HTTPServer(('0.0.0.0', health_port), _HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info(f'Health endpoint on :{health_port}')

    def _normalize_raw(raw: dict) -> list[dict]:
        """Normalize raw API data and store events. Returns new events."""
        new_events = []

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

        return new_events

    def _analyze_and_dispatch(new_events: list[dict]):
        """Run brain analysis and dispatch actions."""
        context = context_cache.build_and_save()
        history = store.get_context_window(account=account, hours=24)
        decisions = analyze_events(new_events, history, {
            'account': account,
            'total_events': store.count(account=account),
            'context_summary': context_cache.build_prompt_context(),
        })

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

    def poll_fast():
        """Fast poll: notifications only (one API call)."""
        raw = {'notifications': poller.poll_notifications()}
        new_events = _normalize_raw(raw)
        stats['polls'] += 1

        if not new_events:
            logger.debug(f'No new notifications for {account}')
            return
        logger.info(f'{len(new_events)} new notifications for {account}')
        _analyze_and_dispatch(new_events)

    def poll_full():
        """Full poll: all repos + notifications + settings."""
        raw = poller.poll_all()
        new_events = _normalize_raw(raw)

        # Settings drift detection per repo
        for repo_str in poller.repos:
            parts = repo_str.split('/', 1)
            if len(parts) != 2:
                continue
            try:
                changes = poll_settings(parts[0], parts[1])
                for change in changes:
                    record = normalize_settings_change(
                        change, account, repo_str
                    )
                    if store.insert(**record):
                        new_events.append(record)
            except Exception as e:
                logger.error(f'Settings poll failed for {repo_str}: {e}')

        stats['polls'] += 1
        stats['full_scans'] += 1
        stats['last_full_scan'] = time.time()
        stats['events_stored'] += len(new_events)

        if not new_events:
            logger.debug(f'No new events for {account}')
            return
        logger.info(f'{len(new_events)} new events for {account} (full scan)')
        _analyze_and_dispatch(new_events)

        if auto_report:
            try:
                from core.report import generate_report
                path = generate_report(store, account, open_browser=False)
                logger.info(f'Auto-report generated: {path}')
            except Exception as e:
                logger.error(f'Auto-report failed: {e}')

    # Main loop
    if once:
        try:
            poll_full()
        except Exception as e:
            logger.error(f'Poll cycle failed: {e}')
        finally:
            store.close()
        return

    signal.signal(signal.SIGTERM, lambda s, f: _shutdown.set())
    signal.signal(signal.SIGINT, lambda s, f: _shutdown.set())

    while not _shutdown.is_set():
        try:
            elapsed = time.time() - stats['last_full_scan']
            if elapsed >= full_scan_interval:
                poll_full()
            else:
                poll_fast()
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
                        help='Poll interval in seconds (fast polls use notifications only)')
    parser.add_argument('--full-scan-interval', type=float, default=300,
                        help='Full repo scan interval in seconds (default: 300)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Log actions without executing')
    parser.add_argument('--once', action='store_true',
                        help='Run single poll cycle then exit')
    parser.add_argument('--health-port', type=int, default=0,
                        help='Health check port (0 to disable)')
    parser.add_argument('--report', action='store_true',
                        help='Generate HTML dashboard report and exit')
    parser.add_argument('--output', default=None,
                        help='Output path for report (used with --report)')
    parser.add_argument('--auto-report', action='store_true',
                        help='Generate HTML report after each full scan')
    parser.add_argument('--verbose', '-v', action='store_true')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )

    if args.report:
        from core.report import generate_report
        db_path = args.db
        if not db_path:
            data_dir = os.path.join(os.path.dirname(__file__), 'data')
            db_path = os.path.join(data_dir, f'{args.account}.db')
        store = EventStore(db_path)
        path = generate_report(store, args.account, output_path=args.output)
        store.close()
        print(f'Report generated: {path}')
        return

    run_agent(
        account=args.account,
        repos=args.repos,
        db_path=args.db,
        poll_interval=args.interval,
        full_scan_interval=args.full_scan_interval,
        dry_run=args.dry_run,
        once=args.once,
        health_port=args.health_port,
        auto_report=args.auto_report,
    )


if __name__ == '__main__':
    main()
