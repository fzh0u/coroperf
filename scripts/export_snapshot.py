#!/usr/bin/env python3
"""Export a public snapshot from the CoroPerf research workspace."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parents[1]
BASE_EDGES = {"base_to_sample", "create_base_to_sample_stack", "base_to_sample_stack"}
PARENT_EDGES = {"coroutine_created_by", "goroutine_created_by", "created_by", "parent_to_create"}
CREATE = {"create", "creation"}
OBSERVATION = {"sample", "cpu_sample", "diagnostic_stacktrace", "task_snapshot"}
DEFERRED_IDS = {"vllm-project--vllm--30343"}
REVIEW = re.compile(
    r"use.after.free|\bcve[- ]\d|heap corruption|memory corruption|security vulnerab|"
    r"invalid free|double free|buffer overflow|stack smashing|authentication bypass|"
    r"remote code execution|out.of.bounds (read|write)|dangling pointer",
    re.IGNORECASE,
)
INTERNAL_PATH = re.compile(
    r"(?:/data\d+/|/home/|/tmp/|/Users/|[A-Za-z]:\\|(?:\./)?(?:perf-out|research|\.tools)/)"
    r"[^\s<>\]'\"()]+"
)
ADDRESS = re.compile(r"\b0x[0-9a-f]{10,}\b", re.IGNORECASE)
TRACKERS = {"github.com", "code.djangoproject.com", "issues.apache.org", "sqlite.org"}
CHINESE_HEADLINES = {
    "dotnet--runtime--60764": "Foo 恢复后，物理调用栈里找不到 Main",
    "drogonframework--drogon--2331": "Drogon 在数据库事件循环上执行同步 SQL，导致请求超时",
    "tokio-rs--tokio--6315": "Tokio 的 LIFO 槽位保留了一个没有及时轮询的任务",
}


def safe_text(value):
    cleaned = INTERNAL_PATH.sub(lambda m: m.group().replace("\\", "/").rsplit("/", 1)[-1], str(value))
    return ADDRESS.sub("[address]", cleaned)


def read_json(filename):
    return json.loads(filename.read_text(encoding="utf-8"))


def event(segment):
    return segment.get("capture_reason") or segment.get("event")


def frame_list(segment, leaf_first=True):
    frames = []
    for item in segment.get("frames", []):
        frame = item if isinstance(item, dict) else {"function": item}
        function = frame.get("function") or frame.get("name") or frame.get("symbol") or "<unknown>"
        file = str(frame.get("file") or "").replace("\\", "/").rsplit("/", 1)[-1]
        line = str(frame.get("line") or "")
        frames.append({
            "function": safe_text(function),
            "file": safe_text(file),
            "line": int(line) if line.isdigit() and int(line) > 0 else None,
        })
    return frames[::-1] if leaf_first else frames


def block(segment, leaf_first):
    return {
        "id": str(segment["id"]),
        "event": event(segment),
        "sample_kind": segment.get("sample_kind"),
        "frames": frame_list(segment, leaf_first),
    }


def instance_labels(segments):
    labels = {}
    for identifier, segment in segments.items():
        identity = segment.get("coroutine_id")
        if identity not in (None, "", "?", "unknown"):
            labels.setdefault(identity, identifier)
    return labels


def framework_root(segment):
    return segment.get("identity_domain") == "react-render-owner"


def raw_parent_edges(graph, segments):
    parents = defaultdict(set)
    for edge in graph["edges"]:
        kind = edge["kind"]
        if kind not in PARENT_EDGES:
            continue
        source, target = str(edge["from"]), str(edge["to"])
        child, parent = (target, source) if kind == "parent_to_create" else (source, target)
        a, b = segments[child], segments[parent]
        if event(a) not in CREATE or event(b) not in CREATE:
            continue
        if not a.get("coroutine_id") or not b.get("coroutine_id") or a["coroutine_id"] == b["coroutine_id"]:
            continue
        if framework_root(a) and edge.get("evidence") != "actual-ReactComponentInfo-owner-object":
            continue
        parents[child].add((parent, kind))
    return parents


def ancestry(start, segments, parents, leaf_first):
    chain = []
    seen = {start}
    current = start
    while options := parents.get(current):
        if len({parent for parent, _ in options}) != 1:
            break
        parent, kind = min(options)
        if parent in seen or not segments[parent].get("frames"):
            break
        entry = block(segments[parent], leaf_first)
        entry["link_to_child"] = kind
        chain.append(entry)
        current = parent
        seen.add(parent)
    return chain[::-1]


def audit_task_id_pair(followup, segments):
    if followup.get("link") != "runtime_task_id":
        return None
    source, target = str(followup["create"]), str(followup["sample"])
    if source not in segments or target not in segments:
        return None
    a, b = segments[source], segments[target]
    if not a.get("process_id") or a["process_id"] != b.get("process_id"):
        return None
    identity = followup["instance"]
    if a.get("coroutine_id") != identity or b.get("coroutine_id") != identity:
        return None
    creates = [s for s in segments.values() if event(s) in CREATE
               and s.get("process_id") == a["process_id"] and s.get("coroutine_id") == identity]
    if len(creates) == 1 and str(creates[0]["id"]) == source:
        return source, target
    return None


def evidence_from_graph(graph, ledger, public, required_pairs):
    segments = {str(s["id"]): s for s in graph["segments"]}
    leaf_first = graph.get("frame_order") != "root_to_leaf"
    parents = raw_parent_edges(graph, segments)
    origin = public.get("origin") or {}
    candidates = defaultdict(dict)
    for edge in graph["edges"]:
        if edge["kind"] not in BASE_EDGES:
            continue
        source, target = str(edge["from"]), str(edge["to"])
        candidates[target][source] = edge["kind"]
    followup = origin.get("followup") or {}
    if followup.get("graph") == ledger.get("graph") and (task_pair := audit_task_id_pair(followup, segments)):
        source, target = task_pair
        candidates[target].setdefault(source, "runtime_task_id")

    joins = []
    labels = instance_labels(segments)
    producer = graph.get("producer", {})
    for source, target in required_pairs:
        sources = candidates[target]
        a, b = segments[source], segments[target]
        identity = a.get("coroutine_id")
        if (set(sources) != {source} or event(a) not in CREATE or event(b) not in OBSERVATION
                or not a.get("frames") or not b.get("frames") or identity not in labels
                or identity != b.get("coroutine_id") or framework_root(a)):
            raise ValueError(f"{ledger['id']}: no verified coroutine join from {source} to {target}")
        creation, observation = block(a, leaf_first), block(b, leaf_first)
        ancestors = ancestry(source, segments, parents, leaf_first)
        for record in [*ancestors, creation, observation]:
            record["instance"] = labels[segments[record["id"]]["coroutine_id"]]
        joins.append({
            "creation": creation,
            "observation": observation,
            "edge": sources[source],
            "ancestors": ancestors,
            "identity_kind": producer.get("identity_kind"),
        })
    return joins


def chinese_case(row):
    findings = {
        "observation": safe_text(row["symptom_zh"]),
        "interpretation": safe_text(row["reasoning_zh"]),
        "limits": safe_text(row["limits_zh"]),
    }
    title = CHINESE_HEADLINES.get(row["id"])
    if not title:
        sentences = re.split(r"[。！？\n]", findings["observation"])
        title = next((sentence.strip() for sentence in sentences if len(sentence.strip()) >= 12),
                     sentences[0].strip())
    return title, findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, help="Root of the original CoroPerf research workspace")
    parser.add_argument("--output", type=Path, default=HERE / "data" / "cases.json")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    public = workspace / "web" / "coroperf-results" / "public"
    results = (public / "results.js").read_text(encoding="utf-8").split("=", 1)[1].strip().removesuffix(";")
    index = json.loads(results)
    index_by_id = {row["id"]: row for row in index["cases"]}
    focus = read_json(HERE / "data" / "focus.json")
    ledger = read_json(workspace / "perf-out" / "systems-repro" / "ledger.json")
    by_id = {row["id"]: row for row in ledger["cases"]}
    deferred = read_json(workspace / "research" / "deferred-security-issues.json")["cases"]
    deferred_ids = DEFERRED_IDS | {row["id"] for row in deferred}
    deferred_urls = {row["issue_url"] for row in deferred}

    cases = []
    for identifier, review in focus.items():
        item = index_by_id[identifier]
        if identifier in deferred_ids or item["url"] in deferred_urls:
            raise ValueError(f"{identifier}: deferred from publication")
        evidence = read_json(public / "evidence" / f"{identifier}.json")
        findings = {key: safe_text(value) for key, value in evidence["findings"].items()}
        if REVIEW.search(" ".join([item["title"], *findings.values()])):
            raise ValueError(f"{identifier}: review required before publication")
        row = by_id[identifier]
        title_zh, findings_zh = chinese_case(row)
        graph = read_json(workspace / row["graph"])
        joins = evidence_from_graph(graph, row, evidence, review["records"])
        if not joins:
            raise ValueError(f"{identifier}: at least one verified join is required")
        upstream_reference = evidence.get("upstream_reference")
        if upstream_reference and not any(upstream_reference.startswith(f"https://{host}/") for host in TRACKERS):
            upstream_reference = None
        cases.append({
            "id": identifier,
            "reference": f'{item["repo"]} #{item["issue"]}',
            "title": safe_text(item["title"]),
            "title_zh": title_zh,
            "url": item["url"],
            "upstream_reference": upstream_reference,
            "reproduction": evidence["reproduction"],
            "diagnosis": evidence["diagnosis"],
            "findings": findings,
            "findings_zh": findings_zh,
            "joins": joins,
            "contribution": review["en"],
            "contribution_zh": review["zh"],
        })
    snapshot = {"corpus_date": index["date"], "cases": cases}
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
