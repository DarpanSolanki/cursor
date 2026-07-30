#!/usr/bin/env python3
"""
build_internal_calls.py — index Java-dispatched nested Request flows into the KG.

Orchestration XML only lists top-level processors. Many money paths dispatch a child
Request at runtime via executionContext.put("api_name", "<Request>"). Without these
edges, `kg why` / `kg orient` miss nested processors and curated failure modes.

Emits:
  processor:{bean} -calls-> request:{repo}/{apiName}
  request:{repo}/{parent} -calls-> request:{repo}/{apiName}  (when parent known from orch)

Usage: build_internal_calls.py <accumulated_raw.jsonl> <repoDir> [<repoDir> ...]
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

API_NAME_RE = re.compile(
    r'\.put(?:Local)?\s*\(\s*["\']api_name["\']\s*,\s*["\']([A-Za-z]\w+)["\']'
)
API_NAME_TERNARY_RE = re.compile(
    r'\.put(?:Local)?\s*\(\s*["\']api_name["\']\s*,\s*[^;]+?\?\s*["\']([A-Za-z]\w+)["\']\s*:\s*["\']([A-Za-z]\w+)["\']',
    re.S,
)
CALL_INTERNAL_API_RE = re.compile(
    r'\.callInternalAPI\s*\(\s*[^,]+,\s*["\']([A-Za-z]\w+)["\']'
)
CLASS_RE = re.compile(r"\bclass\s+(\w+)")


def emit(o: dict) -> None:
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def warn(*a) -> None:
    print(*a, file=sys.stderr)


def bean_name(cls: str) -> str:
    if len(cls) > 1 and cls[0].isupper() and cls[1].isupper():
        return cls
    return cls[0].lower() + cls[1:] if cls else cls


def req_id(repo: str, name: str) -> str:
    return f"request:{repo}/{name}" if repo else f"request:{name}"


def load_maps(tmp: str) -> tuple[dict[str, set[str]], dict[str, set[tuple[str, str]]], set[str]]:
    """api label -> repos; processor bean -> (repo, request); all request ids."""
    owners: dict[str, set[str]] = {}
    proc_to_reqs: dict[str, set[tuple[str, str]]] = {}
    request_ids: set[str] = set()
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
        if o.get("t") == "edge" and o.get("rel") == "invokes":
            src = o.get("from", "")
            dst = o.get("to", "")
            if src.startswith("request:") and dst.startswith("processor:"):
                repo_req = src[len("request:"):]
                if "/" in repo_req:
                    repo, req = repo_req.split("/", 1)
                else:
                    repo, req = "", repo_req
                bean = dst[len("processor:"):]
                proc_to_reqs.setdefault(bean, set()).add((repo, req))
    return owners, proc_to_reqs, request_ids


def resolve_target(api: str, producer_repo: str, owners: dict[str, set[str]], request_ids: set[str]) -> str | None:
    repos = owners.get(api)
    if not repos:
        return None
    if producer_repo in repos:
        cand = req_id(producer_repo, api)
    elif len(repos) == 1:
        cand = req_id(next(iter(repos)), api)
    else:
        cand = req_id(sorted(repos)[0], api)
    return cand if cand in request_ids else None


def scan_java(path: str) -> tuple[str | None, list[str]]:
    try:
        raw = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None, []
    cm = CLASS_RE.search(raw)
    if not cm:
        return None, []
    apis: set[str] = set()
    apis.update(m.group(1) for m in API_NAME_RE.finditer(raw))
    for m in API_NAME_TERNARY_RE.finditer(raw):
        apis.add(m.group(1))
        apis.add(m.group(2))
    apis.update(m.group(1) for m in CALL_INTERNAL_API_RE.finditer(raw))
    return cm.group(1), sorted(apis)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: build_internal_calls.py <accumulated_raw.jsonl> <repoDir> ...", file=sys.stderr)
        sys.exit(2)
    tmp = sys.argv[1]
    repos = sys.argv[2:]
    owners, proc_to_reqs, request_ids = load_maps(tmp)
    seen: set[tuple[str, str, str]] = set()
    n_proc = 0
    n_req = 0
    for rd in repos:
        repo = os.path.basename(rd.rstrip(os.sep))
        for jf in sorted(glob.glob(os.path.join(rd, "src", "main", "java", "**", "*.java"), recursive=True)):
            if "/test/" in jf.replace("\\", "/"):
                continue
            cls, apis = scan_java(jf)
            if not cls or not apis:
                continue
            rel = os.path.relpath(jf, start=os.getcwd())
            bean = bean_name(cls)
            for api in apis:
                tgt = resolve_target(api, repo, owners, request_ids)
                if not tgt:
                    continue
                key = (f"processor:{bean}", tgt, rel)
                if key not in seen:
                    seen.add(key)
                    emit({
                        "t": "edge",
                        "from": f"processor:{bean}",
                        "to": tgt,
                        "rel": "calls",
                        "note": f"java api_name dispatch → {api}",
                        "repo": repo,
                        "src": rel,
                    })
                    n_proc += 1
                for prepo, preq in proc_to_reqs.get(bean, ()):
                    if not prepo:
                        continue
                    parent = req_id(prepo, preq)
                    if parent not in request_ids:
                        continue
                    key2 = (parent, tgt, rel)
                    if key2 not in seen:
                        seen.add(key2)
                        emit({
                            "t": "edge",
                            "from": parent,
                            "to": tgt,
                            "rel": "calls",
                            "note": f"via {bean} api_name → {api}",
                            "repo": prepo,
                            "src": rel,
                        })
                        n_req += 1
    warn(f"[internal_calls] processor→request={n_proc}, request→request={n_req}")


if __name__ == "__main__":
    main()
