#!/usr/bin/env python3
"""Task classifier → skill chain + scripts (proof-backed session routing)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "cursor-bundle/brain/skills-manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


KG_FIRST = [
    "MCP trustt-kg: kg_doctor (validate + fresh)",
    "MCP trustt-kg: kg_orient <apiName>",
    "MCP trustt-kg: kg_flow <apiName>",
    "MCP trustt-kg: kg_crud <apiName>",
    "CLI fallback (scripts/CI only): python3 cursor-bundle/kg/bin/kg.py <verb>",
]

ACCOUNTING = re.compile(
    r"\b(accounting|accrual|accrued|billing|posting|foreclosure|disburse\w*|repayment|dpi|iad|gl"
    r"|ledger|emi|installment|prepayment|writeoff|waiver|restructur\w*|rebooking|excess"
    r"|shg|jlg|indl|lan|loan_\w+|due_details|interest|principal|charge|tax|gst|mandate"
    r"|iac|dcf|clmt|crr|rps|neft|mft|npa|dpd)\b",
    re.I,
)

ACCOUNTING_SCRIPTS = [
    "bash scripts/bin/accounting-flow-coverage.sh",
    "read .cursor/gaps-and-risks-digest.md (escalate to SoT when GAP-id flagged)",
    "MCP trustt-kg: kg_why <apiName>",
]


def classify(text: str) -> dict:
    t = text.lower()
    if (
        re.search(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+", t)
        or re.search(r"\b[^/\s]+/[^/#\s]+#\d+\b", t)
        or re.search(r"\b(review|audit)\s+(this\s+)?(pr|pull request)\b", t)
        or re.search(r"\bpr[- ]review\b", t)
    ):
        kind = "PR_REVIEW"
        skills = ["pr-review"]
        scripts = [
            "scripts/bin/pr-review.sh <PR_URL|owner/repo#number> [--jira KEY] [--env ENV]",
            "python3 scripts/lib/pr_review_gate.py --report <draft.md> --artifacts <collector dir>",
        ]
        risk = "Medium"
    elif re.search(
        r"\b(slow|slower|slowness|latency|throughput|degraded|degradation|performance|perf"
        r"|bottleneck|hung|hang|timeout|timed out|skew|spike|took)\b"
        r"|\b\d+\s*(h|hr|hrs|hour|hours|min|mins|minute|minutes)\b",
        t,
    ) and re.search(
        r"\b(prod|production|uat|qa\d*|eod|bod|batch|job|deploy|deployed|release|train|api|query)\b",
        t,
    ):
        kind = "PERF_RCA"
        skills = ["workspace-router", "architect-thinking", "query-index-perf-gate"]
        scripts = [
            "MCP trustt-kg: kg_orient <apiName>",
            "MCP trustt-kg: kg_flow <apiName>",
            "MCP trustt-kg: kg_impact <symbol>",
            "bash scripts/bin/train-delta.sh <repo> <fromTrain> <toTrain>",
            "psql -f scripts/dpic/sql/helpers/batch_step_metrics.sql  # partition skew",
            "bash scripts/bin/hot-path-scan.sh --from-pending",
        ]
        risk = "High"
    elif re.search(r"\b(sanity|ntest|test|verify|regression|smoke|batch job|eod|dpi)\b", t):
        kind = "TEST"
        skills = ["workspace-router", "autonomous-workspace-ops"]
        scripts = [
            "scripts/bin/agent-ops.sh before-test <apiName>",
            "scripts/bin/ntest.sh auto <apiName>",
            "scripts/bin/agent-ops.sh on-failure accounting <apiName>",
        ]
        risk = "Medium"
    elif re.search(
        r"\b(rca|root cause|bug|incident|stuck|fail|error|sdcp|tdpqa|gap"
        r"|mismatch|not matching|mismatched|wrong|incorrect|discrepanc\w*|differ\w*"
        r"|unexpected|missing|blank|duplicate|reverted|negative|zero)\b",
        t,
    ):
        kind = "BUG/RCA"
        skills = ["workspace-router", "autonomous-workspace-ops"]
        scripts = [
            "MCP trustt-kg: kg_orient <apiName>",
            "python3 scripts/testing/footprint_builder.py show ftf:<id>",
            "scripts/testing/contract_graph.py list --money",
            "scripts/db-local.sh --canned <id> --param ...",
        ]
        risk = "High"
    elif re.search(r"\b(ship|fix|implement|commit|push|capture|kg-flow)\b", t):
        kind = "FIX+SHIP"
        skills = ["workspace-router", "autonomous-workspace-ops", "capture-proof"]
        scripts = [
            "scripts/bin/capture-flow.sh --ftg ... --jira ...",
            "cursor-bundle/kg/bin/changelog-add.sh --kg-flow ...",
            "scripts/bin/sync-intelligence.sh --quick",
            "scripts/bin/ship-knowledge-gate.sh",
        ]
        risk = "High"
    elif re.search(r"\b(sync|branch|scan|map|intelligence|kg rebuild)\b", t):
        kind = "SYNC"
        skills = ["workspace-router"]
        scripts = [
            "scripts/bin/platform-scan.sh --with-kg",
            "scripts/bin/sync-intelligence.sh --force",
            "scripts/bin/write-intelligence-hub.sh",
        ]
        risk = "Low"
    elif re.search(r"\b(email|mail|draft)\b", t):
        kind = "COMMS"
        skills = ["concise-email"]
        scripts = []
        risk = "Low"
    elif re.search(r"\b(@query|repository|dao|sql)\b", t):
        kind = "CODE/DAO"
        skills = ["reuse-queries-java-filter"]
        scripts = [
            "MCP trustt-kg: kg_writes <table>",
            "MCP trustt-kg: kg_reads <table>",
            "MCP trustt-kg: kg_schema <table>[.<column>]",
            "reuse existing @Query + Java filter before adding one",
        ]
        risk = "Medium"
    else:
        kind = "GENERAL"
        skills = ["workspace-router"]
        scripts = [
            "MCP trustt-kg: kg_doctor",
            "MCP trustt-kg: kg_orient <apiName>",
        ]
        risk = "Medium"

    api = None
    m = re.search(r"\b(disburseLoan|loanPrepayment|loanRepayment|dpiAccrual\w+|updateCollectionBatchDetails"
        r"|glBalanceZeroisation|interestAccrual\w+|loanAccountBilling\w*|penalInterestAccrual\w+"
        r"|loanForeclosure\w*|deathForeclosure\w*|postTransaction|loanAccountClosure"
        r"|loanWriteoff|loanAdvanceRepayment|generateRepaymentSchedule)\b", text, re.I)
    if m:
        api = m.group(1)

    if kind != "COMMS":
        merged = list(KG_FIRST)
        if ACCOUNTING.search(t):
            skills = skills + ["accounting-knowledge"]
            merged += ACCOUNTING_SCRIPTS
        for s in scripts:
            if s not in merged:
                merged.append(s)
        scripts = merged

    return {
        "classification": kind,
        "risk": risk,
        "skills": skills,
        "scripts": scripts,
        "api_hint": api,
        "proof_gate": [
            "kg validate before knowledge queries",
            "orchestration XML + processors for behaviour",
            "db-local.sh for DB state",
            "label NOT VERIFIED if no this-turn evidence",
        ],
    }


def cmd_classify(args: argparse.Namespace) -> int:
    text = " ".join(args.words)
    result = classify(text)
    result["input"] = text
    print("## Agent router")
    print(f"**Classification:** {result['classification']}  **Risk:** {result['risk']}")
    if result.get("api_hint"):
        print(f"**API hint:** `{result['api_hint']}`")
    print("\n**Skills to load:**")
    for s in result["skills"]:
        print(f"- `.cursor/skills/{s}/SKILL.md`")
    print("\n**Scripts (in order):**")
    for sc in result["scripts"]:
        print(f"- `{sc}`")
    print("\n**Proof gate:**")
    for p in result["proof_gate"]:
        print(f"- {p}")
    if args.json:
        print("\n--- json ---")
        print(json.dumps(result, indent=2))
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    m = load_manifest()
    print(json.dumps(m, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("classify")
    pc.add_argument("words", nargs="+")
    pc.add_argument("--json", action="store_true")
    sub.add_parser("list")
    args = p.parse_args()
    if args.cmd == "classify":
        return cmd_classify(args)
    if args.cmd == "list":
        return cmd_list(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
