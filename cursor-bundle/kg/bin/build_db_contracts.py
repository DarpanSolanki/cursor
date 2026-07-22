#!/usr/bin/env python3
"""
build_db_contracts.py — DB-seeded cross-service callbacks (invisible to orchestration XML).

Sources:
  - initial-setup flyway: task_type_api_execution COPY/INSERT rows (api_name per action)
  - curated death-foreclosure task SQL migrations (verified paths)

Emits contract:db:* nodes + edges from request:updateTaskWorkflow / task actions → target apiName.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

from _paths import WORKSPACE

COPY_HEADER = re.compile(
    r"COPY\s+task_type_api_execution\s*\([^)]*\)\s+FROM\s+STDIN",
    re.I,
)
API_IN_UPDATE = re.compile(r"api_name\s*=\s*'([^']+)'", re.I)


def emit(o: dict) -> None:
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def infer_service(api_name: str) -> str:
    low = api_name.lower()
    if low.startswith(("loan", "post", "reverse", "gl", "fetch", "getloan", "collectionloan",
                       "disburse", "dpi", "interest", "cancel")):
        return "trustt-platform-accounting"
    if low.startswith(("updatecollection", "createorupdatecollection", "validatefinnone")):
        return "trustt-platform-payments"
    if low.startswith(("update", "create", "getborrower", "getbasic", "geo")):
        return "trustt-platform-los"
    return "trustt-platform-task"


def parse_copy_block(text: str, src: str) -> list[dict]:
    rows: list[dict] = []
    m = COPY_HEADER.search(text)
    if not m:
        return rows
    tail = text[m.end() :]
    for line in tail.splitlines():
        line = line.strip()
        if not line or line.startswith("\\") or line.upper().startswith("SELECT"):
            break
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        api_name = parts[3].strip()
        action = parts[-1].strip() if parts[-1].strip() not in ("\\N", "") else "DEFAULT"
        if not api_name or api_name == "\\N":
            continue
        rows.append({
            "api_name": api_name,
            "action": action,
            "task_type_version_id": parts[1].strip(),
            "src": src,
        })
    return rows


def scan_task_sql() -> list[dict]:
    found: list[dict] = []
    root = os.path.join(WORKSPACE, "trustt-platform-initial-setup", "flyway")
    for path in glob.glob(os.path.join(root, "**", "*.sql"), recursive=True):
        if "task" not in path.replace("\\", "/"):
            continue
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        rel = os.path.relpath(path, WORKSPACE)
        found.extend(parse_copy_block(text, rel))
        for am in API_IN_UPDATE.finditer(text):
            found.append({"api_name": am.group(1), "action": "UPDATE", "src": rel})
    return found


def main() -> None:
    seen: set[str] = set()
    for row in scan_task_sql():
        api = row["api_name"]
        action = row.get("action") or "DEFAULT"
        cid = f"contract:db:task:{action}->{api}"
        if cid in seen:
            continue
        seen.add(cid)
        svc = infer_service(api)
        emit({
            "t": "node",
            "id": cid,
            "kind": "contract",
            "label": f"task_type_api_execution {action} → {api}",
            "protocol": "DB_CALLBACK",
            "money": api.lower().startswith(
                ("loan", "post", "collection", "disburse", "reverse", "dpi", "interest", "cancel")
            ),
            "repo": "trustt-platform-initial-setup",
            "src": row["src"],
        })
        emit({
            "t": "edge",
            "from": "request:updateTaskWorkflow",
            "to": cid,
            "rel": "produces_contract",
            "note": f"DB seed action={action}",
            "src": row["src"],
        })
        emit({
            "t": "edge",
            "from": cid,
            "to": f"request:{api}",
            "rel": "consumes_via",
            "src": row["src"],
        })
        if svc != "trustt-platform-task":
            emit({
                "t": "edge",
                "from": "service:trustt-platform-task",
                "to": f"service:{svc}",
                "rel": "contract",
                "note": f"DB_CALLBACK {action} → {api}",
                "src": row["src"],
            })


if __name__ == "__main__":
    main()
