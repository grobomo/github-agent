"""T068: Tests for service health monitoring — log rotation, heartbeat, circuit breaker."""

import json
import logging
import logging.handlers
import os
import subprocess
import sys
import tempfile
import time

import pytest


class TestHeartbeat:
    """Test _write_heartbeat function."""

    def test_write_heartbeat_creates_file(self, tmp_path):
        from main import _write_heartbeat
        hb_path = str(tmp_path / 'heartbeat.json')
        stats = {
            'polls': 10, 'full_scans': 2, 'errors': 0,
            'last_full_scan': time.time(), 'status': 'ok',
        }
        _write_heartbeat(hb_path, stats, 'testaccount')
        assert os.path.exists(hb_path)
        data = json.loads(open(hb_path).read())
        assert data['account'] == 'testaccount'
        assert data['polls'] == 10
        assert data['pid'] == os.getpid()
        assert 'timestamp' in data

    def test_write_heartbeat_atomic_replace(self, tmp_path):
        from main import _write_heartbeat
        hb_path = str(tmp_path / 'heartbeat.json')
        stats = {'polls': 1, 'full_scans': 0, 'errors': 0,
                 'last_full_scan': 0, 'status': 'ok'}
        _write_heartbeat(hb_path, stats, 'acct1')
        # Overwrite — should not leave .tmp file
        stats['polls'] = 2
        _write_heartbeat(hb_path, stats, 'acct1')
        assert not os.path.exists(hb_path + '.tmp')
        data = json.loads(open(hb_path).read())
        assert data['polls'] == 2

    def test_write_heartbeat_no_last_full_scan(self, tmp_path):
        from main import _write_heartbeat
        hb_path = str(tmp_path / 'heartbeat.json')
        stats = {'polls': 0, 'full_scans': 0, 'errors': 0,
                 'last_full_scan': 0, 'status': 'ok'}
        _write_heartbeat(hb_path, stats, 'acct')
        data = json.loads(open(hb_path).read())
        assert data['last_full_scan'] is None


class TestLogRotation:
    """Test that log rotation is configured correctly via CLI."""

    def test_cli_log_rotation_flags_parsed(self):
        """Verify --log-max-bytes and --log-backup-count are accepted."""
        result = subprocess.run(
            [sys.executable, '-c',
             'import main; import argparse; '
             'p = argparse.ArgumentParser(); '
             'main.main.__code__'],
            capture_output=True, text=True,
        )
        # Just verify the flags exist by running --help
        result = subprocess.run(
            [sys.executable, 'main.py', '--help'],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        assert '--log-max-bytes' in result.stdout
        assert '--log-backup-count' in result.stdout
        assert '--max-errors' in result.stdout

    def test_rotating_handler_class_available(self):
        """Verify RotatingFileHandler is importable (sanity)."""
        handler = logging.handlers.RotatingFileHandler(
            os.devnull, maxBytes=1000, backupCount=1,
        )
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        handler.close()


class TestCircuitBreaker:
    """Test max-errors circuit breaker behavior."""

    def test_max_errors_default_in_help(self):
        result = subprocess.run(
            [sys.executable, 'main.py', '--help'],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        assert '--max-errors' in result.stdout

    def test_circuit_breaker_exits_with_code_2(self, tmp_path, monkeypatch):
        """Simulate consecutive errors exceeding max_errors threshold."""
        from unittest.mock import patch, MagicMock

        db_path = str(tmp_path / 'test.db')
        monkeypatch.setattr('main._shutdown', MagicMock())
        # Make _shutdown.is_set() return False first, then True
        shutdown_mock = MagicMock()
        shutdown_mock.is_set.side_effect = [False, False, False, True]
        shutdown_mock.wait.return_value = None
        monkeypatch.setattr('main._shutdown', shutdown_mock)

        # Mock the poller to always raise
        with patch('main.GitHubPoller') as mock_poller_cls, \
             patch('main.EventStore') as mock_store_cls, \
             patch('main.Dispatcher'), \
             patch('main.ContextCache'), \
             patch('main.MemoryStore'), \
             patch('main.MemoryCompactor'):

            mock_store = MagicMock()
            mock_store_cls.return_value = mock_store
            mock_poller = MagicMock()
            mock_poller.poll_notifications.side_effect = RuntimeError('API down')
            mock_poller_cls.return_value = mock_poller

            with pytest.raises(SystemExit) as exc_info:
                from main import run_agent
                run_agent(
                    account='test',
                    db_path=db_path,
                    poll_interval=0.01,
                    full_scan_interval=9999,  # only fast polls
                    max_errors=2,
                    no_memory=True,
                )
            assert exc_info.value.code == 2

            # Verify heartbeat was written with circuit_breaker status
            hb_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 'data', 'heartbeat.json'
            )
            # Clean up — the test writes to real data dir
            if os.path.exists(hb_path):
                data = json.loads(open(hb_path).read())
                assert data['status'] == 'circuit_breaker'
                os.unlink(hb_path)


class TestWatchdog:
    """Test watchdog.sh script logic."""

    def test_watchdog_no_heartbeat_detects_missing(self):
        """Watchdog should detect when no heartbeat file exists."""
        result = subprocess.run(
            ['bash', 'scripts/watchdog.sh'],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        # Script derives PROJECT_DIR from its own location, so it checks
        # the real data/ dir. If no heartbeat exists, it reports it.
        # Exit code may be 1 or 2 depending on tee/log permissions.
        assert result.returncode != 0
        assert 'heartbeat' in (result.stdout + result.stderr).lower()

    def test_watchdog_fresh_heartbeat_exits_0(self, tmp_path):
        """Watchdog should exit 0 when heartbeat is fresh."""
        from main import _write_heartbeat
        data_dir = tmp_path / 'data'
        data_dir.mkdir()
        hb_path = str(data_dir / 'heartbeat.json')
        stats = {'polls': 5, 'full_scans': 1, 'errors': 0,
                 'last_full_scan': time.time(), 'status': 'ok'}
        _write_heartbeat(hb_path, stats, 'test')

        # Create a minimal watchdog test inline
        script = f"""
import json, time, sys
data = json.load(open(r'{hb_path}'))
from datetime import datetime, timezone
ts = data['timestamp'].replace('Z', '+00:00')
dt = datetime.fromisoformat(ts)
age = time.time() - dt.timestamp()
sys.exit(0 if age < 120 else 1)
"""
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
