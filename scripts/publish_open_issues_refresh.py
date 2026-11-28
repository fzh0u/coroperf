#!/usr/bin/env python3
"""Publish the daily tracker refresh from an isolated checkout.

The timer never commits the user's working tree or forces a remote update.
Failed worktrees and a receipt remain available for diagnosis.
"""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parents[1] / 'perf-out/open-issue-debug/daily'


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    lock = (STATE / 'publication.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    receipt = dict(started_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                   status='running', actions=[])
    env = os.environ.copy()
    env.update(HTTP_PROXY='http://127.0.0.1:7890', HTTPS_PROXY='http://127.0.0.1:7890',
               ALL_PROXY='http://127.0.0.1:7890', NO_PROXY='localhost,127.0.0.1')
    def run(args, cwd=ROOT, timeout=90):
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=timeout)
        receipt['actions'].append(dict(command=args, returncode=result.returncode,
                                       stdout=result.stdout[-4000:], stderr=result.stderr[-2000:]))
        result.check_returncode()
        return result.stdout.strip()
    try:
        run(['git', 'fetch', 'origin'])
        folder = Path(tempfile.mkdtemp(prefix='checkout-', dir=STATE))
        receipt['worktree'] = str(folder)
        run(['git', 'worktree', 'add', '--detach', str(folder), 'origin/main'])
        run(['/usr/bin/python3', '-B', 'scripts/refresh_open_issues.py'], cwd=folder, timeout=420)
        paths = ['data/open-root-cause-review.json', 'data/open-issues-refresh.json',
                 'open-issues.html', 'zh-cn/open-issues.html']
        run(['git', 'diff', '--check'], cwd=folder)
        run(['git', 'add', *paths], cwd=folder)
        changed = run(['git', 'diff', '--cached', '--name-only'], cwd=folder)
        if changed:
            run(['git', 'commit', '-m', 'Refresh Open Issues tracker states'], cwd=folder)
            # A racing publisher causes a normal non-fast-forward rejection;
            # preserve the checkout instead of overwriting its changes.
            run(['git', 'push', 'origin', 'HEAD:main'], cwd=folder)
        receipt['commit'] = run(['git', 'rev-parse', 'HEAD'], cwd=folder)
        receipt['status'] = 'pushed' if changed else 'unchanged'
        run(['git', 'worktree', 'remove', str(folder)])
        print(json.dumps({k:receipt[k] for k in ('status', 'commit')}))
    except Exception as error:
        receipt.update(status='failed', error=str(error))
        raise
    finally:
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        (STATE / 'latest.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
