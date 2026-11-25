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
    'verified_case': ('Verified diagnostic case', '已验证诊断案例'),
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
                windows = row.get('official_search_windows', 2)
                metric = 'messages' if row.get('official_entry_kind') == 'messages' else 'issues'
                outcome += tr(f' {windows} official search windows completed: {row["official_candidates"]} {metric}.', f' 官方跟踪器已完成 {windows} 个窗口：{row["official_candidates"]} 条' + ('邮件消息。' if metric == 'messages' else '命中。'))
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
        mail = result.get('entry_kind') == 'messages'
        mysql = result.get('entry_kind') == 'mysql_issues'
        label = tr('messages', '条邮件消息') if mail else tr('hits', '条命中')
        title = f'<h3>{e(result["repository"])} · {len(result["issues"])} {label}</h3>'
        searches = ' · '.join(f'<a href="{e(search["url"])}">{e(search.get("list", result.get("tracker", "Apache Jira")))} · {e(search["kind"])}</a>'
                              for search in result['searches'] if search.get('url'))
        if not result['issues']:
            official_sections.append(title + '<p class="section-copy">' + tr('No verified search entries collected; coverage remains incomplete. See collection failures.', '未采集到可核对的搜索条目；覆盖尚未完成，详见采集失败记录。') + '</p><p>' + searches + '</p>')
            continue
        rows = []
        ordered = (result['issues'] if mail else sorted(result['issues'], key=lambda row: row['updated_at'], reverse=True) if mysql else
                   sorted(result['issues'], key=lambda row: (-row['votes'], -row['comments'], row['id'])))
        for row in ordered:
            name = f'<th scope="row"><a href="{e(row["url"])}"><span>{e(row["key"])}</span>{e(row["title"])}</a></th>'
            if mail:
                rows.append(f'<tr>{name}<td>{e(row.get("message_date") or "—")}</td><td>{e(row["list"])}</td><td>{status(row["status"])}</td></tr>')
            elif mysql:
                rows.append(f'<tr>{name}<td>{e(row["category"])}<br>{e(row["severity"])} · {e(row["version"])}</td><td>{e(row["updated_at"])}</td><td>{e(row["tracker_state"])}</td><td>{status(row["status"])}</td></tr>')
            else:
                rows.append(f'<tr>{name}<td>{row["votes"]}</td><td>{row["comments"]}</td><td>{e(row["tracker_state"])}</td><td>{status(row["status"])}</td></tr>')
        heads = ([tr('Message', '邮件消息'), tr('Date', '日期'), tr('List', '列表'), tr('Review', '审阅')] if mail else
                 [tr('Report', '报告'), tr('Category / severity / version', '类别 / 严重度 / 版本'), tr('Updated', '更新日期'), tr('Upstream state', '上游状态'), tr('Review', '审阅')] if mysql else
                 [tr('Issue', '问题'), tr('Votes', '投票'), tr('Comments', '评论'), tr('Tracker state', '上游状态'), tr('Review', '审阅')])
        note = ''
        if mail:
            groups = result['subject_groups']
            note = '<p class="section-copy">' + tr(f'{groups} normalized subject groups. Relevance and date orders are not popularity scores; replies and subject groups are not unique bug counts. Message status is not inferred from mail.', f'按主题文字归并为 {groups} 组。相关性和日期排序并非热度；回复数和主题组数均不代表独立 bug 数。邮件不推断开放或关闭状态。') + '</p>'
        elif mysql:
            note = '<p class="section-copy">' + tr('Official relevance and updated-date windows. Severity is not a popularity metric. No vote or comment counts are invented. Upstream Verified is a tracker state; CoroPerf applicability is shown in the separate review column.', '官方相关性与更新日期窗口。严重度并非热度，不补造投票或评论数。上游 Verified 是报告状态；coroPerf 适用性见独立的审阅列。') + '</p>'
        official_sections.append(title + note + '<p>' + searches + '</p>' +
                                 f'<div class="discovery-scroll"><table><thead><tr>{"".join("<th>"+head+"</th>" for head in heads)}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
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
      <p class="section-copy">{tr('Snapshot assembled at', '快照汇总时间')} <time>{e(report['finished_at'])}</time> · <a href="{'../' if zh else ''}data/discovery.json">{tr('Download report', '下载报告')}</a> · <a href="index.html#issues">{tr('Verified cases', '已验证案例')}</a></p>
      <nav class="research-categories" aria-label="{tr('Progress sections', '进度栏目')}"><ul><li><a href="#coverage">{tr('Coverage', '覆盖')}</a></li><li><a href="#official-trackers">{tr('Official sources', '官方来源')}</a></li><li><a href="#candidates">{tr('GitHub review queue', 'GitHub 审阅队列')}</a></li><li><a href="#skipped">{tr('Skipped entries', '已跳过条目')}</a></li></ul></nav></header>
      <section class="block" id="coverage"><h2>{tr('Framework coverage', '框架覆盖')}</h2>
      <p class="section-copy">{tr('Each enabled repository gets a most-discussed window and a recently-updated window, up to 20 issues each. This bounded survey does not cover every issue or external tracker.', '每个启用 Issues 的仓库分别搜索讨论最多和最近更新的窗口，各取最多 20 条。本轮为有界搜索，未覆盖所有 issue 或外部跟踪器。')}</p>
      <div class="discovery-scroll"><table><thead><tr><th>{tr('Repository', '仓库')}</th><th>{tr('Domain', '领域')}</th><th>Stars</th><th>{tr('Hits', '命中')}</th><th>{tr('Coverage evidence', '覆盖证据')}</th></tr></thead><tbody>{''.join(coverage_rows)}</tbody></table></div></section>
      <section class="block" id="official-trackers"><h2>{tr('Official tracker searches', '官方跟踪器搜索')}</h2><p class="section-copy">{tr('Apache Jira uses votes and recent updates. PostgreSQL archive windows use relevance and date for async messages from the past year. MySQL Bugs uses relevance and updated dates for asynchronous reports. Each window collects up to 20 entries. These metrics stay separate from GitHub reactions; every entry needs applicability review.', 'Apache Jira 按投票和最近更新搜索；PostgreSQL 档案按相关性和日期检索近一年含 async 的邮件；MySQL Bugs 按相关性与更新日期检索 asynchronous 报告。每窗最多 20 条。各来源指标与 GitHub 关注反应分开；每条仍需审阅适用性。')}</p>{''.join(official_sections)}</section>
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
