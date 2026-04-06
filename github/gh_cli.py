"""Shared gh CLI wrapper — single source for gh_auto invocation.

Used by poller.py and core/dispatcher.py.
"""

import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

_home = os.path.expanduser('~').replace('\\', '/')
GH_AUTO = f'{_home}/Documents/ProjectsCL1/_shared/scripts/gh_auto'
_GIT_BASH = r'C:\Program Files\Git\bin\bash.exe'
if not os.path.exists(_GIT_BASH):
    _GIT_BASH = 'bash'


def gh_command(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run gh CLI via gh_auto. Returns (returncode, stdout, stderr)."""
    args_str = ' '.join(
        "'" + a.replace("'", "'\\''") + "'" for a in args
    )
    cmd = [_GIT_BASH, '-c', f'{GH_AUTO} {args_str}']
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, 'GH_PROMPT_DISABLED': '1'},
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 1, '', str(e)


def parse_json(output: str) -> list:
    """Safely parse JSON output, returning empty list on failure."""
    if not output:
        return []
    try:
        data = json.loads(output)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return []
