#!/usr/bin/env python3
"""Build an investigation separately from captured, verified case evidence."""
from html import escape as e
import json
from pathlib import Path
from build import document

ROOT = Path(__file__).resolve().parents[1]


def render_result(case, language):
    zh = language == 'zh-CN'
    def tr(en, cn):
        return cn if zh else en
    def text(value):
        return e(value[language])
    result = json.loads((ROOT / case['results']['path']).read_text())
    prefix = '../../' if zh else '../'
    evidence = prefix + 'data/investigations/asio-1720-evidence/'
    title = text(case['title'])
    rows = ''.join(
        f'<tr><th scope="row">{e(row["name"])}</th><td>3</td>'
        f'<td>{tr("Complete", "完成") if row["expected_exit_code"] == 0 else tr("Timeout", "超时")} · 3/3</td></tr>'
        for row in result['variants'])
    joins = ''.join(f'<tr><td>{e(row["operation"])}</td><td>{e(row["coroutine"])}</td>'
                    f'<td>{e(row["parent"])}</td></tr>' for row in result['operation_to_coroutine'])
    frames = '\n'.join(e(f.get('function') or '[unknown]') for f in result['physical_initiation_stack'])
    downloads = ''.join(f'<li><a href="{e(evidence + name)}">{e(name)}</a></li>' for name in
                        ('result.json', 'reproduction.json', 'coroperf-graph.json',
                         'reactor-events.jsonl', 'coroperf-events.log', 'repair.patch'))
    body = f'''<article class="wrap research open-review">
      <section class="block"><a href="../open-issues.html">{tr('Back to Open Issues', '返回 Open Issues')}</a>
        <h1>{title}</h1><p>{text(case['result_summary'])}</p>
        <p><a href="{e(case['url'])}">{tr('Upstream issue', '上游 issue')}</a> ·
        <a href="{e(evidence)}result.json">{tr('Measured evidence', '实测证据')}</a> · {e(result['checked_at'])}</p>
      </section>
      <section class="block"><h2>{tr('Root cause', '根因')}</h2><p>{text(case['root_cause'])}</p>
        <ol>{''.join(f'<li>{text(step)}</li>' for step in case['causal_chain'])}</ol>
        <p>{text(case['repair_status'])}</p><p><a href="{e(evidence)}repair.patch">{tr('Locally validated patch', '本地验证的补丁')}</a></p>
      </section>
      <section class="block"><h2>{tr('Unchanged reproducer and controls', '未改动的复现程序与对照')}</h2>
        <p>{text(case['execution_scope'])}</p>
        <p>Boost {e(result['local_environment']['boost'])} · {e(result['local_environment']['compiler'])}</p>
        <div class="review-scroll"><table><thead><tr><th>{tr('Variant', '配置')}</th><th>{tr('Runs', '次数')}</th><th>{tr('Result', '结果')}</th></tr></thead><tbody>{rows}</tbody></table></div>
        <p>{tr('The three-second timeout belongs to the upstream standalone attachment. Cleanup can print operation_aborted and another Try line after the wait has already failed; these are not additional pre-timeout completions.', '三秒超时来自上游 standalone 附件。等待失败后的清理可能打印 operation_aborted 和下一条 Try；这些不是超时前新增的完成操作。')}</p>
      </section>
      <section class="block"><h2>{tr('What CoroPerf adds', 'CoroPerf 补出了什么')}</h2><p>{text(case['observed_addition'])}</p>
        <div class="review-scroll"><table><thead><tr><th>{tr('Write operation generation', 'write 操作代次')}</th><th>{tr('Coroutine generation', '协程代次')}</th><th>{tr('Creator', '创建者')}</th></tr></thead><tbody>{joins}</tbody></table></div>
        <p>{tr('Eight creations and eight destructions were captured. Six child lifetimes reused one address; the fifth issued the stalled write and the sixth arose during cleanup. With activation intervals, six creation edges link to the writer; instruction-only creation unwinding leaves those six parents unknown. This capture accepts ', '共捕获八次创建和八次销毁。六个子协程寿命复用一个地址：第五代发起挂起的 write，第六代来自清理。启用激活区间证据后，六条创建边接回 writer；仅指令展开时，这六个创建者均未知。本次接受归属的观测为 ')}{result['owner_samples_accepted']}/{result['owner_samples_total']}.
        {tr('This is an admission count, not independently scored recall or precision.', '这是证据接受计数，不是独立真值评分的 recall 或 precision。')}</p>
        <h3>{tr('Without and with retained history', '有／无保留历史的函数栈')}</h3>
        <p>{tr('Both flame views use the same one actual observation of the fifth child just before write initiation. Width counts one diagnostic observation, not CPU time. Each segment shows at most six physical frames; creation history adds typed boundaries.', '两幅火焰图使用第五代子协程发起 write 前的同一条真实观测。宽度表示一条诊断观测，不是 CPU 时间；每段最多显示六个物理帧，创建历史用明确边界接入。')}</p>
        <p><a href="{e(evidence)}current.svg">Without CoroPerf</a> · <a href="{e(evidence)}causal.svg">With CoroPerf</a></p>
        <img style="width:100%;height:auto" src="{e(evidence)}current.svg" alt="Without retained creation history">
        <img style="width:100%;height:auto" src="{e(evidence)}causal.svg" alt="With recorded creation history">
        <details><summary>{tr('Raw physical stack at write initiation', 'write 发起时的原始物理栈')}</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">{frames}</pre></details>
      </section>
      <section class="block"><h2>{tr('Scope and remaining checks', '范围与待补检查')}</h2><p>{text(case['limits'])}</p>
        <p>{tr('Ancestry identifies the relevant lifetime; the reactor observers and cause-specific repair establish the failure mechanism. Diagnosis speedup and collection overhead were not measured.', '创建历史负责定位相关寿命；reactor 观察点和针对原因的修改负责验证失败机制。尚未测量定位提速和采集开销。')}</p>
        <p>{text(case['next_action'])}</p><ul>{downloads}</ul>
      </section></article>'''
    return document('investigations/asio-1720.html', title, text(case['result_summary']), body, language).replace(
        '</head>', f'<link rel="stylesheet" href="{prefix}assets/open-issues.css">\n</head>')


def render(case, language):
    if case.get('results') and case['results'].get('path'):
        return render_result(case, language)
    zh = language == 'zh-CN'
    def tr(en, cn):
        return cn if zh else en
    def text(value):
        return e(value[language])
    slug = case.get('slug', 'asio-1720')
    title = text(case['title']) if case.get('title') else tr('Asio #1720: locating the missing write completion', 'Asio #1720：定位丢失的 write 完成事件')
    description = tr('Investigation created; reproduction, diagnosis and repair are pending.', '已建立调查案例；复现、诊断和修复结果待完成。')
    hypotheses = ''.join(f'<tr><th scope="row">{e(h["id"])} · {text(h["claim"])}</th><td>{text(h["distinguish"])}</td></tr>' for h in case['hypotheses'])
    relations = ''.join(f'<li>{text(row)}</li>' for row in case['required_relations'])
    comparisons = ''.join(f'<li>{text(row)}</li>' for row in case['comparisons'])
    repair_status = (f'<p class="section-copy">{text(case["repair_status"])}</p>'
                     if case.get('repair_status') else '')
    body = f'''<article class="wrap research open-review">
      <section class="block"><a href="../open-issues.html">{tr('Back to open investigations', '返回待分析 Issue')}</a>
        <h1>{title}</h1><p>{description}</p><p>{text(case['source_scope'])}</p>
        <p><a href="{e(case['url'])}">{tr('Upstream issue', '上游 issue')}</a> · <a href="{'../../' if zh else '../'}data/investigations/{e(slug)}.json">{tr('Case record', '案例记录')}</a></p>
      </section>
      <section class="block"><h2>{tr('Observed problem and existing evidence', '问题与已有证据')}</h2><p class="section-copy">{text(case['known'])}</p>{repair_status}</section>
      <section class="block"><h2>{tr('Competing explanations', '待区分的解释')}</h2><div class="review-scroll"><table><thead><tr><th>{tr('Hypothesis', '假设')}</th><th>{tr('Discriminating evidence', '区分证据')}</th></tr></thead><tbody>{hypotheses}</tbody></table></div></section>
      <section class="block"><h2>{tr('Function-stack comparison to collect', '待采集的函数栈对比')}</h2><p class="section-copy">{tr('No captured stacks or flame graphs exist for this investigation yet. These are collection targets.', '本调查尚无采集栈或火焰图，以下是待验证的采集目标。')}</p>
        <div class="review-scroll"><table><thead><tr><th>{tr('Ordinary diagnostics', '普通诊断')}</th><th>{tr('With CoroPerf', '增加 CoroPerf')}</th></tr></thead><tbody><tr><td>{text(case['evidence_comparison']['ordinary'])}</td><td>{text(case['evidence_comparison']['with_coroperf'])}</td></tr></tbody></table></div>
      </section>
      <section class="block"><h2>{tr('Identity and event chain', '身份与事件链')}</h2><ul>{relations}</ul><p>{text(case['proposed_addition'])}</p></section>
      <section class="block"><h2>{tr('Reproduction and controls', '复现与对照')}</h2><ol>{comparisons}</ol></section>
      <section class="block"><h2>{tr('Next action and limits', '下一步与当前边界')}</h2><p class="section-copy">{text(case['next_action'])}</p><p>{text(case['limits'])}</p></section>
    </article>'''
    return document(f'investigations/{slug}.html', title, description, body, language).replace('</head>', f'<link rel="stylesheet" href="{"../../" if zh else "../"}assets/open-issues.css">\n</head>')


if __name__ == '__main__':
    for source in sorted((ROOT / 'data/investigations').glob('*.json')):
        case = json.loads(source.read_text())
        slug = case.get('slug', source.stem)
        for language, prefix in [('en', ''), ('zh-CN', 'zh-cn/')]:
            path = ROOT / prefix / 'investigations' / f'{slug}.html'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(case, language), encoding='utf-8')
        print(f'Built bilingual {case["reference"]} investigation pages.')
