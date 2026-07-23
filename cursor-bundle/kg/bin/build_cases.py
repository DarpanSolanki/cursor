#!/usr/bin/env python3
"""
build_cases.py — flow precedents layer (opt-in from brain CHANGELOG).

NOT every changelog row becomes a KG node. Only entries tagged kg-flow (or KB-FLOW:)
index into case nodes — behaviour/flow fixes agents need at `kg cases <apiName>`.

Full audit log stays in CHANGELOG.md for humans; graph stays lean and stable.

Usage: build_cases.py <existing-nodes.jsonl>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys

from _paths import CHANGELOG

HEADER = re.compile(r"^##\s+(.+)$", re.M)
ERRCODE = re.compile(r"\b(1[0-9]{5})\b")
TICKET = re.compile(r"\b(SDCP-\d+|SP-\d+|HSQA-\d+|TDPFR-\d+|TDPQA-\d+)\b")
SHA = re.compile(r"`?([0-9a-f]{7,40})`?")
KG_FLOW = re.compile(r"\bkg-flow\b", re.I)
KB_ONLY = re.compile(r"\b(kb-only|skip-kg)\b", re.I)
KG_FLOW_DETAIL = re.compile(r"^KG-FLOW:\s*", re.I | re.M)
BRANCH = re.compile(r"\b(mfi_(?:integration|release)_v\d+(?:\.\d+)*)\b")

# Changelog "service" field → workspace repo folder (best-effort).
SERVICE_TO_REPO = {
    "accounting-v2": "trustt-platform-accounting",
    "accounting": "trustt-platform-accounting",
    "acct": "trustt-platform-accounting",
    "payments": "trustt-platform-payments",
    "los": "trustt-platform-los",
    "platform-lib": "trustt-platform-lib",
    "lib": "novopay-platform-lib",
    "actor": "trustt-platform-actor",
    "batch": "trustt-platform-batch",
    "initial-setup": "trustt-platform-initial-setup",
    "notifications": "trustt-platform-notifications",
    "task": "trustt-platform-task",
    "webapp": "trustt-platform-webapp",
}


def emit(o: dict) -> None:
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def should_index_in_kg(header: str, body: str) -> bool:
    if KB_ONLY.search(header):
        return False
    if KG_FLOW.search(header) or KG_FLOW_DETAIL.search(body):
        return True
    return False


def case_id_for(header: str, body: str) -> str:
    sha_m = SHA.search(header)
    if sha_m:
        return f"case:{sha_m.group(1)[:12]}"
    digest = hashlib.sha1(f"{header}\n{body[:200]}".encode()).hexdigest()[:10]
    return f"case:anon:{digest}"


def parse_header_fields(header: str) -> dict[str, str | None]:
    """Parse `DATE | scope | service | branch | tag | title` when present."""
    parts = [p.strip() for p in header.split("|")]
    service = parts[2] if len(parts) >= 3 else None
    branch = None
    if len(parts) >= 4:
        branch_m = BRANCH.search(parts[3]) or BRANCH.search(header)
        branch = branch_m.group(1) if branch_m else parts[3] or None
    else:
        branch_m = BRANCH.search(header)
        branch = branch_m.group(1) if branch_m else None
    repo = None
    if service:
        key = service.lower().strip()
        repo = SERVICE_TO_REPO.get(key)
        if not repo:
            for alias, mapped in SERVICE_TO_REPO.items():
                if alias in key:
                    repo = mapped
                    break
    return {"service": service, "branch": branch, "repo": repo}


def main() -> int:
    req_by_label: dict[str, list[str]] = {}
    tbl_ids: set[str] = set()
    if len(sys.argv) > 1 and __import__("os").path.exists(sys.argv[1]):
        for line in open(sys.argv[1], encoding="utf-8"):
            o = json.loads(line)
            if o.get("t") != "node":
                continue
            if o["kind"] == "request":
                req_by_label.setdefault(o["label"], []).append(o["id"])
            elif o["kind"] == "table":
                tbl_ids.add(o["label"])

    if not CHANGELOG.exists():
        return 0

    text = CHANGELOG.read_text(encoding="utf-8")
    marks = [(m.start(), m.group(1)) for m in HEADER.finditer(text)]
    indexed = 0
    skipped = 0

    for i, (pos, header) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = text[pos:end]

        if not should_index_in_kg(header, body):
            skipped += 1
            continue

        indexed += 1
        cid = case_id_for(header, body)
        date = header.split("|", 1)[0].strip()
        sha_m = SHA.search(header)
        tickets = sorted(set(TICKET.findall(header) + TICKET.findall(body)))
        errs = sorted(set(ERRCODE.findall(body)))
        meta = parse_header_fields(header)

        emit(
            {
                "t": "node",
                "id": cid,
                "kind": "case",
                "label": header[:120],
                "date": date,
                "sha": sha_m.group(1) if sha_m else None,
                "tickets": tickets,
                "error_codes": errs,
                "service": meta["service"],
                "branch": meta["branch"],
                "repo": meta["repo"],
                "src": "brain/changelog/CHANGELOG.md",
                "kg_tier": "flow-precedent",
            }
        )

        linked: set[str] = set()
        for name, ids in req_by_label.items():
            if len(name) >= 6 and re.search(r"\b" + re.escape(name) + r"\b", body):
                for rid in ids:
                    if rid in linked:
                        continue
                    # Prefer same-repo request when case meta has repo
                    if meta.get("repo") and f"request:{meta['repo']}/" not in rid and len(ids) > 1:
                        continue
                    linked.add(rid)
                    emit(
                        {
                            "t": "edge",
                            "from": cid,
                            "to": rid,
                            "rel": "touches",
                            "src": "brain/changelog/CHANGELOG.md",
                        }
                    )
                # if repo filter dropped all, link all
                if name not in {x.split("/")[-1] for x in linked} and name in body:
                    for rid in ids:
                        if rid not in linked:
                            linked.add(rid)
                            emit(
                                {
                                    "t": "edge",
                                    "from": cid,
                                    "to": rid,
                                    "rel": "touches",
                                    "src": "brain/changelog/CHANGELOG.md",
                                }
                            )
        for tbl in tbl_ids:
            if len(tbl) >= 6 and re.search(r"\b" + re.escape(tbl) + r"\b", body):
                emit(
                    {
                        "t": "edge",
                        "from": cid,
                        "to": f"table:{tbl}",
                        "rel": "touches",
                        "src": "brain/changelog/CHANGELOG.md",
                    }
                )
        for ec in errs:
            emit(
                {
                    "t": "node",
                    "id": f"error:{ec}",
                    "kind": "error",
                    "label": ec,
                    "src": "brain/changelog/CHANGELOG.md",
                }
            )
            emit(
                {
                    "t": "edge",
                    "from": cid,
                    "to": f"error:{ec}",
                    "rel": "hit_error",
                    "src": "brain/changelog/CHANGELOG.md",
                }
            )

    print(
        f"[build_cases] flow precedents: {indexed} indexed, {skipped} audit-only (no kg-flow tag)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
