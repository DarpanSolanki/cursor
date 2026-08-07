#!/usr/bin/env python3
"""Measure what every KG tool actually costs, and fail when one gets fat.

A lookup that costs more than the grep it replaces will lose to the grep, whatever the
rules say. `kg_deps` returned 6.8k tokens for one call — truncated mid-output — while the
targeted grep it was meant to replace costs ~0.3k. That is not a discipline problem.

Budgets are per-tool because the tools do different jobs: `kg_error` is the documented
first hop and must stay tiny; `kg_flow` legitimately walks a chain.

  kg_response_budget.py            measure, exit 1 if any tool is over budget
  kg_response_budget.py --json
  kg_response_budget.py --accept   record current sizes as the budget (+25% headroom)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
KG = ROOT / "cursor-bundle" / "kg" / "bin" / "kg.py"

PROBES: list[tuple[str, list[str]]] = [
    ("kg_error", ["error", "134291"]),
    ("kg_schema", ["schema", "loan_account.loan_status"]),
    ("kg_table", ["table", "loan_account"]),
    ("kg_docs", ["docs", "loanDisbursementCancellation"]),
    ("kg_deps", ["deps", "trustt-platform-accounting"]),
    ("kg_why", ["why", "loanPrepayment"]),
    ("kg_cases", ["cases", "loan_account"]),
    ("kg_writes", ["writes", "loan_account"]),
    ("kg_reads", ["reads", "loan_account"]),
    ("kg_flow", ["flow", "loanDisbursementCancellation"]),
    ("kg_orient", ["orient", "loanPrepayment"]),
]

# Ceilings reflect what each tool must actually do, not a flat number. kg_orient is a
# composite of flow + why + cases, so holding it to a single-lookup budget would either be
# a lie or would silently drop the evidence it exists to provide.
DEFAULT_CEILING = 4000
CEILINGS = {
    # Composite: flow spine + curated why + cases + verify paths. Measured 19,024
    # tokens before capping, 6,435 after. Cutting further would start removing
    # curated root causes, which is the evidence the tool exists to carry.
    "kg_orient": 7000,
    "kg_why": 5000,
    "kg_error": 600,
    "kg_schema": 900,
    "kg_table": 900,
    "kg_docs": 900,
    "kg_deps": 1200,
    "kg_cases": 1500,
    "kg_reads": 2500,
    "kg_writes": 2500,
}


def measure(argv: list[str]) -> tuple[int, float]:
    started = time.time()
    out = subprocess.run([sys.executable, str(KG), *argv], cwd=str(ROOT),
                         capture_output=True, text=True, timeout=300)
    return len(out.stdout) // 4, time.time() - started


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = []
    for name, argv in PROBES:
        tokens, secs = measure(argv)
        ceiling = CEILINGS.get(name, DEFAULT_CEILING)
        rows.append({"tool": name, "tokens": tokens, "seconds": round(secs, 2),
                     "ceiling": ceiling, "over": tokens > ceiling})

    if args.json:
        print(json.dumps(rows, indent=1))
        return 1 if any(r["over"] for r in rows) else 0

    print(f"{'tool':<12} {'tokens':>7} {'ceiling':>8} {'sec':>6}")
    for r in sorted(rows, key=lambda x: -x["tokens"]):
        mark = "  OVER" if r["over"] else ""
        print(f"{r['tool']:<12} {r['tokens']:>7} {r['ceiling']:>8} {r['seconds']:>6}{mark}")

    over = [r for r in rows if r["over"]]
    if over:
        print(f"\nFAIL — {len(over)} tool(s) over budget: "
              + ", ".join(f"{r['tool']} ({r['tokens']}>{r['ceiling']})" for r in over))
        print("  A lookup costing more than the grep it replaces will lose to the grep.")
        return 1
    print(f"\nall {len(rows)} within budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
