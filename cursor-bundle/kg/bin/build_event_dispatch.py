#!/usr/bin/env python3
"""
build_event_dispatch.py — loan_account_events_queue event_type → Request dispatch map.

Child SHG flows often enqueue FCL/REP/… rows; ChildLoanEventProcessing* batch reads
the queue and dispatches to orchestration Requests via EVENT_TYPE_ORC_API_MAP.

Emits processor/scheduler -calls-> request:{repo}/{api} for each mapped event type.

Usage: build_event_dispatch.py <accumulated_raw.jsonl> <repoDir> [...]
"""
from __future__ import annotations

import json
import os
import re
import sys

MAP_RE = re.compile(
    r"EVENT_TYPE_ORC_API_MAP\.put\s*\(\s*EventType\.(\w+)\.toString\(\)\s*,\s*\"([A-Za-z]\w+)\"\s*\)"
)
# static { EVENT_TYPE_ORC_API_MAP.put(EventType.FCL.toString(), "childLoanForeclosure"); }
MAP_RE2 = re.compile(
    r'EVENT_TYPE_ORC_API_MAP\.put\s*\(\s*[^,]+\.toString\(\)\s*,\s*"([A-Za-z]\w+)"\s*\)'
)

DISPATCH_PROCESSORS = (
    "childLoanEventProcessingItemProcessor",
    "childLoanEventsProcessingProcessor",
)
DISPATCH_SCHEDULERS = (
    "childLoanEventProcessingBatchJob",
)


def emit(o: dict) -> None:
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def warn(*a) -> None:
    print(*a, file=sys.stderr)


def req_id(repo: str, name: str) -> str:
    return f"request:{repo}/{name}"


def load_maps(tmp: str) -> tuple[dict[str, set[str]], set[str], set[str]]:
    owners: dict[str, set[str]] = {}
    request_ids: set[str] = set()
    known_schedulers: set[str] = set()
    for line in open(tmp, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("t") == "node" and o.get("kind") == "request":
            label = o.get("label") or ""
            repo = o.get("repo") or ""
            rid = o.get("id") or ""
            if label and repo:
                owners.setdefault(label, set()).add(repo)
            if rid:
                request_ids.add(rid)
        if o.get("t") == "node" and o.get("kind") == "scheduler":
            known_schedulers.add(o.get("id", ""))
    return owners, request_ids, known_schedulers


def parse_event_map(java_path: str) -> list[tuple[str, str]]:
    try:
        text = open(java_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    out: list[tuple[str, str]] = []
    for m in MAP_RE.finditer(text):
        out.append((m.group(1), m.group(2)))
    if not out:
        for m in MAP_RE2.finditer(text):
            out.append(("?", m.group(1)))
    return out


def resolve_request(api: str, repo: str, owners: dict[str, set[str]], request_ids: set[str]) -> str | None:
    repos = owners.get(api)
    if not repos:
        return None
    if repo in repos:
        cand = req_id(repo, api)
    elif len(repos) == 1:
        cand = req_id(next(iter(repos)), api)
    else:
        cand = req_id(sorted(repos)[0], api)
    return cand if cand in request_ids else None


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: build_event_dispatch.py <accumulated_raw.jsonl> <repoDir> ...", file=sys.stderr)
        sys.exit(2)
    tmp = sys.argv[1]
    owners, request_ids, known_schedulers = load_maps(tmp)
    seen: set[tuple[str, str]] = set()
    n = 0
    for rd in sys.argv[2:]:
        repo = os.path.basename(rd.rstrip(os.sep))
        entity = os.path.join(
            rd, "src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java"
        )
        if not os.path.isfile(entity):
            continue
        rel = os.path.relpath(entity, start=os.getcwd())
        for event, api in parse_event_map(entity):
            tgt = resolve_request(api, repo, owners, request_ids)
            if not tgt:
                continue
            for bean in DISPATCH_PROCESSORS:
                src = f"processor:{bean}"
                key = (src, tgt)
                if key in seen:
                    continue
                seen.add(key)
                emit({
                    "t": "edge",
                    "from": src,
                    "to": tgt,
                    "rel": "calls",
                    "note": f"loan_account_events_queue event_type={event} → {api}",
                    "repo": repo,
                    "src": rel,
                })
                n += 1
            for sched in DISPATCH_SCHEDULERS:
                sid = f"scheduler:{sched}"
                if sid not in known_schedulers:
                    continue
                key = (sid, tgt)
                if key in seen:
                    continue
                seen.add(key)
                emit({
                    "t": "edge",
                    "from": sid,
                    "to": tgt,
                    "rel": "calls",
                    "note": f"batch dispatches event_type={event} → {api}",
                    "repo": repo,
                    "src": rel,
                })
                n += 1
    warn(f"[event_dispatch] queue→request calls={n}")


if __name__ == "__main__":
    main()
