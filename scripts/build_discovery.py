#!/usr/bin/env python3
"""Render the read-only discovery report separately from verified case evidence."""
import argparse
from collections import Counter
from html import escape as e
import json
from pathlib import Path
from build import document

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = {'ML systems': '机器学习系统', 'Database': '数据库', 'Distributed systems': '分布式系统'}
STATUSES = {
    'needs_review': ('Awaiting applicability review', '待审阅适用性'),
    'already_catalogued': ('Existing research entry', '已有研究记录'),
    'skipped_review': ('Skipped · safety review', '已跳过 · 待安全审阅'),
    'excluded_after_review': ('Excluded after review', '审阅后排除'),
    'no_async_signal': ('No concrete async keyword', '未检出具体异步关键词'),
    'external_environment_required': ('External environment required', '依赖外部环境，已跳过'),
}


def render(report, language):
    zh = language == 'zh-CN'
    def tr(en, cn):
        return cn if zh else en
    def status(key):
        return STATUSES.get(key, (key, key))[zh]
    def domain(key):
        return DOMAINS.get(key, key) if zh else key
    counts = report['counts']
    coverage = report['coverage']
    complete = sum(row['complete'] for row in coverage)
    gaps = sum(not row.get('has_issues', True) for row in coverage)
    official_complete = sum(row.get('official_search_complete', False) for row in coverage)
    summary = tr(
        f"{len(report['issues'])} unique GitHub search hits · {counts.get('needs_review', 0)} awaiting review · {complete}/{len(coverage)} repositories completed both GitHub windows · {official_complete} official trackers searched · {gaps} repositories have GitHub Issues disabled.",
        f"{len(report['issues'])} 条去重 GitHub 命中 · {counts.get('needs_review', 0)} 条待审阅 · {complete}/{len(coverage)} 个仓库完成两个 GitHub 窗口 · 已搜索 {official_complete} 个官方跟踪器 · {gaps} 个仓库未启用 GitHub Issues。")
    coverage_rows = []
    for row in coverage:
        if row.get('error'):
            outcome = tr('Metadata fetch failed; continue with the next repository.', '元数据获取失败，已继续下一仓库。')
        elif not row['has_issues']:
            outcome = tr('GitHub Issues disabled.', 'GitHub Issues 未启用。')
        elif not row['complete']:
            outcome = tr('Partial or failed search; this is a coverage gap.', '搜索不完整或失败，保留覆盖缺口。')
        else:
            outcome = tr('Both GitHub search windows completed.', '已完成两个 GitHub 搜索窗口。')
        if row.get('official_tracker'):
            if row.get('official_search_complete'):
                outcome += tr(f' Both official tracker windows completed: {row["official_candidates"]} hits.', f' 官方跟踪器两个窗口已完成：{row["official_candidates"]} 条命中。')
            else:
                outcome += tr(' Official tracker coverage incomplete.', ' 官方跟踪器覆盖尚未完成。')
        tracker = ''
        if row.get('official_tracker'):
            tracker = f'<br><a href="{e(row["official_tracker"])}">{tr("Official tracker", "官方跟踪器")}</a>'
        coverage_rows.append(f'<tr><th scope="row"><a href="https://github.com/{e(row["repository"])}">{e(row["repository"])}</a>{tracker}</th>'
                             f'<td>{domain(row["domain"])}</td><td>{row["stars"] if row["stars"] is not None else "—"}</td>'
                             f'<td>{row["unique_candidates"]}</td><td>{outcome}</td></tr>')
    candidate_rows = []
    for row in report['issues']:
        reason = status(row['status'])
        ordinal = row.get('coverage_rank', 10**9)
        candidate_rows.append(
            f'<tr data-candidate data-domain="{e(row["domain"])}" data-status="{e(row["status"])}" '
            f'data-state="{e(row["state"])}" data-heat="{row["heat"]}" data-rank="{ordinal}">'
            f'<th scope="row"><a href="{e(row["url"])}"><span>{e(row["repository"])} #{row["number"]}</span>{e(row["title"])}</a></th>'
            f'<td>{domain(row["domain"])}</td><td>{row["heat"]:.2f}<br>{row["comments"]} {tr("comments", "条评论")} · '
            f'{row["positive_reactions"]} {tr("reactions", "次关注反应")}</td>'
            f'<td>{tr(row["state"], "开放" if row["state"] == "open" else "已关闭")}</td><td>{reason}</td></tr>')
    deferred_rows = []
    for row in report['deferred_registry']:
        deferred_rows.append(f'<tr><th scope="row"><a href="{e(row["url"])}">{e(row["title_zh"] if zh else row["title"])}</a></th>'
                             f'<td>{tr("Reproduction skipped; safety impact unassessed.", "已跳过复现；安全影响尚未评估。")}</td></tr>')
    decisions = []
    for identifier, decision in report.get('review_decisions', {}).items():
        sources = ' · '.join(f'<a href="{e(url)}">{tr("Source", "来源")} {n}</a>' for n, url in enumerate(decision['sources'], 1))
        decisions.append(f'<li><strong>{e(identifier)}</strong>: {e(decision.get("reason_zh", decision["reason"]) if zh else decision["reason"])} {sources}</li>')
    official_sections = []
    for result in report.get('official_tracker_results', []):
        jira_rows = []
        for row in sorted(result['issues'], key=lambda row: (-row['votes'], -row['comments'], row['id'])):
            jira_rows.append(f'<tr><th scope="row"><a href="{e(row["url"])}"><span>{e(row["key"])}</span>{e(row["title"])}</a></th>'
                             f'<td>{row["votes"]}</td><td>{row["comments"]}</td><td>{e(row["tracker_state"])}</td><td>{status(row["status"])}</td></tr>')
        official_sections.append(f'<h3>{e(result["repository"])} · {len(result["issues"])} {tr("hits", "条命中")}</h3>'
                                 f'<div class="discovery-scroll"><table><thead><tr><th>{tr("Issue", "问题")}</th><th>{tr("Votes", "投票")}</th><th>{tr("Comments", "评论")}</th><th>{tr("Tracker state", "上游状态")}</th><th>{tr("Review", "审阅")}</th></tr></thead><tbody>{"".join(jira_rows)}</tbody></table></div>')
    failure_rows = []
    for error in report['errors']:
        failure_rows.append(f'<li>{e(error["repository"])} · {e(error["phase"])}: {e(error["error"])}</li>')
    controls = (
        ('domain', tr('Domain', '领域'), [('', tr('All domains', '全部领域'))] + [(key, domain(key)) for key in DOMAINS]),
        ('status', tr('Review status', '审阅状态'), [('', tr('All statuses', '全部状态'))] + [(key, status(key)) for key in STATUSES]),
        ('state', tr('GitHub state', 'GitHub 状态'), [('', tr('All states', '全部状态')), ('open', tr('Open', '开放')), ('closed', tr('Closed', '已关闭'))]),
        ('order', tr('Order', '排序'), [('coverage', tr('Coverage and heat', '覆盖与热度')), ('heat', tr('Heat only', '仅按热度'))]),
    )
    selects = []
    for key, label, options in controls:
        selects.append(f'<div><label for="discovery-{key}">{label}</label><select id="discovery-{key}">' +
                       ''.join(f'<option value="{e(value)}">{e(label)}</option>' for value, label in options) + '</select></div>')
    body = f'''<article class="wrap research discovery">
      <header><p class="eyebrow">coroPerf · {tr('Discovery', '自动搜索')}</p>
      <h1>{tr('Search progress', '搜索进度')}</h1>
      <p class="section-copy">{tr('Search hits need an applicability review. Verified diagnoses and measured results remain in the evidence atlas.', '搜索命中需要逐项审阅 coroPerf 适用性。已验证的诊断和实测结果保留在证据目录中。')}</p>
      <p class="section-copy">{e(summary)}</p>
      <p class="section-copy">{tr('Observed at', '取证时间')} <time>{e(report['finished_at'])}</time> · <a href="{'../' if zh else ''}data/discovery.json">{tr('Download report', '下载报告')}</a> · <a href="index.html#issues">{tr('Verified cases', '已验证案例')}</a></p></header>
      <section class="block"><h2>{tr('Framework coverage', '框架覆盖')}</h2>
      <p class="section-copy">{tr('Each enabled repository gets a most-discussed window and a recently-updated window, up to 20 issues each. This bounded survey does not cover every issue or external tracker.', '每个启用 Issues 的仓库分别搜索讨论最多和最近更新的窗口，各取最多 20 条。本轮为有界搜索，未覆盖所有 issue 或外部跟踪器。')}</p>
      <div class="discovery-scroll"><table><thead><tr><th>{tr('Repository', '仓库')}</th><th>{tr('Domain', '领域')}</th><th>Stars</th><th>{tr('Hits', '命中')}</th><th>{tr('Coverage evidence', '覆盖证据')}</th></tr></thead><tbody>{''.join(coverage_rows)}</tbody></table></div></section>
      <section class="block" id="official-trackers"><h2>{tr('Official tracker searches', '官方跟踪器搜索')}</h2><p class="section-copy">{tr('Apache Jira is searched by votes and recent updates, up to 20 entries per window. Votes are shown separately from GitHub reactions. These entries also need applicability review.', 'Apache Jira 分别按投票和最近更新搜索，每个窗口最多 20 条。投票与 GitHub 关注反应分开展示；这些条目也需要审阅适用性。')}</p>{''.join(official_sections)}</section>
      <section class="block" id="candidates"><h2>{tr('Review queue', '审阅队列')}</h2>
      <p class="section-copy">{tr('Heat uses comments, positive reactions and repository stars. Coverage order rotates domains and takes one issue per repository in each round. Search hits are never counted as CoroPerf successes.', '热度综合评论数、关注反应和仓库 stars。覆盖排序轮转三个领域，每轮每个仓库最多选一条。搜索命中不计为 coroPerf 成功案例。')}</p>
      <details><summary>{tr('Ranking method', '排序方法')}</summary><p><code>{e(report['heat_formula'])}</code></p></details>
      <div class="discovery-controls"><div><label for="discovery-search">{tr('Search', '搜索')}</label><input id="discovery-search" type="search" placeholder="{tr('Repository, title or issue number', '仓库、标题或 issue 编号')}"></div>{''.join(selects)}</div>
      <p id="discovery-count" role="status" aria-live="polite">{len(report['issues'])} {tr('search hits', '条搜索命中')}</p>
      <div class="discovery-scroll"><table><thead><tr><th>{tr('Issue', '问题')}</th><th>{tr('Domain', '领域')}</th><th>{tr('Heat', '热度')}</th><th>{tr('GitHub state', 'GitHub 状态')}</th><th>{tr('Review status', '审阅状态')}</th></tr></thead><tbody id="discovery-rows">{''.join(candidate_rows)}</tbody></table></div>
      <div class="discovery-pager" hidden><button id="discovery-previous" type="button">{tr('Previous', '上一页')}</button><span id="discovery-page"></span><button id="discovery-next" type="button">{tr('Next', '下一页')}</button></div></section>
      <section class="block" id="skipped"><h2>{tr('Skipped for review', '已跳过，待安全审阅')}</h2><p class="section-copy">{tr('Previously deferred entries remain on hold even when absent from these search windows. Security impact is unassessed. New security-related wording is a review signal, not a vulnerability finding.', '历史暂缓条目即使未出现在本轮搜索窗口，也保持跳过。安全影响尚未评估。新命中的安全相关词仅触发审阅，不代表已确认漏洞。')}</p>
      <div class="discovery-scroll"><table><thead><tr><th>{tr('Entry', '条目')}</th><th>{tr('Action', '处理')}</th></tr></thead><tbody>{''.join(deferred_rows)}</tbody></table></div></section>
      <section class="block"><h2>{tr('Review decisions', '逐项审阅结论')}</h2><ul>{''.join(decisions)}</ul></section>
      <section class="block"><h2>{tr('Collection failures', '采集失败')}</h2>{'<ul>' + ''.join(failure_rows) + '</ul>' if failure_rows else '<p>' + tr('No request failures in this run.', '本轮没有请求失败。') + '</p>'}</section>
      </article>'''
    page = document('discovery.html', tr('Search progress', '搜索进度'), summary, body, language)
    prefix = '../' if zh else ''
    return page.replace('</head>', f'<link rel="stylesheet" href="{prefix}assets/discovery.css">\n<script defer src="{prefix}assets/discovery.js"></script>\n</head>')


def build(report, destination=ROOT):
    for language, prefix in [('en', ''), ('zh-CN', 'zh-cn/')]:
        path = destination / prefix / 'discovery.html'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(report, language), encoding='utf-8')
    path = destination / 'data/discovery.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('report', type=Path)
    args = p.parse_args()
    build(json.loads(args.report.read_text()))
