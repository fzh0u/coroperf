#!/usr/bin/env python3
"""Export a public snapshot from the CoroPerf research workspace."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

from copy_text import CASE_LANGUAGES, CONTRIBUTION_KINDS, FIX_STATES, ISSUE_KINDS, SOURCE_TOKEN_STAGES
from refresh_issue_status import apache_jira_key


HERE = Path(__file__).resolve().parents[1]
BASE_EDGES = {"base_to_sample", "create_base_to_sample_stack", "base_to_sample_stack"}
CANCELLATION_EDGE = "cancel_request_to_observation"
CANCELLATION_STAGES = {"taskgroup-internal-cancel": "waiter-error", "taskgroup-outer-cancel": "propagated"}
PARENT_EDGES = {"coroutine_created_by", "goroutine_created_by", "created_by", "parent_to_create"}
PARENT_WITNESSES = {
    "scheduled-handle-running-at-task-creation", "actual-rpc-handler-and-submitted-work-item",
    "same-dequeued-request-in-work-item", "buffered-result-object", "stored-exception-object-handoff",
    "same-frozen-result-object", "same-singleflight-call-result-channel", "same-pool-holder-release-future",
    "same-batch-request-future", "rust-engine-thread-launch", "same-reactor-tool-batch",
    "same-dynamo-endpoint-notifier", "ray-batcher-reader-created-by-request-task",
    "trtllm-batch-task-and-worker-record",
    "same-vllm-benchmark-process-and-client-task",
    "same-ray-terminal-operator", "same-ray-task-id-and-index", "verl-live-processor-task",
    "same-executing-futuretask",
}
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
ANSI_COLOR = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
TRACKERS = {"github.com", "code.djangoproject.com", "issues.apache.org", "sqlite.org"}
CHINESE_HEADLINES = {
    "dotnet--runtime--60764": "Foo 恢复后，物理调用栈里找不到 Main",
    "drogonframework--drogon--2331": "Drogon 在数据库事件循环上执行同步 SQL，导致请求超时",
    "tokio-rs--tokio--6315": "Tokio 的 LIFO 槽位保留了一个没有及时轮询的任务",
    "pgjdbc--pgjdbc--1951": "Hibernate 等待 PostgreSQL 时，被钉住的虚拟线程属于哪个请求？",
    "python--cpython--91048": "睡眠中的 asyncio Task 是谁创建的，又被谁等待？",
    "python--cpython--88831": "哪个任务还在等待 Future 时就被垃圾回收了？",
    "aio-libs--async-lru--528": "缓存协程的实时调用栈缺失原始调用者",
    "fastapi--fastapi--709": "停机时哪个 WebSocket 请求仍在等待订阅？",
    "sqlalchemy--sqlalchemy--8145": "连接清理被取消后，哪次请求留下了未归还的连接？",
    "grpc--grpc-kotlin--299": "相同的 gRPC 状态异常分别来自哪个 Kotlin 调用者？",
    "kotlin--kotlinx.coroutines--2327": "Kotlin 的 Future 桥接丢失了失败请求的调用者",
    "kotlin--kotlinx.coroutines--2604": "delay 恢复后的异常栈缺少 secondCall",
    "python-trio--trio--285": "两个 socket 读取栈相同时，哪个 Trio 子任务被取消？",
    "huggingface--huggingface_hub--2521": "哪个未迭代的推理流触发了警告？",
    "automattic--mongoose--15317": "Mongoose 校验异常栈缺少应用的 save 调用",
    "axios--axios--2387": "相同的 Axios 错误来自哪两个请求入口？",
    "knex--knex--2500": "await Knex 查询后，异常栈缺少应用调用行",
    "sequelize--sequelize--12044": "Sequelize 的重复键异常栈丢失 create 调用点",
    "sidorares--node-mysql2--530": "相同的 mysql2 查询错误分别由哪个入口触发？",
    "sindresorhus--got--2277": "触发 Got 连接超时的是哪个下载调用？",
    "typeorm--typeorm--11499": "TypeORM 的 SQL Server 错误栈止于查询执行器",
    "omnilib--aiosqlite--87": "upsert 返回的 lastrowid 属于哪个并发调用？",
    "tortoise--tortoise-orm--2060": "并发 update_or_create 返回了另一个调用者的值",
    "microsoft--playwright--40141": "嵌套 Playwright 步骤的异常栈缺少外层方法",
    "knex--knex--2419": "Knex 的 await 与 catch 给出不同的查询栈",
    "knex--knex--4531": "未定义的绑定让 Knex 错误栈缺少查询调用点",
    "typeorm--typeorm--11271": "MySQL 重复键异常栈遗漏 TypeORM 插入调用者",
    "magicstack--asyncpg--1149": "游标预取让已到达的行迟迟无法交给调用者",
}


def safe_text(value):
    text = ANSI_COLOR.sub("", str(value))
    cleaned = INTERNAL_PATH.sub(lambda m: m.group().replace("\\", "/").rsplit("/", 1)[-1], text)
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
    record = {
        "id": str(segment["id"]),
        "event": event(segment),
        "sample_kind": segment.get("sample_kind"),
        "frames": frame_list(segment, leaf_first),
    }
    duration = segment.get("wait_duration_ns")
    if duration is not None:
        if type(duration) is not int or duration <= 0:
            raise ValueError(f"Invalid wait duration for record {record['id']}")
        record["wait_duration_ns"] = duration
    return record


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
        witness = edge.get("evidence")
        parents[child].add((parent, kind, witness if witness in PARENT_WITNESSES else ""))
    return parents


def ancestry(start, segments, parents, leaf_first):
    chain = []
    seen = {start}
    current = start
    while options := parents.get(current):
        if len({parent for parent, _, _ in options}) != 1:
            break
        parent, kind, witness = min(options)
        if parent in seen or not segments[parent].get("frames"):
            break
        entry = block(segments[parent], leaf_first)
        entry["link_to_child"] = kind
        if witness:
            entry["link_evidence"] = witness
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


def cancellation_witness(request, observation, edge):
    witness = edge.get("evidence")
    stage = CANCELLATION_STAGES.get(witness)
    details = request.get("observation", {})
    issuer = details.get("issuer")
    internal = issuer == request.get("target_task")
    if (stage and details.get("stage") == "cancel" and issuer
            and internal == (witness == "taskgroup-internal-cancel")
            and observation.get("observation", {}).get("stage") == stage
            and request.get("target_task") and request["target_task"] == observation.get("target_task")
            and request.get("process_id") and request["process_id"] == observation.get("process_id")
            and request.get("thread_id") and request["thread_id"] == observation.get("thread_id")
            and int(request["timestamp_ns"]) < int(observation["timestamp_ns"])):
        return witness
    return None


def evidence_from_graph(graph, ledger, public, required_pairs):
    segments = {str(s["id"]): s for s in graph["segments"]}
    leaf_first = graph.get("frame_order") != "root_to_leaf"
    parents = raw_parent_edges(graph, segments)
    origin = public.get("origin") or {}
    candidates = defaultdict(dict)
    cancellation = {}
    for edge in graph["edges"]:
        kind = edge["kind"]
        source, target = str(edge["from"]), str(edge["to"])
        if kind in BASE_EDGES:
            candidates[target][source] = kind
        elif kind == CANCELLATION_EDGE:
            witness = cancellation_witness(segments[source], segments[target], edge)
            if witness:
                candidates[target][source] = kind
                cancellation[source, target] = witness
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
        source_events = {"cancel_request"} if sources.get(source) == CANCELLATION_EDGE else CREATE
        if (set(sources) != {source} or event(a) not in source_events or event(b) not in OBSERVATION
                or not a.get("frames") or not b.get("frames") or identity not in labels
                or identity != b.get("coroutine_id") or framework_root(a)):
            raise ValueError(f"{ledger['id']}: no verified coroutine join from {source} to {target}")
        creation, observation = block(a, leaf_first), block(b, leaf_first)
        ancestors = ancestry(source, segments, parents, leaf_first)
        for record in [*ancestors, creation, observation]:
            record["instance"] = labels[segments[record["id"]]["coroutine_id"]]
        ownership = b.get("ownership_evidence")
        identity_kind = producer.get("identity_kind")
        if ownership in {
            "actor-entry-argument-dataflow", "active-work-item-object", "same-ray-actor-asyncio-task",
            "verl-live-rollout-task", "verl-live-paused-processor",
        }:
            identity_kind = ownership
        identity_kind = cancellation.get((source, target), identity_kind)
        joins.append({
            "creation": creation,
            "observation": observation,
            "edge": sources[source],
            "ancestors": ancestors,
            "identity_kind": identity_kind,
            "interval_attribution": ownership == "execution-interval",
        })
    return joins


def chinese_case(row):
    findings = {
        "observation": safe_text(row["symptom_zh"]),
        "interpretation": safe_text(row["reasoning_zh"]),
        "limits": safe_text(row["limits_zh"]),
    }
    title = row.get("title_zh") or CHINESE_HEADLINES.get(row["id"])
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
    followups = []
    for row in deferred:
        if not (website := row.get("website")):
            continue
        url = row["issue_url"]
        issue = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/issues/(\d+)", url)
        merged_fix = website.get("merged_fix")
        fix_url = merged_fix or website.get("pull_request")
        if issue:
            repo, number = issue.groups()
            reference = f"{repo} #{number}"
            if fix_url and not re.fullmatch(rf"https://github\.com/{re.escape(repo)}/pull/\d+", fix_url):
                raise ValueError(f'{row["id"]}: invalid public follow-up pull request URL')
        elif key := apache_jira_key(url):
            reference = key
            if website.get("pull_request") or (merged_fix and not re.fullmatch(
                r"https://github\.com/apache/[A-Za-z0-9_.-]+/commit/[0-9a-f]{40}", merged_fix
            )):
                raise ValueError(f'{row["id"]}: invalid public Apache follow-up fix URL')
        else:
            raise ValueError(f'{row["id"]}: invalid public follow-up issue URL')
        followups.append({
            "id": row["id"], "url": url, "reference": reference,
            "title": website["title"], "title_zh": website["title_zh"],
            "fix": {"state": "merged" if merged_fix else "unconfirmed", "url": fix_url} if fix_url else None,
        })

    cases = []
    snapshot_date = index["date"]
    for identifier, review in focus.items():
        kind = review.get("kind")
        if kind not in ISSUE_KINDS:
            raise ValueError(f"{identifier}: expected a reviewed issue type")
        contribution_kind = review.get("contribution_kind")
        if contribution_kind not in CONTRIBUTION_KINDS:
            raise ValueError(f"{identifier}: expected a reviewed diagnostic contribution")
        language = review.get("language")
        if language not in CASE_LANGUAGES:
            raise ValueError(f"{identifier}: expected a reviewed case language")
        fix = review.get("fix")
        if fix:
            state = fix.get("state")
            url = fix.get("url", "")
            if state not in FIX_STATES or (state != "local" and not url.startswith("https://github.com/")):
                raise ValueError(f"{identifier}: invalid fix evidence")
            if state == "local" and url:
                raise ValueError(f"{identifier}: local patch has an upstream URL")
        if review.get("case_file"):
            row = read_json(workspace / review["case_file"])
            if row["id"] != identifier:
                raise ValueError(f"{identifier}: imported case ID differs from the catalog")
            snapshot_date = max(snapshot_date, row["verified_on"])
            item, evidence = row, row
        else:
            item = index_by_id[identifier]
            row = by_id[identifier]
            evidence = read_json(public / "evidence" / f"{identifier}.json")
        if identifier in deferred_ids or item["url"] in deferred_urls:
            raise ValueError(f"{identifier}: deferred from publication")
        findings = {key: safe_text(value) for key, value in evidence["findings"].items()}
        if REVIEW.search(" ".join([item["title"], *findings.values()])):
            raise ValueError(f"{identifier}: review required before publication")
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
            "reference": apache_jira_key(item["url"]) or f'{item["repo"]} #{item["issue"]}',
            "title": safe_text(item["title"]),
            "title_zh": title_zh,
            "url": item["url"],
            "upstream_reference": upstream_reference,
            "kind": kind,
            "contribution_kind": contribution_kind,
            "language": language,
            "fix": fix,
            "reproduction": evidence["reproduction"],
            "diagnosis": evidence["diagnosis"],
            "findings": findings,
            "findings_zh": findings_zh,
            "joins": joins,
            "contribution": review["en"],
            "contribution_zh": review["zh"],
        })
        transfers = graph.get("observed_source_token_transfers", [])
        if transfers:
            observations = {join["observation"]["id"]: join["observation"]["instance"] for join in joins}
            for transfer in transfers:
                start, end = transfer["from"], transfer["to"]
                if (transfer["stage"] not in SOURCE_TOKEN_STAGES or start not in observations
                        or end not in observations or observations[start] == observations[end]):
                    raise ValueError(f"{identifier}: invalid source token transfer {start} → {end}")
            cases[-1]["observed_source_token_transfers"] = transfers
    snapshot = {"corpus_date": snapshot_date, "cases": cases, "deferred_followups": followups}
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
