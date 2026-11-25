#!/usr/bin/env python3
"""Render the read-only discovery report separately from verified case evidence."""
import argparse
from collections import Counter
from html import escape as e
import json
from pathlib import Path
from urllib.parse import urlsplit
from build import document

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = {'ML systems': '机器学习系统', 'Database': '数据库', 'Distributed systems': '分布式系统',
           'Language runtimes': '语言运行时与异步库'}
STATUSES = {
    'needs_review': ('Awaiting applicability review', '待审阅适用性'),
    'already_catalogued': ('Existing research entry', '已有研究记录'),
    'skipped_review': ('Reproduction deferred · review pending', '暂缓复现 · 待确认'),
    'excluded_after_review': ('Excluded after review', '审阅后排除'),
    'no_async_signal': ('No concrete async keyword', '未检出具体异步关键词'),
    'external_environment_required': ('External environment required', '依赖外部环境，已跳过'),
    'preparation_deferred': ('Preparation stopped · follow-up pending', '准备未完成 · 暂缓跟进'),
    'verified_case': ('Verified diagnostic case', '已验证诊断案例'),
    'component_reproduced': ('Component reproduced · see diagnostic scope', '组件已复现 · 诊断范围见记录'),
}
HOLD_REASONS = {
    'safety_review': ('Safety review pending', '安全影响待复核'),
    'automatic_review_rejection': ('Automatic approval review rejected further work', '自动审查拒绝继续执行'),
    'reported_runtime_failure': ('Reported runtime failure requires review', '报告中的运行时故障待复核'),
    'reported_failure_review': ('Reported failure requires review', '报告中的故障待复核'),
    'user_request': ('Skipped at user request', '按用户要求跳过'),
    'platform_unavailable': ('Required platform unavailable', '缺少所需平台'),
    'temporary_user_deferral': ('Preparation stopped within its time budget', '准备超出时间预算，暂缓'),
}


def skipped_entries(report):
    """Keep persistent holds and current signal-based skips visible together."""
    entries = {}
    urls = set()
    for row in report['deferred_registry']:
        entries[row['id']] = {**row, 'origin': 'registry', 'urls': [row['url']]}
        urls.add(row['url'])
    sources = [report.get('signal_holds', []), report['issues']] + [result['issues'] for result in report.get('official_tracker_results', [])]
    for source in sources:
        for row in source:
            if row['status'] != 'skipped_review' or row['url'] in urls:
                continue
            group = row.get('issue_group_id', row['id'])
            if group in entries:
                # Explicit bug IDs may group several mail messages; never infer a bug from a subject.
                if row['id'] != group and row['url'] not in entries[group]['urls']:
                    entries[group]['urls'].append(row['url'])
                continue
            entries[group] = {**row, 'origin': 'signal', 'urls': [row['url']]}
            urls.add(row['url'])
    return list(entries.values())


def review_group(row):
    reason = row.get('skip_reason')
    if reason == 'automatic_review_rejection':
        return 'rejected'
    if reason in {'user_request', 'platform_unavailable', 'temporary_user_deferral'}:
        return 'other'
    return 'manual' if row['origin'] == 'registry' else 'signal'


def security_github_entry(row):
    url = urlsplit(row['url'])
    parts = url.path.strip('/').split('/')
    return (url.hostname == 'github.com' and len(parts) == 4 and
            parts[2] == 'issues' and parts[3].isdigit() and review_group(row) != 'other')


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
        f"{len(report['issues'])} unique GitHub search hits · {counts.get('needs_review', 0)} awaiting review · {complete}/{len(coverage)} repositories completed configured GitHub windows · {official_complete} official trackers searched · {gaps} repositories have GitHub Issues disabled.",
        f"{len(report['issues'])} 条去重 GitHub 命中 · {counts.get('needs_review', 0)} 条待审阅 · {complete}/{len(coverage)} 个仓库完成本轮 GitHub 窗口 · 已搜索 {official_complete} 个官方跟踪器 · {gaps} 个仓库未启用 GitHub Issues。")
    coverage_rows = []
    for row in coverage:
        if row.get('error'):
            outcome = tr('Metadata fetch failed; continue with the next repository.', '元数据获取失败，已继续下一仓库。')
        elif not row['has_issues']:
            outcome = tr('GitHub Issues disabled.', 'GitHub Issues 未启用。')
        elif not row['complete']:
            outcome = tr('Partial or failed search; this is a coverage gap.', '搜索不完整或失败，保留覆盖缺口。')
        else:
            windows = row.get('planned_windows', 2)
            outcome = tr(f'All {windows} configured GitHub windows completed.', f'已完成本轮 {windows} 个 GitHub 搜索窗口。')
        if row.get('discussion_depth_page'):
            outcome += tr(f' Rotating discussion page: {row["discussion_depth_page"]}.', f' 轮换热度页：第 {row["discussion_depth_page"]} 页。')
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
        canonical = row.get('canonical_repository') or row['repository']
        name = row['repository']
        if canonical.lower() != name.lower():
            name += ' → ' + canonical
        coverage_rows.append(f'<tr><th scope="row"><a href="https://github.com/{e(canonical)}">{e(name)}</a>{tracker}</th>'
                             f'<td>{domain(row["domain"])}</td><td>{row["stars"] if row["stars"] is not None else "—"}</td>'
                             f'<td>{row["unique_candidates"]}</td><td>{outcome}</td></tr>')
    candidate_rows = []
    for row in report['issues']:
        reason = status(row['status'])
        ordinal = row.get('coverage_rank', 10**9)
        reference = f'{row["repository"]} #{row["number"]}'
        if row.get('canonical_repository'):
            reference += ' → ' + row['canonical_repository']
        candidate_rows.append(
            f'<tr data-candidate data-domain="{e(row["domain"])}" data-status="{e(row["status"])}" '
            f'data-state="{e(row["state"])}" data-heat="{row["heat"]}" data-rank="{ordinal}">'
            f'<th scope="row"><a href="{e(row["url"])}"><span>{e(reference)}</span>{e(row["title"])}</a></th>'
            f'<td>{domain(row["domain"])}</td><td>{row["heat"]:.2f}<br>{row["comments"]} {tr("comments", "条评论")} · '
            f'{row["positive_reactions"]} {tr("reactions", "次关注反应")}</td>'
            f'<td>{tr(row["state"], "开放" if row["state"] == "open" else "已关闭")}</td><td>{reason}</td></tr>')
    deferred_rows = []
    skipped = skipped_entries(report)
    security_rows = [row for row in skipped if security_github_entry(row)]
    review_counts = Counter(review_group(row) for row in security_rows)
    for row in sorted(skipped, key=lambda row: (review_group(row) != 'rejected', row['origin'] != 'registry')):
        label = row.get('title_zh', row['title']) if zh else row['title']
        origin = tr('Manual review hold', '人工审阅暂缓') if row['origin'] == 'registry' else tr('Automatic review signal', '自动审阅信号')
        if review_group(row) == 'rejected':
            origin = tr('Automatic approval review rejected further work', '自动审查拒绝继续执行')
        reason = tr('Reproduction deferred; see the recorded reason.', '已暂缓复现，具体原因见记录。')
        if row.get('prior_local_execution') is True:
            reason = tr('Earlier local attempt recorded; further reproduction remains on hold.',
                        '历史上曾有本地尝试；当前暂缓后续复现。')
        elif row.get('prior_local_execution') is False:
            reason += tr(' No local execution recorded.', ' 未执行本地复现。')
        if row.get('skip_reason'):
            reason += '<br>' + tr('Recorded hold reason: ', '暂缓原因：') + e(HOLD_REASONS.get(row['skip_reason'], (row['skip_reason'], row['skip_reason']))[zh])
        if row.get('risk_signal'):
            reason += tr(' Wording at detection: ', ' 检出时的匹配词：') + e(row['risk_signal']) + '.'
            if row.get('risk_signal_source') == 'body_error_signature':
                reason += tr(' Reported error signature in the body.', ' 来源为正文中的错误签名。')
        if row.get('last_seen'):
            reason += '<br>' + tr('Last observed: ', '最近观测：') + e(row['last_seen'])
        if zh and row.get('review_note_zh'):
            reason += '<br>' + e(row['review_note_zh'])
        reference = ''
        if urlsplit(row['url']).hostname == 'github.com':
            parts = urlsplit(row['url']).path.strip('/').split('/')
            if len(parts) == 4:
                reference = f'<span>{e("/".join(parts[:2]))} #{e(parts[3])}</span>'
        links = ' · '.join(f'<a href="{e(url)}">{tr("Related source", "相关来源")} {n}</a>' for n, url in enumerate(row['urls'][1:], 2))
        deferred_rows.append(f'<tr data-skipped data-security-github="{str(security_github_entry(row)).lower()}" '
                             f'data-github="{str(bool(reference)).lower()}" data-review-group="{review_group(row)}">'
                             f'<th scope="row"><a href="{e(row["url"])}">{reference}{e(label)}</a>{"<br>" + links if links else ""}</th>'
                             f'<td>{origin}<br>{reason}</td></tr>')
    decisions = []
    for identifier, decision in report.get('review_decisions', {}).items():
        sources = ' · '.join(f'<a href="{e(url)}">{tr("Source", "来源")} {n}</a>' for n, url in enumerate(decision['sources'], 1))
        decisions.append(f'<li><strong>{e(identifier)}</strong>: {e(decision.get("reason_zh", decision["reason"]) if zh else decision["reason"])} {sources}</li>')
    records = []
    for record in report.get('supplemental_records', []):
        title = record['title_zh'] if zh else record['title']
        summary = record['summary_zh'] if zh else record['summary']
        url = ('../' if zh else '') + record['path']
        records.append(f'<li><a href="{e(url)}">{e(title)}</a> · <time>{e(record["checked_at"])}</time><p>{e(summary)}</p></li>')
    supplemental = (f'<section class="block"><h2>{tr("Additional review records", "补充审阅记录")}</h2><ul>{"".join(records)}</ul></section>' if records else '')
    progress = ''
    if facts := report.get('progress_summary'):
        added = facts['new_verified_ids']
        reviewed = facts['new_review_decision_ids']
        unknown = tr('baseline unavailable', '缺少可比较基线')
        added_label = str(len(added)) if added is not None else unknown
        review_label = str(len(reviewed)) if reviewed is not None else unknown
        progress_title = tr('Report update progress', '本次更新成果') if facts.get('source') == 'report_update' else tr('Periodic progress', '本次定时报告成果')
        progress = (f'<section class="block"><h2>{progress_title}</h2>'
                    f'<p>{tr("Verified catalogue entries", "已验证证据目录")} {facts["verified_catalogue_entries"]} · '
                    f'{tr("New entries since the comparison report", "相对基线新增证据")} {e(added_label)} · '
                    f'{tr("Review decisions", "逐项审阅结论")} {facts["review_decisions"]} · '
                    f'{tr("New review decisions", "新增审阅结论")} {e(review_label)}</p>'
                    f'<p>{tr("Manual holds", "人工暂缓")} {facts["manual_holds"]} · '
                    f'{tr("Persistent automatic signals", "持久自动信号")} {facts["automatic_signal_holds"]}</p>'
                    f'<p class="section-copy">{tr("Assembled", "汇总时间")} {e(facts["assembled_at"])} · '
                    f'{tr("Comparison report", "比较报告")} {e(facts.get("comparison_reported_at") or unknown)}. '
                    f'{tr("Deltas use the previous successful Git publication. Search hits do not count as verified cases.", "增量以最近一次 Git 发布成功的报告为基线。搜索命中不计为验证案例。")}</p></section>')
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
      <nav class="research-categories" aria-label="{tr('Progress sections', '进度栏目')}"><ul><li><a href="#coverage">{tr('Coverage', '覆盖')}</a></li><li><a href="#official-trackers">{tr('Official sources', '官方来源')}</a></li><li><a href="#candidates">{tr('GitHub review queue', 'GitHub 审阅队列')}</a></li><li><a href="#security-review">{tr('GitHub safety review', '安全相关 GitHub issue')}</a></li><li><a href="#skipped">{tr('Skipped entries', '已跳过条目')}</a></li></ul></nav></header>
      {progress}
      <section class="block" id="coverage"><h2>{tr('Framework coverage', '框架覆盖')}</h2>
      <p class="section-copy">{tr('Each enabled repository gets a most-discussed window and a recently-updated window, up to 20 issues each. This bounded survey does not cover every issue or external tracker.', '每个启用 Issues 的仓库分别搜索讨论最多和最近更新的窗口，各取最多 20 条。本轮为有界搜索，未覆盖所有 issue 或外部跟踪器。')}</p>
      <div class="discovery-scroll"><table><thead><tr><th>{tr('Repository', '仓库')}</th><th>{tr('Domain', '领域')}</th><th>Stars</th><th>{tr('Hits', '命中')}</th><th>{tr('Coverage evidence', '覆盖证据')}</th></tr></thead><tbody>{''.join(coverage_rows)}</tbody></table></div></section>
      <section class="block" id="official-trackers"><h2>{tr('Official tracker searches', '官方跟踪器搜索')}</h2><p class="section-copy">{tr('Apache Jira uses votes, recent updates and a title-focused async window. PostgreSQL archive windows use relevance and date for async messages from the past year. MySQL Bugs uses relevance and updated dates for asynchronous reports. Each window collects up to 20 entries. These metrics stay separate from GitHub reactions; every entry needs applicability review.', 'Apache Jira 按投票、最近更新及标题聚焦异步关键词搜索；PostgreSQL 档案按相关性和日期检索近一年含 async 的邮件；MySQL Bugs 按相关性与更新日期检索 asynchronous 报告。每窗最多 20 条。各来源指标与 GitHub 关注反应分开；每条仍需审阅适用性。')}</p>{''.join(official_sections)}</section>
      <section class="block" id="candidates"><h2>{tr('Review queue', '审阅队列')}</h2>
      <p class="section-copy">{tr('Heat uses comments, positive reactions and repository stars. Coverage order rotates domains and takes one issue per repository in each round. Search hits are never counted as CoroPerf successes.', '热度综合评论数、关注反应和仓库 stars。覆盖排序轮转各领域，每轮每个仓库最多选一条。搜索命中不计为 coroPerf 成功案例。')}</p>
      <details><summary>{tr('Ranking method', '排序方法')}</summary><p><code>{e(report['heat_formula'])}</code></p></details>
      <p class="section-copy">{tr('Each repository keeps its discussion head and recent-update windows. When more results exist, one deeper discussion page rotates every two hours, within the first 1,000 searchable results. Resuming a run keeps its saved page plan. Live rankings can change, so this is not exhaustive coverage.', '每个仓库保留热度首页和最近更新窗口；有更多结果时，每两小时轮换一个更深的热度页，范围限于可搜索的前 1,000 条。恢复同一轮任务沿用已保存的页码计划。实时排名会变化，因此不代表穷尽覆盖。')}</p>
      <div class="discovery-controls"><div><label for="discovery-search">{tr('Search', '搜索')}</label><input id="discovery-search" type="search" placeholder="{tr('Repository, title or issue number', '仓库、标题或 issue 编号')}"></div>{''.join(selects)}</div>
      <p id="discovery-count" role="status" aria-live="polite">{len(report['issues'])} {tr('search hits', '条搜索命中')}</p>
      <div class="discovery-scroll"><table><thead><tr><th>{tr('Issue', '问题')}</th><th>{tr('Domain', '领域')}</th><th>{tr('Heat', '热度')}</th><th>{tr('GitHub state', 'GitHub 状态')}</th><th>{tr('Review status', '审阅状态')}</th></tr></thead><tbody id="discovery-rows">{''.join(candidate_rows)}</tbody></table></div>
      <div class="discovery-pager" hidden><button id="discovery-previous" type="button">{tr('Previous', '上一页')}</button><span id="discovery-page"></span><button id="discovery-next" type="button">{tr('Next', '下一页')}</button></div></section>
      <section class="block" id="skipped"><h2>{tr('Deferred reproductions', '暂缓复现与待确认条目')}</h2><p class="section-copy">{tr(f'{len(skipped)} displayed review entries or explicit bug groups. Reasons include user requests, environment limits, and reported failure or resource signals. These are reproduction-routing records, not confirmed defect or vulnerability findings. Holds persist across runs, including entries absent from current windows. Replies with the same explicit bug number share one row.', f'展示 {len(skipped)} 条审阅记录或明确 bug 编号组。原因包括用户要求、环境限制，以及报告中的故障或资源线索。这些是复现任务分流记录，不代表已确认缺陷或漏洞；人工暂缓与自动信号跨轮次保留，包括未出现在本轮窗口的条目。同一明确 bug 编号的回复合并展示。')}</p>
      <div id="security-review"><h3>{tr('GitHub issues held for safety review', '安全相关 GitHub issue')}</h3>
      <p class="section-copy">{tr(f'{len(security_rows)} unique GitHub issues: {review_counts["manual"]} manual holds, {review_counts["rejected"]} automatic approval review holds and {review_counts["signal"]} automatic wording signals. Security impact remains unassessed. Ordinary user skips and environment or time-budget deferrals are available under All deferred entries.', f'{len(security_rows)} 个去重 GitHub issue：人工暂缓 {review_counts["manual"]} 个、自动审查拒绝 {review_counts["rejected"]} 个、自动词语信号 {review_counts["signal"]} 个。安全影响仍待评估。单纯按用户要求跳过、环境或时间预算暂缓的条目，可切换到“全部暂缓条目”查看。')}</p>
      <div class="discovery-controls review-controls">
      <div><label for="review-search">{tr('Search held issues', '搜索暂缓 issue')}</label><input id="review-search" type="search" placeholder="{tr('Repository, issue number, title or reason', '仓库、issue 编号、标题或原因')}"></div>
      <div><label for="review-scope">{tr('Scope', '范围')}</label><select id="review-scope"><option value="security">{tr('GitHub safety review', '安全相关 GitHub issue')}</option><option value="github">{tr('All deferred GitHub issues', '全部暂缓 GitHub issue')}</option><option value="all">{tr('All deferred entries', '全部暂缓条目')}</option></select></div>
      <div><label for="review-group">{tr('Hold source', '暂缓来源')}</label><select id="review-group"><option value="">{tr('All sources', '全部来源')}</option><option value="rejected">{tr('Automatic approval review', '自动审查拒绝')}</option><option value="manual">{tr('Manual review', '人工审阅')}</option><option value="signal">{tr('Automatic wording signal', '自动词语信号')}</option><option value="other">{tr('User / environment / time budget', '用户要求／环境／时间预算')}</option></select></div></div>
      <p id="review-count" role="status" aria-live="polite">{tr('Enable JavaScript to filter this complete list.', '启用 JavaScript 后可筛选下方完整列表。')}</p>
      <div class="discovery-scroll"><table><thead><tr><th>{tr('Entry', '条目')}</th><th>{tr('Hold reason and execution history', '暂缓原因与执行记录')}</th></tr></thead><tbody id="review-rows">{''.join(deferred_rows)}</tbody></table></div>
      <div class="discovery-pager review-pager" hidden><button id="review-previous" type="button">{tr('Previous', '上一页')}</button><span id="review-page"></span><button id="review-next" type="button">{tr('Next', '下一页')}</button></div></div></section>
      <section class="block"><h2>{tr('Review decisions', '逐项审阅结论')}</h2><ul>{''.join(decisions)}</ul></section>
      {supplemental}
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
