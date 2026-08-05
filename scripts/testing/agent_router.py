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
    elif re.search(r"\b(sanity|ntest|test|verify|regression|smoke|batch job|eod|dpi)\b", t):
        kind = "TEST"
        skills = ["workspace-router", "autonomous-workspace-ops"]
        scripts = [
            "scripts/bin/agent-ops.sh before-test <apiName>",
            "scripts/bin/ntest.sh auto <apiName>",
            "scripts/bin/agent-ops.sh on-failure accounting <apiName>",
        ]
        risk = "Medium"
    elif re.search(r"\b(rca|root cause|bug|incident|stuck|fail|error|sdcp|gap)\b", t):
        kind = "BUG/RCA"
        skills = ["workspace-router", "autonomous-workspace-ops"]
        scripts = [
            "python3 cursor-bundle/kg/bin/kg.py orient <apiName>",
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
        scripts = ["grep *Repository.java *DAOService.java before new @Query"]
        risk = "Medium"
    else:
        kind = "GENERAL"
        skills = ["workspace-router"]
        scripts = [
            "python3 cursor-bundle/kg/bin/kg.py validate",
            "python3 cursor-bundle/kg/bin/kg.py orient <apiName>",
        ]
        risk = "Medium"

    api = None
    m = re.search(r"\b(disburseLoan|loanPrepayment|loanRepayment|dpiAccrual\w+|updateCollectionBatchDetails|glBalanceZeroisation)\b", text, re.I)
    if m:
        api = m.group(1)

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
