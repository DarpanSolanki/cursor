#!/usr/bin/env python3
"""Mechanical audit: selection vs execution, hang sites, script verdicts."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

CHAIN_BINS = [
    "workspace-close.sh",
    "ship-loop-gate.sh",
    "impact-tests.sh",
    "ntest.sh",
    "stack-doctor.sh",
    "run-guarded.sh",
    "ship-knowledge-gate.sh",
    "push-origin.sh",
    "agent-ops.sh",
]

CHAIN_LIBS = [
    "impact_tests.py",
    "resolve_ship_impact.py",
    "ship_push_gate.py",
    "chain_budgets.py",
    "ship_test_plan.py",
    "resolve_ship_cases.py",
]

WAIT_PATTERNS = [
    (re.compile(r"\bsleep\s+"), "sleep"),
    (re.compile(r"\bwhile\b.*\bwait"), "poll-loop"),
    (re.compile(r"\bpsql\b"), "psql"),
    (re.compile(r"\bcurl\b"), "curl"),
    (re.compile(r"gradlew\b"), "gradle"),
    (re.compile(r"\btimeout\b"), "timeout-cmd"),
    (re.compile(r"subprocess\.(run|Popen|call)"), "subprocess"),
    (re.compile(r"urllib\.request\.urlopen"), "http"),
    (re.compile(r"flock\b|\.lock"), "lock"),
]


def _grep_chain_invokes() -> dict[str, list[str]]:
    edges: dict[str, list[str]] = {}
    bin_dir = ROOT / "scripts/bin"
    for name in CHAIN_BINS:
        p = bin_dir / name
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        calls: list[str] = []
        for m in re.finditer(r'bash\s+"?\$ROOT/scripts/bin/([a-z0-9_.-]+\.sh)"?', text):
            calls.append(m.group(1))
        for m in re.finditer(r'python3\s+"?\$ROOT/scripts/(lib|testing)/([a-z0-9_./-]+\.py)"?', text):
            calls.append(f"{m.group(1)}/{m.group(2)}")
        edges[name] = sorted(set(calls))
    return edges


def _hang_scan(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        if not path.is_file():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for pat, kind in WAIT_PATTERNS:
                if pat.search(line):
                    budget = "derived" if "chain_budgets" in line or "BATCH_POLL" in line or "timeout" in line.lower() else "none"
                    if "sleep 0." in line or "sleep 1" in line or "sleep 2" in line:
                        budget = "fixed-short"
                    rows.append(
                        {
                            "site": f"{path.relative_to(ROOT)}:{i}",
                            "kind": kind,
                            "budget": budget,
                            "verdict": "OK" if budget != "none" else "UNBUDGETED",
                        }
                    )
                    break
    return rows


def selection_vs_executed() -> dict:
    from impact_tests import build_plan  # noqa: WPS433
    from resolve_ship_impact import resolve  # noqa: WPS433

    pending = ROOT / ".cursor/.pending-ship-work.json"
    plan = build_plan(from_pending=True, shipped_only=True)
    selection = set(plan.get("ordered_cases") or [])
    resolved = resolve(ROOT, pending, "", [], True)
    exec_cases = set(resolved.get("ntest_cases") or [])
    only_sel = sorted(selection - exec_cases)
    only_exec = sorted(exec_cases - selection)
    return {
        "selection_n": len(selection),
        "execution_n": len(exec_cases),
        "aligned": selection == exec_cases,
        "only_selection": only_sel,
        "only_execution": only_exec,
        "selection": sorted(selection),
        "execution": sorted(exec_cases),
    }


def main() -> int:
    edges = _grep_chain_invokes()
    scan_paths = [ROOT / "scripts/bin" / n for n in CHAIN_BINS]
    scan_paths += [ROOT / "scripts/lib" / n for n in CHAIN_LIBS]
    hangs = _hang_scan(scan_paths)
    unbudgeted = sum(1 for h in hangs if h["verdict"] == "UNBUDGETED")
    sel = selection_vs_executed()
    out = {
        "chain_edges": edges,
        "hang_total": len(hangs),
        "hang_unbudgeted": unbudgeted,
        "selection_audit": sel,
    }
    print(json.dumps(out, indent=2))
    return 0 if sel.get("aligned") else 2


if __name__ == "__main__":
    sys.exit(main())
