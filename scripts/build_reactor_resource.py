#!/usr/bin/env python3
"""Build the supplemental resource page from its saved public evidence."""
from html import escape
import json
from pathlib import Path
from build import document

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'data/reactor-4478-verification.json').read_text())
V = DATA['verification']
PATH = 'evidence/reactor-4478-resource.html'


def stack(frames):
    return '\n'.join(escape(f["function"] + ' (' + f['file'] + (':' + str(f['line']) if f['line'] else '') + ')')
                     for f in frames)


for language in ('en', 'zh-CN'):
    zh = language == 'zh-CN'
    def tr(en, cn):
        return cn if zh else en
    title = tr('Reactor #4478: disposal worker origin', 'Reactor #4478：清理工作线程来源')
    prefix = '../../' if zh else '../'
    facts = V['native_result']
    rows = [(tr('Library / JDK', '库 / JDK'), 'Reactor 3.8.8 · reactive-streams 1.0.4 · JDK 21.0.1'),
            (tr('Disposal returned', '清理返回'), f"{facts['dispose_returned_ms']:.2f} ms"),
            (tr('Worker after disposal', '清理后的工作线程'), tr('Alive · non-daemon · TIMED_WAITING', '仍存活 · 非守护 · TIMED_WAITING')),
            (tr('Natural JVM exit', 'JVM 自然退出'), f"{facts['process_exit_seconds']:.2f} s"),
            (tr('Preparation and first check', '准备与首轮检查'), f"{V['first_check_seconds']:.2f} s · " + tr('one execution', '执行一次'))]
    table = ''.join(f'<tr><th scope="row">{escape(a)}</th><td>{escape(b)}</td></tr>' for a, b in rows)
    observed, origin = DATA['capture']['segments'][1], DATA['capture']['segments'][0]
    body = f'''<section class="wrap block">
      <p class="eyebrow">{tr('Supplemental resource provenance · outside the selected catalogue', '补充资源来源证据 · 不计入已选目录')}</p>
      <h1>{escape(title)}</h1>
      <p>{tr('One unused-scheduler disposal returns promptly but leaves a non-daemon internal worker. The JVM waits for its idle timeout before exiting.', '一次未使用 scheduler 的清理很快返回，但内部非守护工作线程仍存活，JVM 等待其空闲超时后退出。')}</p>
      <p><a href="https://github.com/reactor/reactor-core/issues/4478">{tr('Upstream report', '上游报告')}</a> · <a href="{prefix}data/reactor-4478-verification.json">{tr('Saved evidence and hashes', '保存的证据与哈希')}</a></p>
      <table><tbody>{table}</tbody></table>
    </section>
    <section class="wrap block">
      <h2>{tr('What the connection adds', '接合补充了什么')}</h2>
      <p>{tr('The physical worker stack contains only the idle queue and executor. The creation stack identifies SchedulerState disposal machinery and beginDisposeApplication, which has already returned. CoroPerf shared analysis joins the two records by the same retained Thread object and Java Thread ID.', '工作线程的物理栈仅有空闲队列及执行器；创建栈指出 SchedulerState 清理机制和已经返回的 beginDisposeApplication。CoroPerf 共享分析通过同一个保留的 Thread 对象及其 Java Thread ID 接合两条记录。')}</p>
      <p>{tr('An explicit extra ThreadFactory observer delegates to the original factory and returns its Thread unchanged. It records resource creation; it does not provide a coroutine parent graph or automatic semantic diagnosis.', '明确新增的 ThreadFactory 观察器调用原工厂，原样返回其 Thread。它记录资源创建，不提供协程父图或自动语义诊断。')}</p>
      <table><thead><tr><th>{tr('Physical observation · record 2', '物理观测 · 记录 2')}</th><th>{tr('Recovered creation · record 1', '恢复的创建来源 · 记录 1')}</th></tr></thead>
      <tbody><tr><td><pre style="white-space:pre-wrap;overflow-wrap:anywhere">{stack(observed['frames'])}</pre></td>
      <td><pre style="white-space:pre-wrap;overflow-wrap:anywhere">{stack(origin['frames'])}</pre></td></tr></tbody></table>
      <p>{tr('The current folded output lacks the application caller; the causal folded output contains it. Both are included in the evidence download.', 'current folded 输出缺少应用调用者，causal folded 输出包含该调用者；两者均随证据下载提供。')}</p>
    </section>
    <section class="wrap block">
      <h2>{tr('Repair guidance and limits', '修复方向与范围')}</h2>
      <p>{tr('The report proposes daemon workers for TRANSITION_AWAIT_POOL. The source uses a default thread factory and a ten-second idle keep-alive. No fix or alternate version was executed.', '报告建议让 TRANSITION_AWAIT_POOL 使用守护线程。源码使用默认线程工厂和十秒空闲保留时间。本次没有测试修复或其他版本。')}</p>
      <p>{tr('This is one Linux/JDK21 component adaptation of a WSL2/JDK27 report. The process exits normally; no permanent leak, full Reactor subscription lineage, generic automatic thread capture or production overhead result is claimed. The selected catalogue remains at 127.', '这是对 WSL2/JDK27 报告的一次 Linux/JDK21 组件适配。进程正常退出；没有证明永久泄漏、完整 Reactor 订阅关系、通用自动线程采集或生产开销。已选目录仍为 127 条。')}</p>
    </section>'''
    destination = ROOT / ('zh-cn' if zh else '') / PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document(PATH, title, title, body, language))
    print(destination.relative_to(ROOT))
