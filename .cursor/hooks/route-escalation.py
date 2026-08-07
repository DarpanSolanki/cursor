#!/usr/bin/env python3
"""PostToolUse hook — escalate the open task when the edited path outranks the planned class.

The router plans from the words of the request; an edit is what the task turns out to be. When a
task planned as docs-kb starts writing an accounting money path, the plan was too light — this
records the divergence and names the gates the heavier class demands, so "shortest path" can never
quietly become "skipped the money gates".
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.environ.get("CURSOR_PROJECT_DIR") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, os.path.join(ROOT, "scripts", "lib"))

MONEY_PATH = re.compile(
    r"(trustt-platform-accounting/.*(loan|batchnew|deathforeclosure|dpi|transaction|posting|billing|accrual|foreclos)"
    r"|/orchestration/.*\.xml$"
    r"|scripts/(sql|dpic|dcf_sanity|disbursement)/"
    r"|trustt-platform-payments/.*(collection|allocat|settle)"
    r"|trustt-platform-los/.*(disburs|sync))",
    re.I,
)
SERVICE_CODE = re.compile(r"(trustt-platform-|novopay-)[a-z-]+/.*\.(java|xml|gradle)$", re.I)
KB_PATH = re.compile(r"(\.cursor/|docs/|cursor-bundle/|\.md$)", re.I)


def infer_class(rel: str) -> str:
    if MONEY_PATH.search(rel):
        return "money-fix"
    if SERVICE_CODE.search(rel):
        return "non-money-fix"
    if KB_PATH.search(rel):
        return "docs-kb"
    return "non-money-fix"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    ti = payload.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if not path:
        return 0
    rel = os.path.relpath(path, ROOT)
    if rel.startswith(".."):
        return 0

    try:
        from route_ledger import escalate, load
    except Exception:
        return 0

    data = load()
    if not data or data.get("status") != "open":
        return 0

    target = infer_class(rel)
    res = escalate(to_class=target, reason=f"edit touched a {target} path", path=rel)
    if not res.get("escalated"):
        return 0

    gates = res.get("delta_gates") or []
    print(
        f"[route-escalation] PLAN ESCALATED {res['from']} → {res['to']} "
        f"({rel}). The lighter plan did not include these gates:"
    )
    if gates:
        for g in gates:
            print(f"  + {g}")
    else:
        print("  (no additional gates — terminal predicates raised instead)")
    print("  Run the added gates before closing; `route-ledger.sh terminal` shows what is unmet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
