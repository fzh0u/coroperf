#!/usr/bin/env python3
"""Render the bilingual, source-reviewed queue without altering verified cases."""
from html import escape as e
import json
from pathlib import Path

from build import document

ROOT = Path(__file__).resolve().parents[1]


def validate(data):
    """Curation is explicit; an open/skipped review alone never qualifies."""
    ids = [row['id'] for row in data['candidates']]
    assert len(ids) == len(set(ids)), 'Duplicate investigation candidate'
    assert not set(ids) & {row['id'] for row in data['not_primary']}
    for row in data['candidates']:
        assert row['stage'] in {'candidate', 'follow_up', 'status_check', 'diagnosed'}
        for field in ('question', 'known', 'patch', 'coroperf_addition',
                      'required_evidence', 'diagnosis_plan', 'validation', 'limits', 'first_step'):
            assert all(row[field].get(lang) for lang in ('en', 'zh-CN')), (row['id'], field)


def render(data, language):
    zh = language == 'zh-CN'
    def tr(en, cn):
        return cn if zh else en
    rows = []
    for row in data['candidates']:
        target = row.get('investigation_path', row['url'])
        source = (f'<small><a href="{e(row["url"])}">{tr("Upstream issue", "上游 issue")}</a></small>'
                  if row.get('investigation_path') else '')
        status = (tr('Skipped at user request', '按用户要求跳过') if row.get('skip_reason') == 'user_request' else
                  tr('Cause verified locally', '本地根因已验证') if row['stage'] == 'diagnosed' else
                  tr('Status check pending', '先核验状态') if row['stage'] == 'status_check' else
                  tr('Diagnosis pending', '待定位验证'))
        fields = [('known', 'Existing evidence', '已有证据'),
                  ('patch', 'Root-cause / repair screen', '根因／修复筛查'),
                  ('required_evidence', 'Observations to collect', '需要采集的证据'),
                  ('validation', 'Validation against the original failure', '如何验证原始失败'),
                  ('limits', 'Environment and coverage gaps', '环境与覆盖缺口')]
        details = ''.join(f'<dt>{tr(en, cn)}</dt><dd>{e(row[key][language])}</dd>' for key, en, cn in fields)
        checked = row.get('last_source_check')
        if checked:
            details += (f'<dt>{tr("Source checked", "来源检查时间")}</dt>'
                        f'<dd><time datetime="{e(checked)}">{e(checked)}</time></dd>')
        status_check = row.get('last_status_check')
        if status_check:
            details += (f'<dt>{tr("Latest tracker-status check", "最近 tracker 状态检查")}</dt>'
                        f'<dd><time datetime="{e(status_check)}">{e(status_check)}</time> · '
                        f'{e(row.get("upstream_state", "unconfirmed"))}</dd>')
        plan = row.get('diagnosis_plan')
        if plan:
            details += f'<dt>{tr("Competing explanations", "需要区分的解释")}</dt><dd>{e(plan[language])}</dd>'
        evidence = row.get('diagnosis_result')
        if row.get('preparation_result'):
            details += f'<dt>{tr("Preparation and collector checks", "准备与采集检查")}</dt><dd>{e(row["preparation_result"][language])}</dd>'
        if evidence:
            details += f'<dt>{tr("Measured diagnosis result", "定位实测结果")}</dt><dd>{e(evidence[language])}</dd>'
        else:
            details += f'<dt>{tr("Measured diagnosis result", "定位实测结果")}</dt><dd>{tr("Not measured: diagnosis time, speedup and a validated cause remain unavailable.", "尚未测量：定位耗时、提速和已验证根因均无结果。")}</dd>'
        contribution = tr('Observed CoroPerf contribution', 'CoroPerf 已补充的定位证据') if row['stage'] == 'diagnosed' else tr('Proposed CoroPerf contribution', 'CoroPerf 拟补充的定位证据')
        rows.append(f'<tr id="{e(row["id"])}"><th scope="row"><a href="{e(target)}">{e(row["reference"])}</a>{source}</th>'
                    f'<td>{e(row["language"])}</td><td><p>{e(row["question"][language])}</p>'
                    f'<p><strong>{contribution}</strong><br>{e(row["coroperf_addition"][language])}</p>'
                    f'<details><summary>{tr("Evidence and validation plan", "展开证据与验证计划")}</summary><dl>{details}</dl></details></td>'
                    f'<td><span class="review-status">{status}</span><p>{e(row["first_step"][language])}</p></td></tr>')
    title = 'Open Issues'
    skipped = sum(row.get('skip_reason') == 'user_request' for row in data['candidates'])
    pending = sum(row['stage'] == 'status_check' and not row.get('skip_reason') for row in data['candidates'])
    diagnosed = sum(row['stage'] == 'diagnosed' for row in data['candidates'])
    description = tr(f'{diagnosed} locally verified causes; {len(rows) - pending - diagnosed - skipped} diagnosis candidates; {pending} awaiting status checks; {skipped} skipped at user request.', f'{diagnosed} 个本地已验证根因，{len(rows) - pending - diagnosed - skipped} 个定位候选，{pending} 个先核验状态，{skipped} 个按用户要求跳过。')
    prefix = '../' if zh else ''
    protocol = data['diagnosis_protocol']
    steps = ''.join(f'<li>{e(step[language])}</li>' for step in protocol['steps'])
    effects = ([protocol['effect_evidence']] if protocol.get('effect_evidence') else [])
    effects += protocol.get('additional_effect_evidence', [])
    effect_html = ''
    for effect in effects:
        developer = effect.get('developer_report_url')
        developer_link = (f' · <a href="{e(developer)}">{tr("Developer report", "开发者结果")}</a>'
                          if developer else '')
        effect_html += (
            f'<p><strong>{tr("Checked attribution example", "已核验的归因示例")}</strong> · '
            f'<a href="{e(effect["case_path"])}">{e(effect["reference"])}</a><br>'
            f'{e(effect["summary"][language])} '
            f'<a href="{prefix}{e(effect["evidence_path"])}">{tr("Audit data", "核验数据")}</a>{developer_link}</p>'
            f'<p class="review-meta">{e(effect["limits"][language])}</p>'
        )
    body = f'''<article class="wrap research open-review">
      <h1>{title}</h1>
      <p class="review-meta">{description} <a href="{prefix}data/open-root-cause-review.json">{tr('Review records', '审阅记录')}</a></p>
      <p>{e(data['criteria'][language])}</p>
      <p class="review-meta">{tr('Initial review snapshot', '初次审阅快照')}：{e(data['reviewed_at'])} · {tr('Per-entry source-check times are shown where recorded. Each entry retains its own evidence limits; tracker-state polling does not re-review the complete discussion or validate a repair.', '已记录的逐条来源检查时间见展开详情。各条目保留原审阅范围；tracker 状态轮询不等于重新审阅完整讨论或验证修复。')}</p>
      <div class="review-scroll" id="issues"><table>
        <thead><tr><th>Issue</th><th>{tr('Language / execution', '语言／执行机制')}</th><th>{tr('Question, CoroPerf contribution and evidence', '问题、coroperf 价值与证据')}</th><th>{tr('Status / next step', '状态／下一步')}</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table></div>
      <section class="diagnosis-protocol"><h2>{tr('How to demonstrate faster diagnosis', '怎样证明能更快定位')}</h2>
        <p>{e(protocol['claim'][language])}</p><ol>{steps}</ol>
        <p class="review-meta">{e(protocol['measurement_status'][language])}</p>
        {effect_html}
      </section>
    </article>'''
    return document('open-issues.html', title, description, body, language).replace(
        '</head>', f'<link rel="stylesheet" href="{prefix}assets/open-issues.css">\n</head>')


def main():
    data = json.loads((ROOT / 'data/open-root-cause-review.json').read_text(encoding='utf-8'))
    validate(data)
    for language, prefix in [('en', ''), ('zh-CN', 'zh-cn/')]:
        (ROOT / prefix / 'open-issues.html').write_text(render(data, language), encoding='utf-8')
    print('Built open-issues.html and zh-cn/open-issues.html')


if __name__ == '__main__':
    main()
