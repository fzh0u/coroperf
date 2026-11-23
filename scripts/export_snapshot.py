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
SUPPLEMENTAL_GRAPHS = {
    "ktorio--ktor--1267": (
        "perf-out/systems-repro/processing/prior-01/ktorio--ktor--1267/kotlin-analysis/graph.json",
        "Supplemental Kotlin Job capture",
    ),
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
        entry["component"] = segments[parent].get("component_name")
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


def evidence_from_graph(graph, ledger, public):
    segments = {str(s["id"]): s for s in graph["segments"]}
    leaf_first = graph.get("frame_order") != "root_to_leaf"
    parents = raw_parent_edges(graph, segments)
    raw_witness = [str(i) for i in ledger.get("witness_segment_ids") or []]
    witnesses = {identifier: index for index, identifier in enumerate(raw_witness)}
    origin = public.get("origin") or {}
    historical_pair = (str(origin.get("create")), str(origin.get("sample")))
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

    pairs = []
    for target, sources in candidates.items():
        if len(sources) != 1:
            continue
        source, kind = next(iter(sources.items()))
        a, b = segments[source], segments[target]
        if event(a) not in CREATE or event(b) not in OBSERVATION or not a.get("frames") or not b.get("frames"):
            continue
        identity = a.get("coroutine_id")
        if identity in (None, "", "?", "unknown") or identity != b.get("coroutine_id"):
            continue
        historical = (source, target) == historical_pair
        rank = (not historical, target not in witnesses, witnesses.get(target, len(witnesses)),
                source not in witnesses, int(target) if target.isdecimal() else float("inf"), target)
        pairs.append((rank, source, target, kind, identity, historical))
    pairs.sort()

    joins = []
    seen_samples = set()
    for _, source, target, kind, identity, historical in pairs:
        creation, sample = block(segments[source], leaf_first), block(segments[target], leaf_first)
        signature = (identity, sample["sample_kind"], tuple(f["function"] for f in sample["frames"]))
        if signature in seen_samples:
            continue
        seen_samples.add(signature)
        creation["component"] = segments[source].get("component_name")
        ownership = framework_root(segments[source])
        joins.append({
            "creation": creation, "observation": sample, "edge": kind,
            "ancestors": ancestry(source, segments, parents, leaf_first),
            "relation": "renderer" if ownership else "creation",
            "selected_witness": target in witnesses,
            "historical_pair": historical,
        })
        if len(joins) == 3:
            break

    physical = []
    shown = {j["observation"]["id"] for j in joins} | {j["creation"]["id"] for j in joins}
    for exported in public.get("segments") or []:
        identifier = str(exported["id"])
        if identifier in shown or not exported.get("frames"):
            continue
        native = segments.get(identifier)
        physical.append(block(native if native and native.get("frames") else exported,
                              leaf_first if native and native.get("frames") else True))
        if len(physical) == 4:
            break
    if not joins and not physical:
        for segment in segments.values():
            if event(segment) in OBSERVATION and segment.get("frames"):
                physical.append(block(segment, leaf_first))
                if len(physical) == 4:
                    break
    return joins, physical, len(pairs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, help="Root of the original CoroPerf research workspace")
    parser.add_argument("--output", type=Path, default=HERE / "data" / "cases.json")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    public = workspace / "web" / "coroperf-results" / "public"
    results = (public / "results.js").read_text(encoding="utf-8").split("=", 1)[1].strip().removesuffix(";")
    index = json.loads(results)
    ledger = read_json(workspace / "perf-out" / "systems-repro" / "ledger.json")
    by_id = {row["id"]: row for row in ledger["cases"]}
    deferred = read_json(workspace / "research" / "deferred-security-issues.json")["cases"]
    deferred_ids = DEFERRED_IDS | {row["id"] for row in deferred}
    deferred_urls = {row["issue_url"] for row in deferred}

    cases = []
    for item in index["cases"]:
        identifier = item["id"]
        if identifier in deferred_ids or item["url"] in deferred_urls:
            continue
        evidence = read_json(public / "evidence" / f"{identifier}.json")
        findings = {key: safe_text(value) for key, value in evidence["findings"].items()}
        if REVIEW.search(" ".join([item["title"], *findings.values()])):
            continue
        row = by_id[identifier]
        graph_path = workspace / row["graph"] if row.get("graph") else None
        graph = read_json(graph_path) if graph_path and graph_path.is_file() else {"edges": [], "segments": []}
        joins, physical, pair_count = evidence_from_graph(graph, row, evidence)
        if not joins and identifier in SUPPLEMENTAL_GRAPHS:
            path, label = SUPPLEMENTAL_GRAPHS[identifier]
            if (workspace / path).is_file():
                supplement = read_json(workspace / path)
                joins, _, pair_count = evidence_from_graph(supplement, {}, {})
                for join in joins:
                    join["capture_label"] = label
        upstream_reference = evidence.get("upstream_reference")
        if upstream_reference and not any(upstream_reference.startswith(f"https://{host}/") for host in TRACKERS):
            upstream_reference = None
        cases.append({
            "id": identifier,
            "reference": f'{item["repo"]} #{item["issue"]}',
            "title": safe_text(item["title"]),
            "url": item["url"],
            "upstream_reference": upstream_reference,
            "reproduction": evidence["reproduction"],
            "diagnosis": evidence["diagnosis"],
            "reviewed_origin": bool(item.get("origin")),
            "findings": findings,
            "joins": joins,
            "physical": physical,
            "pair_count": pair_count,
        })
    snapshot = {"corpus_date": index["date"], "historical_issues": ledger["statistics"]["issues"],
                "historical_origin_lower_bound": ledger["statistics"]["source_for_coroutine_lower_bound"],
                "cases": cases}
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
