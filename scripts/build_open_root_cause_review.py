#!/usr/bin/env python3
"""Render the bilingual, source-reviewed queue without altering verified cases."""
from html import escape as e
import json
from pathlib import Path

from build import document

ROOT = Path(__file__).resolve().parents[1]


def render(data, language):
    zh = language == 'zh-CN'
    def tr(en, cn):
        return cn if zh else en
    rows = []
    for row in data['candidates']:
        target = row.get('investigation_path', row['url'])
        source = (f'<small><a href="{e(row["url"])}">{tr("Upstream issue", "上游 issue")}</a></small>'
                  if row.get('investigation_path') else '')
        status = tr('Status check pending', '待核验状态') if row['stage'] == 'status_check' else tr('Investigation pending', '待调查')
        rows.append(f'<tr id="{e(row["id"])}"><th scope="row"><a href="{e(target)}">{e(row["reference"])}</a>{source}</th>'
                    f'<td>{e(row["language"])}</td><td>{e(row["question"][language])}</td><td>{status}</td></tr>')
    title = 'Open Issues'
    description = tr(f'{len(rows)} issues for investigation with CoroPerf.', f'{len(rows)} 个待用 CoroPerf 调查的 issue。')
    prefix = '../' if zh else ''
    body = f'''<article class="wrap research open-review">
      <h1>{title}</h1>
      <p class="review-meta">{description} <a href="{prefix}data/open-root-cause-review.json">{tr('Review records', '审阅记录')}</a></p>
      <div class="review-scroll" id="issues"><table>
        <thead><tr><th>Issue</th><th>{tr('Language / execution', '语言／执行机制')}</th><th>{tr('Unresolved question', '未解决的问题')}</th><th>{tr('Status', '状态')}</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table></div>
    </article>'''
    return document('open-issues.html', title, description, body, language).replace(
        '</head>', f'<link rel="stylesheet" href="{prefix}assets/open-issues.css">\n</head>')


def main():
    data = json.loads((ROOT / 'data/open-root-cause-review.json').read_text(encoding='utf-8'))
    for language, prefix in [('en', ''), ('zh-CN', 'zh-cn/')]:
        (ROOT / prefix / 'open-issues.html').write_text(render(data, language), encoding='utf-8')
    print('Built open-issues.html and zh-cn/open-issues.html')


if __name__ == '__main__':
    main()
