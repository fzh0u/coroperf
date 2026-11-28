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
    def text(value):
        return e(value[language])
    title = tr('Open issues for root-cause investigation', '待逐项分析的 Open Issue')
    primary = [r for r in data['candidates'] if r['stage'] == 'candidate']
    description = tr(f'{len(data["candidates"])} issues to investigate with CoroPerf, ordered by review priority.',
                     f'{len(data["candidates"])} 个待用 CoroPerf 调查的 issue，按审阅优先顺序列出。')
    stages = {'candidate': tr('Priority investigation', '优先调查'),
              'follow_up': tr('Investigation pending', '待调查'),
              'status_check': tr('Status check first', '先核验状态')}
    corpus = data['corpus']
    rows = []
    for n, row in enumerate(data['candidates'], 1):
        stage = stages[row['stage']]
        detail = (f'<small><a href="{e(row["investigation_path"])}">{tr("Investigation case", "独立案例页")}</a></small>'
                  if row.get('investigation_path') else '')
        rows.append(f'<tr><th scope="row"><a href="#{e(row["id"])}">{n}. {e(row["reference"])}</a>'
                      f'<small>{e(row["language"])}</small>{detail}</th><td>{text(row["question"])}</td><td>{stage}</td></tr>')
    fields = [('known', 'Existing evidence', '已有证据'), ('patch', 'Repair status in inspected material', '所读材料中的修复状态'),
              ('coroperf_addition', 'What CoroPerf could add', 'CoroPerf 可补充的证据'),
              ('required_evidence', 'Required observations', '需要采集的关系与事件'),
              ('validation', 'How to distinguish causes', '如何区分原因并验证'),
              ('limits', 'Unresolved prerequisites', '尚未解决的前提'),
              ('first_step', 'First step', '第一步')]
    cards = []
    for n, row in enumerate(data['candidates'], 1):
        items = ''.join(f'<dt>{tr(en, cn)}</dt><dd>{text(row[key])}</dd>' for key, en, cn in fields)
        steps = []
        if n > 1:
            prev = data['candidates'][n-2]
            steps.append(f'<a href="#{e(prev["id"])}">{tr("Previous issue", "上一个 issue")}</a>')
        if n < len(data['candidates']):
            nxt = data['candidates'][n]
            steps.append(f'<a href="#{e(nxt["id"])}">{tr("Next issue", "下一个 issue")}</a>')
        stage = stages[row['stage']]
        upstream = e(row.get('upstream_state', 'unconfirmed').title())
        detail = (f'<p><a href="{e(row["investigation_path"])}">{tr("Open the investigation case", "查看独立案例与验证计划")}</a></p>'
                  if row.get('investigation_path') else '')
        cards.append(f'<section class="block review-card" id="{e(row["id"])}">'
                     f'<h2>{n}. {e(row["reference"])}</h2><h3>{text(row["question"])}</h3>'
                     f'<p class="review-meta">{e(row["language"])} · {upstream} · {stage}</p>'
                     f'<p><a href="{e(row["url"])}">{tr("Read the upstream issue", "阅读上游 issue")}</a></p>'
                     f'{detail}<dl>{items}</dl><nav class="review-steps" aria-label="{tr("Issue review order", "逐项审阅顺序")}">{"".join(steps)}</nav></section>')
    excluded = ''.join(f'<tr><th scope="row"><a href="{e(r["url"])}">{e(r["reference"])}</a></th><td>{text(r["reason"])}</td></tr>'
                       for r in data['not_primary'])
    prefix = '../' if zh else ''
    body = f'''<article class="wrap research open-review">
      <section class="block">
        <p class="eyebrow">{tr('Investigation queue', '逐项审阅清单')}</p>
        <h1>{title}</h1><p>{description}</p>
        <p class="review-meta">{tr('Reviewed', '核验日期')} {e(data['reviewed_at'][:10])} · {tr('No new executions', '本轮未执行复现')}</p>
        <p>{text(data['criteria'])}</p>
        <p>{text(data['priority_note'])}</p>
        <p>{text(data['scope'])}</p>
        <p>{tr('Saved discovery snapshot', '已保存的搜索快照')}：{corpus['discovery_entries']} {tr('entries', '条')}，
           {corpus['open_in_saved_discovery']} Open；{tr('existing review decisions', '已有审阅结论')} {corpus['review_decisions']}。
           {tr('Investigation leads do not add verified cases.', '调查候选不增加已验证案例数。')}</p>
        <div class="actions"><a class="button" href="#{e(primary[0]['id'])}">{tr('Review the first issue', '从第一个开始过')}</a>
          <a href="{prefix}data/open-root-cause-review.json">{tr('Download review data', '下载审阅记录')}</a>
          <a href="discovery.html">{tr('Search database', '搜索数据库')}</a></div>
      </section>
      <section class="block" id="issues"><h2>{tr(f'Issue list ({len(rows)})', f'Issue 列表（{len(rows)}）')}</h2>
        <div class="review-scroll"><table><thead><tr><th>Issue</th><th>{tr('Unresolved question', '未解决的问题')}</th><th>{tr('Status', '状态')}</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
        <p class="section-copy">{text(data['workflow'])}</p>
      </section>
      {''.join(cards)}
      <section class="block"><h2>{tr('Existing fixes and other reasons for exclusion', '已有修复及其他不列为首要候选的原因')}</h2>
        <p class="section-copy">{tr('Open does not mean no patch, no explanation, or a currently reproducible defect.', 'Open 不等于没有补丁、没有解释，也不等于当前版本仍能复现。')}</p>
        <div class="review-scroll"><table><thead><tr><th>Issue</th><th>{tr('Reason', '原因')}</th></tr></thead><tbody>{excluded}</tbody></table></div>
      </section>
      <section class="block"><h2>{tr('Evidence boundary', '证据边界')}</h2>
        <p>{tr('All proposed observations and controls remain to be performed. Creation ancestry alone does not establish socket, queue, message or descriptor ownership. A root-cause claim needs the failing event sequence, competing-explanation controls, and a cause-specific repair test. Upstream partial results are attributed to their reports.', '上述采集与对照均为待做工作。创建祖先本身不能证明 socket、队列、消息或 fd 的所有权。根因结论需要失败事件序列、竞争解释对照，以及针对原因的修复测试；上游阶段性结果均归属于原报告。')}</p>
      </section>
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
