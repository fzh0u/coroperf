#!/usr/bin/env python3
"""Build the static evidence atlas from the checked-in public snapshot."""

from collections import Counter
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEATURED = [
    ("dotnet--runtime--60764", "Managed identity", "Recovering Main after an async resume"),
    ("sgl-project--sglang--50722", "Performance", "Finding the poll loop behind a throughput drop"),
    ("drogonframework--drogon--2331", "Native disassembly", "Attributing a database stall in a stripped binary"),
    ("vercel--next.js--74988", "Framework ownership", "Finding the components behind a render failure"),
]
STATE = {
    "creation": "Coroutine stack joined",
    "renderer": "Renderer chain linked",
    "physical": "Physical stacks captured",
    "missing": "No stack captured",
}


def document(title, description, body, prefix="", script=""):
    output = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#772f26">
  <meta name="description" content="{escape(description)}">
  <title>{escape(title)} · coroPerf</title>
  <link rel="stylesheet" href="{prefix}assets/site.css">
  {script}
</head>
<body>
  <a class="skip" href="#main">Skip to content</a>
  <header class="site-header">
    <div class="wrap header-row">
      <a class="brand" href="{prefix}index.html"><span class="mark" aria-hidden="true"><i></i><i></i><i></i></span>coro<em>Perf</em></a>
      <nav aria-label="Main navigation">
        <a href="{prefix}index.html#issues">Issue evidence</a>
        <a href="{prefix}research.html">Research notes</a>
        <a href="{prefix}index.html#method">Method</a>
      </nav>
    </div>
  </header>
  <main id="main">{body}</main>
  <footer class="site-footer"><div class="wrap"><span>coroPerf · Coroutine Evidence Atlas</span><a href="#main">Back to top ↑</a></div></footer>
</body>
</html>
"""
    return "\n".join(line.rstrip() for line in output.splitlines()) + "\n"


def case_state(case):
    if any(join["relation"] == "creation" for join in case["joins"]):
        return "creation"
    if case["joins"]:
        return "renderer"
    return "physical" if case["physical"] else "missing"


def pill(state):
    return f'<span class="pill {state}">{STATE[state]}</span>'


def frame_rows(frames):
    rows = []
    for frame in frames:
        location = frame["file"]
        if location and frame["line"]:
            location += f':{frame["line"]}'
        source = f'<span>{escape(location)}</span>' if location else ""
        rows.append(f'<li><code>{escape(frame["function"])}</code>{source}</li>')
    return '<ol class="frames">' + "".join(rows) + "</ol>"


def stack(block, title, extra_class=""):
    kind = block["sample_kind"]
    note = f" · {escape(kind.replace('_', ' '))}" if kind and kind != "unknown" else ""
    return (
        f'<section class="stack {extra_class}">'
        f'<div class="stack-head"><h4>{escape(title)}</h4>'
        f'<span>Record {escape(block["id"])}{note}</span></div>'
        f'{frame_rows(block["frames"])}</section>'
    )


def lineage(join):
    ancestors = join["ancestors"]
    if not ancestors:
        return ""
    renderer = join["relation"] == "renderer"
    blocks = []
    for ancestor in ancestors:
        relation = ("JSX render owner" if renderer else
                    "Recorded async parent" if ancestor["link_to_child"] == "parent_to_create" else
                    "Recorded creator")
        heading = ancestor["component"] if renderer and ancestor["component"] else "Ancestor creation stack"
        blocks.append(stack(ancestor, heading))
        blocks.append(f'<div class="edge">↓ <span>{relation}</span><code>{escape(ancestor["link_to_child"])}</code></div>')
    return "".join(blocks)


def trace(join):
    creation = join["creation"]
    observation = join["observation"]
    renderer = join["relation"] == "renderer"
    opening = "Renderer registration stack" if renderer else "Creation stack"
    ending = "Observed render stack" if renderer else "Observed execution stack"
    boundary = "Same recorded renderer instance" if renderer else "Same coroutine instance across records"
    if join["edge"] == "runtime_task_id":
        boundary = "Same runtime task ID in one process"
    evidence = [*join["ancestors"], creation]
    components = [entry["component"] for entry in evidence if entry["component"]]
    chain = ""
    if renderer and len(components) > 1:
        chain = '<p class="chain">' + " <span>→</span> ".join(map(escape, components)) + "</p>"
    return f"""
      <div class="trace-grid">
        <div class="trace-pane stitched">
          <h3>CoroPerf connected stack</h3>
          {chain}
          {lineage(join)}
          {stack(creation, opening)}
          <div class="edge">↓ <span>{boundary}</span><code>{escape(join["edge"])}</code></div>
          {stack(observation, ending, "observed")}
        </div>
        <div class="trace-pane">
          <h3>Original physical stack</h3>
          {stack(observation, ending, "observed")}
          <p class="small trace-note">The frames on record {escape(observation["id"])} before stitching. Both columns list frames from caller to callee.</p>
        </div>
      </div>"""


def provenance(join):
    if join.get("capture_label"):
        return join["capture_label"]
    if join["historical_pair"]:
        return "Reviewed creation-to-observation witness"
    if join["selected_witness"]:
        return "Observation selected in the issue review"
    return "Other observation in the same capture"


def physical_stacks(blocks):
    if not blocks:
        return ""
    content = []
    for i, record in enumerate(blocks):
        event = str(record["event"] or "stack").replace("_", " ")
        heading = "Captured stack"
        leaf = record["frames"][-1]["function"]
        content.append(f'<details class="extra" {"open" if i == 0 else ""}>'
                       f'<summary>Record {escape(record["id"])} · {escape(event)}'
                       f'<code>{escape(leaf)}</code></summary>{stack(record, heading)}</details>')
    return "".join(content)


def case_page(case):
    state = case_state(case)
    joins = case["joins"]
    if joins:
        if state == "renderer":
            explanation = "The React renderer records the component-owner relationship and links the throw to the same registered renderer instance."
        elif joins[0]["edge"] == "runtime_task_id":
            explanation = "The runtime spawn hook and the helper-body observation record the same Tokio task ID in one process. The graph also records the task that spawned it."
        else:
            explanation = "CoroPerf follows a recorded graph edge from a creation stack to an observation of the same coroutine instance. Any additional creator links appear above the creation stack."
        displays = [f'<p class="provenance">{provenance(joins[0])} · observation {escape(joins[0]["observation"]["id"])}</p>{trace(joins[0])}']
        for join in joins[1:]:
            displays.append(f'<details class="extra more-trace"><summary>{provenance(join)} · observation '
                            f'{escape(join["observation"]["id"])}</summary>{trace(join)}</details>')
        content = "".join(displays)
        if case["physical"]:
            content += f'<h3 class="related-head">Other captured stacks</h3>{physical_stacks(case["physical"])}'
    elif state == "physical":
        explanation = "The available capture has stack frames, but supplies no verified join between a creation stack and an observed execution stack."
        content = physical_stacks(case["physical"])
    else:
        explanation = "This case has no captured stack frames in the published snapshot. The findings below record the scope and outcome of the investigation."
        content = ""
    source = ""
    if case["upstream_reference"] and case["upstream_reference"] != case["url"]:
        source = f'<a href="{escape(case["upstream_reference"])}">Follow-up evidence ↗</a>'
    fields = [("observation", "Local observation"), ("interpretation", "What CoroPerf showed"), ("limits", "Scope and limits")]
    findings = "".join(
        f'<div><dt>{label}</dt><dd>{escape(case["findings"][key])}</dd></div>'
        for key, label in fields if case["findings"].get(key)
    )
    origin = "Confirmed in the issue review" if case["reviewed_origin"] else "Outside the reviewed origin lower bound"
    body = f"""
    <article class="wrap case">
      <a class="back" href="../index.html#issues">← Issue evidence</a>
      <header class="case-header">
        <p class="eyebrow">{escape(case["reference"])}</p>
        <h1>{escape(case["title"])}</h1>
        <div class="case-links"><a href="{escape(case["url"])}">Upstream report ↗</a>{source}</div>
        <dl class="case-status">
          <div><dt>Reproduction</dt><dd>{escape(case["reproduction"])}</dd></div>
          <div><dt>Diagnosis</dt><dd>{escape(case["diagnosis"])}</dd></div>
          <div><dt>Reviewed coroutine origin</dt><dd>{origin}</dd></div>
        </dl>
      </header>
      <section class="call-stack" aria-labelledby="stack-title" id="call-stack">
        <div class="section-head"><h2 id="stack-title">Call-stack evidence</h2>{pill(state)}</div>
        <p class="section-copy">{explanation}</p>
        {content}
      </section>
      <section class="findings" aria-labelledby="findings-title">
        <div class="section-head"><h2 id="findings-title">Issue findings</h2></div>
        <dl>{findings}</dl>
      </section>
    </article>"""
    return document(case["reference"], case["title"], body, "../")


def featured_card(case, label, headline):
    return f"""
      <a class="feature" href="evidence/{escape(case["id"])}.html">
        <span class="feature-label">{escape(label)}</span>
        <h3>{escape(headline)}</h3>
        <span class="feature-ref">{escape(case["reference"])} <span aria-hidden="true">↗</span></span>
      </a>"""


def table_row(case):
    state = case_state(case)
    reviewed = "yes" if case["reviewed_origin"] else "no"
    return f"""
      <tr data-state="{state}" data-reviewed="{reviewed}">
        <th scope="row"><a href="evidence/{escape(case["id"])}.html"><span>{escape(case["reference"])}</span>{escape(case["title"])}</a></th>
        <td>{pill(state)}</td><td>{escape(case["reproduction"])}</td>
      </tr>"""


def index_page(snapshot):
    cases = snapshot["cases"]
    by_id = {case["id"]: case for case in cases}
    totals = Counter(map(case_state, cases))
    dotnet = by_id["dotnet--runtime--60764"]
    example = dotnet["joins"][0]
    top = example["creation"]["frames"][0]["function"]
    leaf = next(frame["function"] for frame in example["observation"]["frames"] if frame["function"] == "A..ctor")
    selected = "".join(featured_card(by_id[identifier], label, title) for identifier, label, title in FEATURED)
    stats = [
        (len(cases), "Issue evidence pages"),
        (totals["creation"], "Coroutine stack joins"),
        (totals["renderer"], "Renderer chains"),
        (snapshot["historical_origin_lower_bound"], "Reviewed origins in the full study"),
    ]
    numbers = "".join(f"<div><dd>{n:,}</dd><dt>{escape(title)}</dt></div>" for n, title in stats)
    options = "".join(f'<option value="{key}">{text}</option>' for key, text in STATE.items())
    rows = "".join(map(table_row, cases))
    body = f"""
    <section class="wrap hero" aria-labelledby="hero-title">
      <div>
        <p class="eyebrow">Coroutine Evidence Atlas</p>
        <h1 id="hero-title">Follow the stack<br>across <em>resumes.</em></h1>
        <p class="hero-copy">Explore real issue reproductions, performance investigations, and the recorded stack links that recover where asynchronous execution began.</p>
        <div class="actions"><a class="button" href="#issues">Browse issue evidence ↓</a><a href="research.html">Read the research notes ↗</a></div>
      </div>
      <figure class="specimen">
        <figcaption><span>From the issue evidence</span><a href="evidence/dotnet--runtime--60764.html#call-stack">dotnet/runtime #60764 ↗</a></figcaption>
        <div class="specimen-body">
          <div class="specimen-block"><span>Creation · record {escape(example["creation"]["id"])}</span><code>{escape(top)}</code><code>{escape(example["creation"]["frames"][-1]["function"])}</code></div>
          <div class="specimen-edge">↓ &nbsp; Same state-machine instance</div>
          <div class="specimen-block"><span>Observation · record {escape(example["observation"]["id"])}</span><code>Program.Foo [MoveNext]</code><code>{escape(leaf)}</code></div>
        </div>
        <div class="specimen-foot">Selected frames from the recorded join</div>
      </figure>
    </section>
    <section class="wrap block" aria-labelledby="coverage">
      <div class="section-head"><h2 id="coverage">Evidence coverage</h2><span class="small">Corpus snapshot · <time>{escape(snapshot["corpus_date"])}</time></span></div>
      <dl class="stats">{numbers}</dl>
    </section>
    <section class="wrap block" aria-labelledby="selected">
      <div class="section-head"><h2 id="selected">Selected investigations</h2></div>
      <div class="features">{selected}</div>
    </section>
    <section class="wrap block" id="issues" aria-labelledby="issues-title">
      <div class="section-head"><h2 id="issues-title">Issue evidence</h2><a href="data/cases.json" download>Download snapshot data ↓</a></div>
      <p class="section-copy">Open a case to inspect its connected call stack, original physical frames, local findings, and upstream report. Cases with limited captures describe the evidence gap.</p>
      <div class="filters" hidden>
        <div><label for="query">Search issues</label><input type="search" id="query" placeholder="Project, issue number, or title"></div>
        <div><label for="state">Call stack</label><select id="state"><option value="">Any stack status</option>{options}</select></div>
        <div><label for="origin">Issue review</label><select id="origin"><option value="">Any review status</option><option value="yes">Confirmed coroutine origin</option></select></div>
      </div>
      <p class="results-count" id="results-count" role="status">{len(cases)} issues</p>
      <div class="table-wrap">
        <table><thead><tr><th scope="col">Issue</th><th scope="col">Call stack</th><th scope="col">Reproduction</th></tr></thead>
        <tbody id="case-rows">{rows}</tbody></table>
      </div>
    </section>
    <section class="method" id="method" aria-labelledby="method-title">
      <div class="wrap">
        <div class="section-head"><h2 id="method-title">How to read the evidence</h2></div>
        <div class="method-grid">
          <div><h3>The recorded join</h3><p>Each join has two stack-bearing records with a shared instance identity and a recorded graph edge or audited runtime task ID. Parent and renderer-owner links have their own labels. Frames run from caller to callee within each record.</p></div>
          <div><h3>Two coverage measures</h3><p>The join count measures coverage in the published captures. The lower bound of {snapshot["historical_origin_lower_bound"]} measures issue-relevant origins reviewed in the underlying {snapshot["historical_issues"]}-issue corpus. A join from a different observation in the same capture may provide context while the origin relevant to the reported symptom remains open.</p></div>
          <div><h3>Reproduction scope</h3><p>The affected example, a reproduced component, and a limited or unavailable reproduction have distinct labels. A case can show a physical stack or diagnose a symptom even when creation was outside the capture window.</p></div>
        </div>
      </div>
    </section>"""
    return document("Coroutine Evidence Atlas", "Real systems issues and the recorded call-stack joins that recover coroutine origins.",
                    body, script='<script defer src="assets/filter.js"></script>')


def main():
    snapshot = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    generated = set()
    for case in snapshot["cases"]:
        path = evidence / f'{case["id"]}.html'
        path.write_text(case_page(case), encoding="utf-8")
        generated.add(path)
    for stale in set(evidence.glob("*.html")) - generated:
        stale.unlink()
    (ROOT / "index.html").write_text(index_page(snapshot), encoding="utf-8")
    research = (ROOT / "scripts" / "research.fragment.html").read_text(encoding="utf-8")
    (ROOT / "research.html").write_text(document("Research notes", "Performance and assembly-assisted coroutine investigations.",
                                                 research), encoding="utf-8")


if __name__ == "__main__":
    main()
