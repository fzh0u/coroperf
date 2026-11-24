#!/usr/bin/env python3
"""Build both versions of the static atlas from the public snapshot."""

from collections import Counter
import csv
from datetime import datetime
from html import escape
import json
from pathlib import Path

from copy_text import CASE_LANGUAGES, CONTRIBUTION_KINDS, COPY, FEATURES, ISSUE_KINDS


ROOT = Path(__file__).resolve().parents[1]
FEATURED = (
    "dotnet--runtime--60764",
    "drogonframework--drogon--2331",
    "nodejs--node--50056",
    "grpc--grpc-kotlin--299",
)
SCOPES = ("Full local reproduction", "Component reproduced")
TRACKER_STATES = ("open", "closed", "unconfirmed")


def document(path, title, description, body, language):
    text = COPY[language]
    chinese = language == "zh-CN"
    depth = path.count("/")
    prefix = "../" * depth
    assets = "../" * (depth + chinese)
    alternate = assets + ("" if chinese else "zh-cn/") + path
    alt_language = "en" if chinese else "zh-CN"
    language_names = {"en": "English", "zh-CN": "简体中文"}
    options = []
    for code, name in language_names.items():
        current = code == language
        target = path.rsplit("/", 1)[-1] if current else alternate
        mark = ' aria-current="page"' if current else ""
        options.append(f'<a href="{target}" lang="{code}" hreflang="{code}"{mark}>{name}</a>')
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
      <a class="brand" href="{prefix}index.html"><img class="brand-pony" src="{assets}assets/coroperf-pony-full.png" width="52" height="52" alt="">coro<em>Perf</em></a>
      <nav class="site-nav" aria-label="{text["navigation"]}">
        <a href="{prefix}index.html#issues">{text["issues"]}</a>
        <a href="{prefix}research.html">{text["research"]}</a>
        <a href="{prefix}index.html#method">{text["method"]}</a>
      </nav>
      <nav class="languages" aria-labelledby="language-label">
        <span class="language-label" id="language-label">
          <svg class="globe" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false">
            <circle cx="12" cy="12" r="9.5"/>
            <ellipse cx="12" cy="12" rx="4.5" ry="9.5"/>
            <path d="M3.8 7.25h16.4M2.5 12h19M3.8 16.75h16.4"/>
          </svg>
          {text["language_picker"]}
        </span>
        {"".join(options)}
      </nav>
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
        "cancellation": "cancellation_proof",
        "tokio": "task_proof",
        "parent": "parent_proof",
        "async_parent": "async_parent_proof",
        "batch_input": "batch_input_proof",
        "channel_handoff": "channel_handoff_proof",
        "engine_launch": "engine_launch_proof",
        "tool_registration": "tool_registration_proof",
        "result_dependency": "result_dependency_proof",
        "release_dependency": "release_dependency_proof",
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
        "execution-interval", "injected-value-token", "runtime-token-generation", "weak-identity-object-id",
        "actor-entry-argument-dataflow", "scheduled-handle-running-at-task-creation",
        "actual-rpc-handler-and-submitted-work-item", "active-work-item-object",
        "live-child-node", "same-dequeued-request-in-work-item", "jdi-fiber-receiver", "dart-callback-object",
        "go-opener-signal", "dotnet-task-fault-object", "buffered-result-object", "stored-exception-object-handoff",
        "dotnet-chat-iterator-and-message", "langchain4j-stream-handler-and-exception",
        "taskgroup-internal-cancel", "taskgroup-outer-cancel", "same-frozen-result-object", "captured-goroutine-id",
        "asyncio-live-task-at-snapshot", "asyncio-task-and-stream-frame",
        "rust-engine-launch-token", "reactor-scheduled-tool-callback",
        "tokio-join-handle-and-running-task", "same-dynamo-endpoint-notifier",
        "ray-batcher-task-and-queue-object", "ray-batcher-reader-created-by-request-task",
        "ray-cache-loader-task-object", "ray-model-loader-created-by-request-task",
        "ray-router-reporter-live-task", "ray-router-cross-thread-metrics-callback",
        "sglang-detokenizer-ipc-row-and-request-task", "sglang-tokenizer-internal-request-id",
        "sglang-tokenizer-http-request-id", "sglang-stream-task-and-output-queue",
        "dynamo-stripped-serializer-task-and-request",
        "ollama-embedding-goroutine-and-request-row",
        "trtllm-live-batch-worker-and-record", "trtllm-batch-task-and-worker-record",
        "same-aiohttp-protocol-and-benchmark-task",
        "polars-stopped-task-and-source-token",
    ) else ""
    return f"""
        <aside class="join-marker" id="{prefix}-point-{number}" aria-label="{text["join_number"].format(n=number)}">
        <div class="join-heading"><span aria-hidden="true">↑</span><a href="#{prefix}-point-{number}">{text["join_number"].format(n=number)}</a><strong>{text[f"join_{relation}"]}</strong></div>
          <p class="join-records"><a href="#{prefix}-record-{source_id}">{record_label(source, text)}</a><span aria-hidden="true">→</span><a href="#{prefix}-record-{target_id}">{record_label(target, text)}</a></p>
          <p>{text[proof]}</p>
          {identity_detail}
          <p class="join-verification">{verification}</p>
        </aside>"""


def trace(join, number, text):
    creation, observation = join["creation"], join["observation"]
    ancestors = join["ancestors"]
    batch_submission = ancestors and ancestors[-1].get("link_evidence") == "same-batch-request-future"
    origin_title = text["batch_submission_stack" if batch_submission else "origin_stack"]
    task_snapshot = observation["sample_kind"] == "task_snapshot"
    observation_title = text["task_snapshot" if task_snapshot else "execution_observation"]
    raw_title = text["raw_task_snapshot" if task_snapshot else "raw_stack"]

    anchor = f'join-{number}-record-{escape(observation["id"])}'
    blocks = [stack(observation, observation_title, text, anchor, "observed")]
    links = []
    path = [*ancestors, creation, observation]
    for index in range(len(path) - 1, 0, -1):
        parent, child = path[index - 1:index + 1]
        ancestor_link = index <= len(ancestors)
        kind = parent["link_to_child"] if ancestor_link else join["edge"]
        identity = parent.get("link_evidence") if ancestor_link else join.get("identity_kind")
        anchor = f'join-{number}-record-{escape(parent["id"])}'
        if ancestor_link and identity == "same-singleflight-call-result-channel":
            relation = "result_dependency"
            title = text["result_producer_stack"]
        elif ancestor_link and identity == "same-pool-holder-release-future":
            relation = "release_dependency"
            title = text["acquiring_task_stack"]
        elif ancestor_link and identity == "same-batch-request-future":
            relation = "batch_input"
            title = text["batch_request_stack"]
        elif ancestor_link and identity == "rust-engine-thread-launch":
            relation = "engine_launch"
            title = text["application_launch_stack"]
        elif ancestor_link and identity == "same-reactor-tool-batch":
            relation = "tool_registration"
            title = text["application_launch_stack"]
        elif ancestor_link:
            relation = "async_parent" if kind == "parent_to_create" else "parent"
            title = text["async_ancestor_stack" if relation == "async_parent" else "ancestor_stack"]
        elif kind == "cancel_request_to_observation":
            relation = "cancellation"
            title = text["cancellation_stack"]
        elif identity == "go-channel-work-item":
            relation = "channel_handoff"
            title = text["channel_submission_stack"]
        else:
            title = origin_title
            relation = "tokio" if kind == "runtime_task_id" else "creation"
        if relation == "creation" and join.get("interval_attribution") and identity not in {"live-child-node", "go-opener-signal"}:
            identity = "execution-interval"
        blocks.append(join_marker(parent, child, kind, relation, number, index, text, identity))
        blocks.append(stack(parent, title, text, anchor))
        label = text["join_number"].format(n=index)
        links.append(f'<a href="#join-{number}-point-{index}">{label} '
                     f'<code>{escape(child["id"])} → {escape(parent["id"])}</code></a>')

    original = {key: value for key, value in observation.items() if key != "instance"}
    return f"""
      <div class="trace-grid">
        <div class="trace-pane">
          <h3>{raw_title}</h3>
          {stack(original, observation_title, text, extra_class="observed")}
          <p class="small trace-note">{text["raw_note"].format(id=escape(original["id"]))}</p>
        </div>
        <div class="trace-pane stitched">
          <h3>{text["connected"]}</h3>
          <nav class="join-links" aria-label="{text["jump_joins"]}">{"".join(links)}</nav>
          {"".join(blocks)}
        </div>
      </div>"""


def contribution(case, language):
    return case["contribution_zh"] if language == "zh-CN" else case["contribution"]


def fix_description(case, text, label_prefix):
    state = (case["fix"] or {}).get("state", "unconfirmed")
    label = text[label_prefix + state]
    pull = case.get("fix_pr_status")
    if pull and (state, pull) != ("merged", "merged"):
        label += " · " + text["pull_" + pull]
    return label


def source_token_table(case, text):
    transfers = case.get("observed_source_token_transfers")
    if not transfers:
        return ""
    links = {
        observation["id"]: f'<a href="#join-{index}-record-{escape(observation["id"])}">{record_label(observation, text)}</a>'
        for index, join in enumerate(case["joins"], start=1)
        for observation in (join["observation"],)
    }
    rows = "".join(
        f'<tr><th scope="row">{text[transfer["stage"]]}</th>'
        f'<td>{links[transfer["from"]]}</td><td>{links[transfer["to"]]}</td></tr>'
        for transfer in transfers
    )
    return f"""
      <section id="source-token-transfers" aria-labelledby="stop-title">
        <div class="section-head"><h2 id="stop-title">{text["source_token_transfers"]}</h2></div>
        <div class="table-wrap summary-table">
          <table aria-labelledby="stop-title">
            <thead><tr><th scope="col">{text["source_token_stage"]}</th><th scope="col">{text["source_token_write"]}</th><th scope="col">{text["source_token_read"]}</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
      </section>"""


def case_page(case, language):
    text = COPY[language]
    title = case_title(case, language)
    displays = []
    for index, join in enumerate(case["joins"], start=1):
        observation = join["observation"]
        note = text["observation_number"].format(id=escape(observation["id"]))
        if duration := observation.get("wait_duration_ns"):
            note += " · " + text["suspended_duration"].format(ms=f"{duration / 1_000_000:.1f}")
        content = trace(join, index, text)
        if index == 1:
            displays.append(f'<p class="provenance">{note}</p>{content}')
        else:
            displays.append(f'<details class="extra more-trace"><summary>{note}</summary>{content}</details>')
    content = "".join(displays)

    source = ""
    fix = case["fix"] or {}
    if case["upstream_reference"] and case["upstream_reference"] not in {case["url"], fix.get("url")}:
        source = f'<a href="{escape(case["upstream_reference"])}">{text["followup"]}</a>'
    fix_label = fix_description(case, text, "fix_")
    if fix.get("url"):
        fix_label = f'<a href="{escape(fix["url"])}">{fix_label} ↗</a>'
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
          <div><dt>{text["contribution_kind"]}</dt><dd>{text[case["contribution_kind"]]}</dd></div>
          <div><dt>{text["issue_kind"]}</dt><dd>{text[case["kind"]]}</dd></div>
          <div><dt>{text["tracker_status"]}</dt><dd>{text["tracker_" + case["tracker_status"]]}</dd></div>
          <div><dt>{text["fix_status"]}</dt><dd>{fix_label}</dd></div>
          <div><dt>{text["case_language"]}</dt><dd>{escape(case["language"])}</dd></div>
          <div><dt>{text["reproduction"]}</dt><dd>{text[case["reproduction"]]}</dd></div>
          <div><dt>{text["diagnosis"]}</dt><dd>{text[case["diagnosis"]]}</dd></div>
        </dl>
      </header>
      <section class="call-stack" aria-labelledby="stack-title" id="call-stack">
        <div class="section-head"><h2 id="stack-title">{text["stack_title"]}</h2></div>
        <div class="join-contribution"><h3>{text["why_join"]}</h3><p>{escape(contribution(case, language))}</p></div>
        <p class="small join-guide">{text["join_guide"]}</p>
        {content}
      </section>{source_token_table(case, text)}
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


def table_status(case, text):
    state = case["tracker_status"]
    fix = case["fix"] or {}
    fix_text = fix_description(case, text, "fix_short_")
    if fix.get("url"):
        fix_label = f'<a class="fix-label" href="{escape(fix["url"])}">{fix_text}</a>'
    else:
        fix_label = f'<span class="fix-label">{fix_text}</span>'
    return f'<td class="row-status"><a class="state-pill state-{state}" href="{escape(case["url"])}">{text["tracker_" + state]}</a>{fix_label}</td>'


def table_row(case, text, language):
    category = case["contribution_kind"]
    state = case["tracker_status"]
    other_language = "en" if language == "zh-CN" else "zh-CN"
    return f"""
      <tr class="issue-row" data-scope="{escape(case["reproduction"])}" data-kind="{case["kind"]}" data-contribution="{category}" data-tracker-status="{state}" data-title-alt="{escape(case_title(case, other_language))}">
        <th scope="row"><a href="evidence/{escape(case["id"])}.html"><span>{escape(case["reference"])}</span>{escape(case_title(case, language))}</a></th>
        <td class="row-contribution"><strong>{text[category]}</strong><small class="case-kind">{text[case["kind"]]}</small></td>
        {table_status(case, text)}
      </tr>"""


def table_group(name, cases, text, language):
    heading = text["language_issues"].format(count=len(cases))
    ordered = sorted(cases, key=lambda case: TRACKER_STATES.index(case["tracker_status"]))
    rows = "".join(table_row(case, text, language) for case in ordered)
    return f"""
    <tbody class="language-group" data-language="{escape(name)}">
      <tr class="language-heading"><th colspan="3" scope="rowgroup">{escape(name)}
        <span data-language-count data-format="{text["language_issues"]}">{heading}</span>
      </th></tr>{rows}
    </tbody>"""


def outcomes(cases, text, csv_path):
    tags = Counter(case["contribution_kind"] for case in cases)
    direct = Counter(case["contribution_kind"] for case in cases if case["diagnosis"] == "Direct")
    classified = "".join(
        f'<tr><th scope="row"><a href="research.html#{key}">{text[key]}</a><small>{text[key + "_detail"]}</small></th>'
        f'<td>{tags[key]}</td><td>{direct[key]}</td></tr>' for key in CONTRIBUTION_KINDS
    )
    reported = Counter(case["kind"] for case in cases)
    by_scope = Counter((case["reproduction"], case["diagnosis"]) for case in cases)
    kinds = "".join(
        f'<tr><th scope="row">{text[kind]}<small>{text[kind + "_detail"]}</small></th>'
        f'<td>{reported[kind]}</td></tr>' for kind in ISSUE_KINDS
    )
    evidence = "".join(
        f'<tr><th scope="row">{text[scope]}</th><td>{by_scope[scope, "Direct"]}</td>'
        f'<td>{by_scope[scope, "Inferred from controls"]}</td></tr>' for scope in SCOPES
    )
    return f"""
    <section class="wrap block" id="outcomes" aria-labelledby="outcomes-title">
      <div class="section-head"><h2 id="outcomes-title">{text["outcomes"]}</h2><a href="{csv_path}" download>{text["case_csv"]}</a></div>
      <p class="section-copy">{text["outcomes_scope"]}</p>
      <div class="table-wrap summary-table">
        <table aria-labelledby="outcomes-title"><thead><tr><th scope="col">{text["contribution_kind"]}</th><th scope="col">{text["case_count"]}</th><th scope="col">{text["direct_diagnosis"]}</th></tr></thead>
        <tbody>{classified}</tbody></table>
      </div>
      <details class="extra">
        <summary id="reported-breakdown">{text["reported_breakdown"]}</summary>
        <div class="table-wrap summary-table">
          <table aria-labelledby="reported-breakdown"><thead><tr><th scope="col">{text["issue_kind"]}</th><th scope="col">{text["case_count"]}</th></tr></thead>
          <tbody>{kinds}</tbody></table>
        </div>
      </details>
      <details class="extra">
        <summary id="evidence-matrix">{text["evidence_matrix"]}</summary>
        <p class="section-copy">{text["evidence_matrix_help"]}</p>
        <div class="table-wrap summary-table">
          <table aria-labelledby="evidence-matrix"><thead><tr><th scope="col">{text["reproduction"]}</th><th scope="col">{text["direct_diagnosis"]}</th><th scope="col">{text["Inferred from controls"]}</th></tr></thead>
          <tbody>{evidence}</tbody></table>
        </div>
      </details>
    </section>"""


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
    groups = {name: [] for name in CASE_LANGUAGES}
    for case in cases:
        groups[case["language"]].append(case)
    groups = {name: rows for name, rows in groups.items() if rows}
    stats = [
        (len(cases), "stat_pages"),
        (len(joins), "stat_observations"),
        (sum(len(join["ancestors"]) + 1 for join in joins), "stat_joins"),
        (len(groups), "language_coverage"),
    ]
    numbers = "".join(f"<div><dd>{count:,}</dd><dt>{text[key]}</dt></div>" for count, key in stats)
    language_options = "".join(f'<option value="{escape(name)}">{escape(name)} ({len(rows)})</option>'
                               for name, rows in groups.items())
    options = "".join(f'<option value="{key}">{text[key]}</option>' for key in SCOPES)
    issue_types = "".join(f'<option value="{key}">{text[key]}</option>' for key in ISSUE_KINDS)
    contribution_types = "".join(f'<option value="{key}">{text[key]}</option>' for key in CONTRIBUTION_KINDS)
    tracker_states = "".join(f'<option value="{state}">{text["tracker_" + state]}</option>' for state in TRACKER_STATES)
    tracker_counts = Counter(case["tracker_status"] for case in cases)
    tracker_summary = text["tracker_summary"].format(opened=tracker_counts["open"], closed=tracker_counts["closed"])
    if tracker_counts["unconfirmed"]:
        tracker_summary += " · " + text["tracker_unconfirmed_count"].format(count=tracker_counts["unconfirmed"])
    checked_at = snapshot["tracker_checked_at"]
    checked = text["tracker_checked"].format(time=datetime.fromisoformat(checked_at).strftime("%Y-%m-%d %H:%M UTC"))
    rows = "".join(table_group(name, items, text, language) for name, items in groups.items())
    data = "../data/" if language == "zh-CN" else "data/"
    followup_link = ""
    if snapshot.get("deferred_followups"):
        followup_link = f'<a href="research.html#deferred-followups">{text["deferred_followups"]}</a>'
    body = f"""
    <section class="wrap hero" aria-labelledby="hero-title">
      <div>
        <p class="eyebrow">{text["atlas"]}</p>
        <h1 id="hero-title">{text["hero_a"]}<br>{text["hero_b"]} <em>{text["hero_em"]}</em></h1>
        <p class="hero-copy">{text["hero_copy"]}</p>
        <div class="actions"><a class="button" href="#issues">{text["browse"]}</a><a href="#outcomes">{text["outcomes"]}</a></div>
      </div>
      <figure class="specimen">
        <figcaption><span>{text["specimen"]}</span><a href="evidence/dotnet--runtime--60764.html#join-1-point-1">dotnet/runtime #60764 ↗</a></figcaption>
        <div class="specimen-body">
          <div class="specimen-block"><span>{text["sample"]} · {record_label(example["observation"], text)}</span><code>Program.Foo [MoveNext]</code><code>{escape(leaf)}</code></div>
          <div class="specimen-edge">↑ &nbsp; {text["specimen_join"]}</div>
          <div class="specimen-block"><span>{text["create"]} · {record_label(example["creation"], text)}</span><code>{escape(top)}</code><code>{escape(example["creation"]["frames"][-1]["function"])}</code></div>
        </div>
        <div class="specimen-foot">{text["specimen_foot"]}</div>
      </figure>
    </section>
    <section class="wrap block" aria-labelledby="coverage">
      <div class="section-head"><h2 id="coverage">{text["coverage"]}</h2><span class="small">{text["snapshot"]} · <time>{escape(snapshot["corpus_date"])}</time></span></div>
      <dl class="stats">{numbers}</dl>
    </section>
    <section class="wrap block" id="issues" aria-labelledby="issues-title">
      <div class="section-head"><h2 id="issues-title">{text["issues"]}</h2><a href="{data}cases.json" download>{text["download"]}</a></div>
      <p class="section-copy">{text["index_copy"]}</p>
      <p class="tracker-summary" id="upstream-status"><strong>{tracker_summary}</strong><time datetime="{escape(checked_at)}">{checked}</time><a href="{data}upstream-status.json" download>{text["tracker_data"]}</a>{followup_link}</p>
      <div class="filters" hidden>
        <div><label for="query">{text["search"]}</label><input type="search" id="query" placeholder="{text["placeholder"]}"></div>
        <div><label for="case-language">{text["case_language"]}</label><select id="case-language"><option value="">{text["any_case_language"]}</option>{language_options}</select></div>
        <div><label for="tracker-status">{text["tracker_status"]}</label><select id="tracker-status"><option value="">{text["any_tracker_status"]}</option>{tracker_states}</select></div>
        <div><label for="contribution">{text["contribution_kind"]}</label><select id="contribution"><option value="">{text["any_contribution"]}</option>{contribution_types}</select></div>
        <div><label for="kind">{text["issue_kind"]}</label><select id="kind"><option value="">{text["any_issue_kind"]}</option>{issue_types}</select></div>
        <div><label for="scope">{text["reproduction"]}</label><select id="scope"><option value="">{text["any_scope"]}</option>{options}</select></div>
      </div>
      <p class="results-count" id="results-count" role="status" data-format="{text["filtered_result"]}" data-empty="{text["no_result"]}" data-all="{text["result"].format(total=len(cases))}">{text["result"].format(total=len(cases))}</p>
      <div class="table-wrap">
        <table class="issue-table" id="case-rows" aria-labelledby="issues-title"><thead><tr><th scope="col">{text["issue"]}</th><th scope="col">{text["contribution_kind"]}</th><th scope="col" class="table-state">{text["tracker_status"]}<small>{text["fix_status"]}</small></th></tr></thead>
        {rows}</table>
      </div>
    </section>
    {outcomes(cases, text, data + "case-classification.csv")}
    <section class="wrap block" aria-labelledby="selected">
      <div class="section-head"><h2 id="selected">{text["selected"]}</h2></div>
      <div class="features">{selected}</div>
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


def research_case(case, note, language):
    if note:
        anchor = note["anchor"]
        title = note[language]["title"]
        summary = note[language]["summary"]
    else:
        anchor = "call-stack"
        title = case_title(case, language)
        summary = f'<p>{escape(contribution(case, language))}</p>'
    return f"""
      <tr>
        <th scope="row"><a href="evidence/{escape(case["id"])}.html#{escape(anchor)}"><span>{escape(case["reference"])}</span>{escape(title)}</a></th>
        <td>{summary}</td>
        {table_status(case, COPY[language])}
      </tr>"""


def deferred_section(followups, language):
    if not followups:
        return ""
    text = COPY[language]
    rows = "".join(f"""
          <tr id="followup-{escape(row["id"])}">
            <th scope="row">
              <a href="{escape(row["url"])}"><span>{escape(row["reference"])}</span>{escape(case_title(row, language))}</a>
              <small>{text["safety_review_hold"]}</small>
            </th>
            {table_status(row, text)}
          </tr>""" for row in followups)
    return f"""
    <section class="block" id="deferred-followups" aria-labelledby="deferred-title">
      <div class="section-head"><h2 id="deferred-title">{text["deferred_followups"]}</h2></div>
      <p class="section-copy">{text["deferred_copy"]}</p>
      <div class="table-wrap summary-table">
        <table aria-labelledby="deferred-title">
          <thead><tr><th scope="col">{text["issue"]}</th><th scope="col">{text["tracker_status"]}<small>{text["fix_status"]}</small></th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>"""


def research_page(cases, notes, language, followups):
    text = COPY[language]
    groups = {category: [] for category in CONTRIBUTION_KINDS}
    for case in cases:
        groups[case["contribution_kind"]].append(case)
    categories = []
    sections = []
    for category, group in groups.items():
        label = text[category]
        count = text["language_issues"].format(count=len(group))
        categories.append(f'<li><a href="#{category}">{label} <span>({len(group)})</span></a></li>')
        rows = "".join(research_case(case, notes.get(case["id"]), language) for case in group)
        heading = "assembly" if category == "cost_attribution" else f"{category}-title"
        sections.append(f"""
    <section class="block" id="{category}" aria-labelledby="{heading}">
      <div class="section-head"><h2 id="{heading}">{label}</h2><span class="case-kind">{count}</span></div>
      <p class="section-copy">{text[category + "_detail"]}</p>
      <div class="table-wrap research-table">
        <table aria-labelledby="{heading}">
          <thead><tr><th scope="col">{text["issue"]}</th><th scope="col">{text["interpretation"]}</th><th scope="col">{text["tracker_status"]}<small>{text["fix_status"]}</small></th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>""")
    body = f"""
    <article class="wrap research">
      <a class="back" href="index.html#issues">← {text["issues"]}</a>
      <header id="identity">
        <h1>{text["research_title"]}</h1>
        <p class="section-copy">{text["research_intro"]}</p>
      </header>
      <nav class="research-categories" aria-label="{text["contribution_kind"]}"><ul>{"".join(categories)}</ul></nav>
      {deferred_section(followups, language)}
      {"".join(sections)}
    </article>"""
    return document("research.html", text["research"], text["research_description"], body, language)


def build(snapshot, language, notes):
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
    research = research_page(snapshot["cases"], notes, language, snapshot.get("deferred_followups", []))
    (destination / "research.html").write_text(research, encoding="utf-8")


def write_classification(snapshot):
    with (ROOT / "data" / "case-classification.csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("issue", "issue_url", "language", "contribution_key", "contribution_en",
                         "contribution_zh", "reported_issue_type", "reproduction", "diagnosis",
                         "github_status", "fix_evidence", "fix_url", "fix_pr_status", "status_checked_at"))
        for case in snapshot["cases"]:
            tag = case["contribution_kind"]
            fix = case["fix"] or {}
            writer.writerow((case["reference"], case["url"], case["language"], tag, COPY["en"][tag],
                             COPY["zh-CN"][tag], case["kind"], case["reproduction"], case["diagnosis"],
                             case["tracker_status"], fix.get("state", "unconfirmed"), fix.get("url", ""),
                             case.get("fix_pr_status", ""), snapshot["tracker_checked_at"]))


if __name__ == "__main__":
    snapshot = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))
    tracker = json.loads((ROOT / "data" / "upstream-status.json").read_text(encoding="utf-8"))
    snapshot["tracker_checked_at"] = tracker["checked_at"]
    for case in snapshot["cases"] + snapshot.get("deferred_followups", []):
        entry = tracker["issues"].get(case["id"], {})
        state = entry.get("status")
        case["tracker_status"] = state if entry.get("url") == case["url"] and state in TRACKER_STATES else "unconfirmed"
        fix_url = (case["fix"] or {}).get("url")
        pull = tracker.get("pull_requests", {}).get(fix_url)
        if pull in {"open", "closed", "merged", "unconfirmed"}:
            case["fix_pr_status"] = pull
    write_classification(snapshot)
    notes = json.loads((ROOT / "scripts" / "research-notes.json").read_text(encoding="utf-8"))
    for language in COPY:
        build(snapshot, language, notes)
