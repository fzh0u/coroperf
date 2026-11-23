#!/usr/bin/env python3
"""Build both versions of the static atlas from the public snapshot."""

from html import escape
import json
from pathlib import Path

from copy_text import COPY, FEATURES


ROOT = Path(__file__).resolve().parents[1]
FEATURED = (
    "dotnet--runtime--60764",
    "drogonframework--drogon--2331",
    "tokio-rs--tokio--6315",
    "grpc--grpc-kotlin--299",
)
SCOPES = ("Full local reproduction", "Component reproduced")


def document(path, title, description, body, language):
    text = COPY[language]
    chinese = language == "zh-CN"
    depth = path.count("/")
    prefix = "../" * depth
    assets = "../" * (depth + chinese)
    alternate = assets + ("" if chinese else "zh-cn/") + path
    alt_language, alt_name = ("en", "English") if chinese else ("zh-CN", "简体中文")
    language_links = (
        f'<a class="language-switch" id="language-switch" href="{alternate}" '
        f'lang="{alt_language}" hreflang="{alt_language}">{alt_name}</a>'
    )
    if chinese:
        language_links += '<span class="language-current" lang="zh-CN" aria-current="true">简体中文</span>'
    else:
        language_links = '<span class="language-current" lang="en" aria-current="true">English</span>' + language_links
    script = f'<script defer src="{assets}assets/filter.js"></script>' if path == "index.html" else ""
    output = f"""<!doctype html>
<html lang="{language}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#772f26">
  <meta name="description" content="{escape(description)}">
  <title>{escape(title)} · coroPerf</title>
  <link rel="alternate" hreflang="{alt_language}" href="{alternate}">
  <link rel="icon" type="image/png" href="{assets}assets/coroperf-pony.png">
  <link rel="stylesheet" href="{assets}assets/site.css">
  <script defer src="{assets}assets/navigation.js"></script>
  {script}
</head>
<body>
  <a class="skip" href="#main">{text["skip"]}</a>
  <header class="site-header">
    <div class="wrap header-row">
      <a class="brand" href="{prefix}index.html"><img class="brand-pony" src="{assets}assets/coroperf-pony.png" width="44" height="44" alt="">coro<em>Perf</em></a>
      <nav aria-label="{text["navigation"]}">
        <a href="{prefix}index.html#issues">{text["issues"]}</a>
        <a href="{prefix}research.html">{text["research"]}</a>
        <a href="{prefix}index.html#method">{text["method"]}</a>
      </nav>
      <div class="languages">{language_links}</div>
    </div>
  </header>
  <main id="main">{body}</main>
  <footer class="site-footer"><div class="wrap"><span>coroPerf · {text["atlas"]}</span><a href="#main">{text["top"]}</a></div></footer>
</body>
</html>
"""
    return "\n".join(line.rstrip() for line in output.splitlines()) + "\n"


def case_title(case, language):
    return case["title_zh"] if language == "zh-CN" else case["title"]


def record_label(record, text):
    return text["record"].format(id=escape(record["id"]))


def frame_rows(frames):
    rows = []
    for frame in frames:
        location = frame["file"]
        if location and frame["line"]:
            location += f':{frame["line"]}'
        source = f'<span>{escape(location)}</span>' if location else ""
        rows.append(f'<li><code>{escape(frame["function"])}</code>{source}</li>')
    return '<ol class="frames">' + "".join(rows) + "</ol>"


def stack(block, title, text, anchor="", extra_class=""):
    identifier = f' id="{anchor}"' if anchor else ""
    kind = block["sample_kind"]
    note = f" · {escape(kind)}" if kind and kind != "unknown" else ""
    identity = ""
    if block.get("instance") is not None:
        label = text["instance"].format(id=escape(block["instance"]))
        identity = f'<span class="record-instance">{label}</span>'
    return (
        f'<section class="stack {extra_class}"{identifier}>'
        f'<div class="stack-head"><h4>{escape(title)}</h4>'
        f'<span>{record_label(block, text)}{note}</span>{identity}</div>'
        f'{frame_rows(block["frames"])}</section>'
    )


def join_marker(source, target, kind, relation, trace_number, number, text, identity_kind=None):
    proof = {
        "creation": "edge_proof",
        "tokio": "task_proof",
        "parent": "parent_proof",
        "async_parent": "async_parent_proof",
    }[relation]
    prefix = f"join-{trace_number}"
    source_id, target_id = escape(source["id"]), escape(target["id"])
    raw_from, raw_to = source_id, target_id
    if kind in {"coroutine_created_by", "goroutine_created_by", "created_by"}:
        raw_from, raw_to = target_id, source_id
    verification = (
        f'{text["identity"]} <code>{escape(kind)}</code>' if relation == "tokio"
        else f'{text["edge"]} <code>{escape(kind)} · {raw_from} → {raw_to}</code>'
    )
    identity_detail = f"<p>{text[identity_kind]}</p>" if identity_kind in (
        "injected-value-token", "runtime-token-generation"
    ) else ""
    return f"""
        <aside class="join-marker" id="{prefix}-point-{number}" aria-label="{text["join_number"].format(n=number)}">
          <div class="join-heading"><span aria-hidden="true">↓</span><a href="#{prefix}-point-{number}">{text["join_number"].format(n=number)}</a><strong>{text[f"join_{relation}"]}</strong></div>
          <p class="join-records"><a href="#{prefix}-record-{source_id}">{record_label(source, text)}</a><span aria-hidden="true">→</span><a href="#{prefix}-record-{target_id}">{record_label(target, text)}</a></p>
          <p>{text[proof]}</p>
          {identity_detail}
          <p class="join-verification">{verification}</p>
        </aside>"""


def trace(join, number, text):
    creation, observation = join["creation"], join["observation"]
    ancestors = join["ancestors"]
    origin_title = text["origin_stack"]
    observation_title = text["execution_observation"]

    blocks = []
    links = []
    path = [*ancestors, creation, observation]
    for index, (parent, child) in enumerate(zip(path, path[1:]), start=1):
        ancestor_link = index <= len(ancestors)
        kind = parent["link_to_child"] if ancestor_link else join["edge"]
        anchor = f'join-{number}-record-{escape(parent["id"])}'
        if ancestor_link:
            title = text["ancestor_stack"]
            relation = "async_parent" if kind == "parent_to_create" else "parent"
        else:
            title = origin_title
            relation = "tokio" if kind == "runtime_task_id" else "creation"
        blocks.append(stack(parent, title, text, anchor))
        identity = join.get("identity_kind") if relation == "creation" else None
        blocks.append(join_marker(parent, child, kind, relation, number, index, text, identity))
        label = text["join_number"].format(n=index)
        links.append(f'<a href="#join-{number}-point-{index}">{label} '
                     f'<code>{escape(parent["id"])} → {escape(child["id"])}</code></a>')
    anchor = f'join-{number}-record-{escape(observation["id"])}'
    blocks.append(stack(observation, observation_title, text, anchor, "observed"))

    physical = {key: value for key, value in observation.items() if key != "instance"}
    return f"""
      <div class="trace-grid">
        <div class="trace-pane stitched">
          <h3>{text["connected"]}</h3>
          <nav class="join-links" aria-label="{text["jump_joins"]}">{"".join(links)}</nav>
          {"".join(blocks)}
        </div>
        <div class="trace-pane">
          <h3>{text["raw_stack"]}</h3>
          {stack(physical, observation_title, text, extra_class="observed")}
          <p class="small trace-note">{text["raw_note"].format(id=escape(physical["id"]))}</p>
        </div>
      </div>"""


def contribution(case, language):
    return case["contribution_zh"] if language == "zh-CN" else case["contribution"]


def case_page(case, language):
    text = COPY[language]
    title = case_title(case, language)
    displays = []
    for index, join in enumerate(case["joins"], start=1):
        note = text["observation_number"].format(id=escape(join["observation"]["id"]))
        content = trace(join, index, text)
        if index == 1:
            displays.append(f'<p class="provenance">{note}</p>{content}')
        else:
            displays.append(f'<details class="extra more-trace"><summary>{note}</summary>{content}</details>')
    content = "".join(displays)

    source = ""
    if case["upstream_reference"] and case["upstream_reference"] != case["url"]:
        source = f'<a href="{escape(case["upstream_reference"])}">{text["followup"]}</a>'
    data = case["findings_zh"] if language == "zh-CN" else case["findings"]
    findings = "".join(
        f'<div><dt>{text[key]}</dt><dd>{escape(data[key])}</dd></div>'
        for key in ("observation", "interpretation", "limits") if data.get(key)
    )
    body = f"""
    <article class="wrap case">
      <a class="back" href="../index.html#issues">← {text["issues"]}</a>
      <header class="case-header">
        <p class="eyebrow">{escape(case["reference"])}</p>
        <h1>{escape(title)}</h1>
        <div class="case-links"><a href="{escape(case["url"])}">{text["upstream"]}</a>{source}</div>
        <dl class="case-status">
          <div><dt>{text["reproduction"]}</dt><dd>{text[case["reproduction"]]}</dd></div>
          <div><dt>{text["diagnosis"]}</dt><dd>{text[case["diagnosis"]]}</dd></div>
        </dl>
      </header>
      <section class="call-stack" aria-labelledby="stack-title" id="call-stack">
        <div class="section-head"><h2 id="stack-title">{text["stack_title"]}</h2></div>
        <div class="join-contribution"><h3>{text["why_join"]}</h3><p>{escape(contribution(case, language))}</p></div>
        <p class="small join-guide">{text["join_guide"]}</p>
        {content}
      </section>
      <section class="findings" aria-labelledby="findings-title">
        <div class="section-head"><h2 id="findings-title">{text["findings"]}</h2></div>
        <dl>{findings}</dl>
      </section>
    </article>"""
    return document(f'evidence/{case["id"]}.html', case["reference"], title, body, language)


def featured_card(case, label, headline):
    return f"""
      <a class="feature" href="evidence/{escape(case["id"])}.html#call-stack">
        <span class="feature-label">{escape(label)}</span>
        <h3>{escape(headline)}</h3>
        <span class="feature-ref">{escape(case["reference"])} <span aria-hidden="true">↗</span></span>
      </a>"""


def table_row(case, text, language):
    scope = escape(case["reproduction"])
    other_language = "en" if language == "zh-CN" else "zh-CN"
    return f"""
      <tr data-scope="{scope}" data-title-alt="{escape(case_title(case, other_language))}">
        <th scope="row"><a href="evidence/{escape(case["id"])}.html"><span>{escape(case["reference"])}</span>{escape(case_title(case, language))}</a></th>
        <td>{escape(contribution(case, language))}</td><td>{text[case["reproduction"]]}</td>
      </tr>"""


def index_page(snapshot, language):
    text = COPY[language]
    cases = snapshot["cases"]
    by_id = {case["id"]: case for case in cases}
    joins = [join for case in cases for join in case["joins"]]
    example = by_id["dotnet--runtime--60764"]["joins"][0]
    top = example["creation"]["frames"][0]["function"]
    leaf = next(frame["function"] for frame in example["observation"]["frames"] if frame["function"] == "A..ctor")
    selected = "".join(featured_card(by_id[identifier], *feature)
                       for identifier, feature in zip(FEATURED, FEATURES[language]))
    stats = [
        (len(cases), "stat_pages"),
        (len(joins), "stat_observations"),
        (sum(len(join["ancestors"]) + 1 for join in joins), "stat_joins"),
    ]
    numbers = "".join(f"<div><dd>{count:,}</dd><dt>{text[key]}</dt></div>" for count, key in stats)
    options = "".join(f'<option value="{key}">{text[key]}</option>' for key in SCOPES)
    rows = "".join(table_row(case, text, language) for case in cases)
    data = "../data/cases.json" if language == "zh-CN" else "data/cases.json"
    body = f"""
    <section class="wrap hero" aria-labelledby="hero-title">
      <div>
        <p class="eyebrow">{text["atlas"]}</p>
        <h1 id="hero-title">{text["hero_a"]}<br>{text["hero_b"]} <em>{text["hero_em"]}</em></h1>
        <p class="hero-copy">{text["hero_copy"]}</p>
        <div class="actions"><a class="button" href="#issues">{text["browse"]}</a><a href="research.html">{text["read_research"]}</a></div>
      </div>
      <figure class="specimen">
        <figcaption><span>{text["specimen"]}</span><a href="evidence/dotnet--runtime--60764.html#join-1-point-1">dotnet/runtime #60764 ↗</a></figcaption>
        <div class="specimen-body">
          <div class="specimen-block"><span>{text["create"]} · {record_label(example["creation"], text)}</span><code>{escape(top)}</code><code>{escape(example["creation"]["frames"][-1]["function"])}</code></div>
          <div class="specimen-edge">↓ &nbsp; {text["specimen_join"]}</div>
          <div class="specimen-block"><span>{text["sample"]} · {record_label(example["observation"], text)}</span><code>Program.Foo [MoveNext]</code><code>{escape(leaf)}</code></div>
        </div>
        <div class="specimen-foot">{text["specimen_foot"]}</div>
      </figure>
    </section>
    <section class="wrap block" aria-labelledby="coverage">
      <div class="section-head"><h2 id="coverage">{text["coverage"]}</h2><span class="small">{text["snapshot"]} · <time>{escape(snapshot["corpus_date"])}</time></span></div>
      <dl class="stats">{numbers}</dl>
    </section>
    <section class="wrap block" aria-labelledby="selected">
      <div class="section-head"><h2 id="selected">{text["selected"]}</h2></div>
      <div class="features">{selected}</div>
    </section>
    <section class="wrap block" id="issues" aria-labelledby="issues-title">
      <div class="section-head"><h2 id="issues-title">{text["issues"]}</h2><a href="{data}" download>{text["download"]}</a></div>
      <p class="section-copy">{text["index_copy"]}</p>
      <div class="filters" hidden>
        <div><label for="query">{text["search"]}</label><input type="search" id="query" placeholder="{text["placeholder"]}"></div>
        <div><label for="scope">{text["reproduction"]}</label><select id="scope"><option value="">{text["any_scope"]}</option>{options}</select></div>
      </div>
      <p class="results-count" id="results-count" role="status" data-format="{text["filtered_result"]}" data-empty="{text["no_result"]}">{text["result"].format(total=len(cases))}</p>
      <div class="table-wrap">
        <table><thead><tr><th scope="col">{text["issue"]}</th><th scope="col">{text["why_join"]}</th><th scope="col">{text["reproduction"]}</th></tr></thead>
        <tbody id="case-rows">{rows}</tbody></table>
      </div>
    </section>
    <section class="method" id="method" aria-labelledby="method-title">
      <div class="wrap">
        <div class="section-head"><h2 id="method-title">{text["read_evidence"]}</h2></div>
        <div class="method-grid">
          <div><h3>{text["read_join"]}</h3><p>{text["method_join"]}</p></div>
          <div><h3>{text["admission"]}</h3><p>{text["method_coverage"]}</p></div>
          <div><h3>{text["reproduction_scope"]}</h3><p>{text["method_reproduction"]}</p></div>
        </div>
      </div>
    </section>"""
    return document("index.html", text["atlas"], text["index_description"], body, language)


def build(snapshot, language):
    text = COPY[language]
    chinese = language == "zh-CN"
    destination = ROOT / "zh-cn" if chinese else ROOT
    evidence = destination / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    generated = set()
    for case in snapshot["cases"]:
        path = evidence / f'{case["id"]}.html'
        path.write_text(case_page(case, language), encoding="utf-8")
        generated.add(path)
    for stale in set(evidence.glob("*.html")) - generated:
        stale.unlink()
    (destination / "index.html").write_text(index_page(snapshot, language), encoding="utf-8")
    fragment = "research.zh-cn.fragment.html" if chinese else "research.fragment.html"
    research = (ROOT / "scripts" / fragment).read_text(encoding="utf-8")
    (destination / "research.html").write_text(
        document("research.html", text["research"], text["research_description"], research, language),
        encoding="utf-8",
    )


if __name__ == "__main__":
    snapshot = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))
    for language in COPY:
        build(snapshot, language)
