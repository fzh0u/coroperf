#!/usr/bin/env python3
"""Refresh tracker metadata while preserving measured diagnostic evidence.

No downloaded issue text or linked code is executed. Closure is an upstream
state, never an assertion that a cause or repair has been verified locally.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen

from refresh_issue_status import fetch
from build_open_root_cause_review import main as build

ROOT = Path(__file__).resolve().parents[1]


def check(row):
    observed = datetime.now(timezone.utc).isoformat(timespec='seconds')
    parts = row['url'].split('github.com/', 1)[1].split('/')
    owner, repository, _, number = parts
    try:
        request = Request(f'https://api.github.com/repos/{owner}/{repository}/issues/{number}',
                          headers={'User-Agent': 'CoroPerf-Open-Issues',
                                   'Accept': 'application/vnd.github+json'})
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
        assert result['number'] == int(number) and 'pull_request' not in result
        assert result['state'] in ('open', 'closed')
        return dict(id=row['id'], status=result['state'], checked_at=observed,
                    updated_at=result['updated_at'], comments=result['comments'],
                    title=result['title'], method='GitHub issue API')
    except Exception as error:
        # The existing HTML-header parser checks the canonical issue identity.
        result = fetch(row)
        return dict(id=row['id'], status=result['status'], checked_at=observed,
                    method='Rendered issue state / API fallback', api_error=str(error))


def main():
    path = ROOT / 'data/open-root-cause-review.json'
    original = path.read_text()
    data = json.loads(original)
    archived = data.setdefault('closed_investigations', {})
    entries = {row['id']: row for row in data['candidates']}
    entries.update(archived)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(check, entries.values()))
    for result in results:
        row = entries[result['id']]
        if result['status'] not in ('open', 'closed'):
            row['status_check_error'] = result.get('api_error', 'Tracker state unconfirmed')
            continue
        row.pop('status_check_error', None)
        row['last_status_check'] = result['checked_at']
        row['upstream_state'] = result['status']
        row['status_check_method'] = result['method']
        if result.get('updated_at'):
            row['last_upstream_activity'] = result['updated_at']
            row['upstream_comment_count'] = result['comments']
        if result['status'] == 'closed':
            archived[row['id']] = row
            data['candidates'] = [item for item in data['candidates'] if item['id'] != row['id']]
            if not any(item['id'] == row['id'] for item in data['not_primary']):
                data['not_primary'].append(dict(id=row['id'], reference=row['reference'], url=row['url'],
                    last_status_check=result['checked_at'], exclusion_source='daily_tracker_refresh',
                    reason={'en': 'Upstream issue is closed; original investigation and local evidence are retained in closed_investigations. Repair effectiveness is not inferred from closure.',
                            'zh-CN': '上游 issue 已关闭；原调查与本地证据保留于 closed_investigations，不从关闭状态推断修复有效。'}))
        elif row['id'] in archived:
            # Restore only entries archived by this status-refresh workflow.
            archived.pop(row['id'])
            data['not_primary'] = [item for item in data['not_primary'] if item['id'] != row['id']]
            data['candidates'].append(row)
    snapshot = dict(checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    scope='Tracker metadata only; local root-cause and repair evidence preserved',
                    results=results)
    data['tracker_refresh'] = dict(checked_at=snapshot['checked_at'],
                                   success=sum(r['status'] in ('open', 'closed') for r in results),
                                   attempted=len(results))
    # Do not overwrite a concurrent manual diagnosis update.
    if path.read_text() != original:
        raise RuntimeError('Review data changed while querying upstream; retry from the new state')
    pending = path.with_suffix('.pending.json')
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    pending.replace(path)
    (ROOT / 'data/open-issues-refresh.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    build()
    print(f"Refreshed {data['tracker_refresh']['success']}/{len(results)} tracker states; "
          f"{len(data['candidates'])} open investigations, {len(archived)} archived closed entries")
    if not data['tracker_refresh']['success']:
        raise RuntimeError('No upstream state could be refreshed')


if __name__ == '__main__':
    main()
