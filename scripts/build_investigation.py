#!/usr/bin/env python3
"""Build an investigation separately from captured, verified case evidence."""
from html import escape as e
import json
from pathlib import Path
from build import document

ROOT = Path(__file__).resolve().parents[1]


def render(case, language):
    zh = language == 'zh-CN'
    def tr(en, cn):
        return cn if zh else en
    def text(value):
        return e(value[language])
    title = tr('Asio #1720: locating the missing write completion', 'Asio #1720：定位丢失的 write 完成事件')
    description = tr('Investigation created; reproduction, diagnosis and repair are pending.', '已建立调查案例；复现、诊断和修复结果待完成。')
    hypotheses = ''.join(f'<tr><th scope="row">{e(h["id"])} · {text(h["claim"])}</th><td>{text(h["distinguish"])}</td></tr>' for h in case['hypotheses'])
    relations = ''.join(f'<li>{text(row)}</li>' for row in case['required_relations'])
    comparisons = ''.join(f'<li>{text(row)}</li>' for row in case['comparisons'])
    body = f'''<article class="wrap research open-review">
      <section class="block"><a href="../open-issues.html">{tr('Back to open investigations', '返回待分析 Issue')}</a>
        <h1>{title}</h1><p>{description}</p><p>{text(case['source_scope'])}</p>
        <p><a href="{e(case['url'])}">{tr('Upstream issue', '上游 issue')}</a> · <a href="{'../../' if zh else '../'}data/investigations/asio-1720.json">{tr('Case record', '案例记录')}</a></p>
      </section>
      <section class="block"><h2>{tr('Observed problem and existing evidence', '问题与已有证据')}</h2><p class="section-copy">{text(case['known'])}</p></section>
      <section class="block"><h2>{tr('Competing explanations', '待区分的解释')}</h2><div class="review-scroll"><table><thead><tr><th>{tr('Hypothesis', '假设')}</th><th>{tr('Discriminating evidence', '区分证据')}</th></tr></thead><tbody>{hypotheses}</tbody></table></div></section>
      <section class="block"><h2>{tr('Function-stack comparison to collect', '待采集的函数栈对比')}</h2><p class="section-copy">{tr('No captured stacks or flame graphs exist for this investigation yet. These are collection targets.', '本调查尚无采集栈或火焰图，以下是待验证的采集目标。')}</p>
        <div class="review-scroll"><table><thead><tr><th>{tr('Ordinary diagnostics', '普通诊断')}</th><th>{tr('With CoroPerf', '增加 CoroPerf')}</th></tr></thead><tbody><tr><td>{text(case['evidence_comparison']['ordinary'])}</td><td>{text(case['evidence_comparison']['with_coroperf'])}</td></tr></tbody></table></div>
      </section>
      <section class="block"><h2>{tr('Identity and event chain', '身份与事件链')}</h2><ul>{relations}</ul><p>{text(case['proposed_addition'])}</p></section>
      <section class="block"><h2>{tr('Reproduction and controls', '复现与对照')}</h2><ol>{comparisons}</ol></section>
      <section class="block"><h2>{tr('Next action and limits', '下一步与当前边界')}</h2><p class="section-copy">{text(case['next_action'])}</p><p>{text(case['limits'])}</p></section>
    </article>'''
    return document('investigations/asio-1720.html', title, description, body, language).replace('</head>', f'<link rel="stylesheet" href="{"../../" if zh else "../"}assets/open-issues.css">\n</head>')


if __name__ == '__main__':
    case = json.loads((ROOT / 'data/investigations/asio-1720.json').read_text())
    for language, prefix in [('en', ''), ('zh-CN', 'zh-cn/')]:
        path = ROOT / prefix / 'investigations/asio-1720.html'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(case, language), encoding='utf-8')
    print('Built bilingual Asio #1720 investigation pages.')
