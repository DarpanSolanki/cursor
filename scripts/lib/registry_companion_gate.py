#!/usr/bin/env python3
"""Registry / runbook companion gate — money ships must keep suite docs aligned with code.

Centralizes checks previously duplicated in enrichment-audit.sh and ship-knowledge-gate.sh.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CHANGELOG = ROOT / "cursor-bundle/brain/changelog/CHANGELOG.md"
REGISTRY = ROOT / "scripts/testing/registry.json"
RUNBOOK_DCF = ROOT / "cursor-bundle/brain/runbooks/sdcp-10199-group-parent-last-child-dfc.md"
GAPS = ROOT / ".cursor/gaps-and-risks.md"
E2E = ROOT / "scripts/dcf_sanity/group_parent_last_child_dfc_local_e2e.py"

# Registry/runbook must not claim last-child-only parent FB when code is any-child (9b6454df6).
STALE_NOTE_PATTERNS = (
    re.compile(r"parent\s+FB.*last[- ]child\s+only", re.I),
    re.compile(r"force[- ]bill.*last[- ]child\s+only", re.I),
    re.compile(r"only\s+last[- ]child.*parent\s+FB", re.I),
)

DCF_KG_KEYS = (
    "DeathForeclosure",
    "deathForeclosure",
    "loanDeathForeclosure",
    "DFC",
    "EXTRA",
    "labd",
    "force-bill",
    "force_bill",
)


def _top_kg_flow_block(changelog_text: str) -> str:
    m = re.search(r"^## .+?\| kg-flow \|.*?(?=^## |\Z)", changelog_text, re.M | re.S)
    return m.group(0) if m else changelog_text[:2000]


def _is_dcf_kg_flow(block: str) -> bool:
    return any(k in block for k in DCF_KG_KEYS)


def check_stale_note_patterns(registry_note: str, runbook_text: str) -> list[str]:
    errors: list[str] = []
    for pat in STALE_NOTE_PATTERNS:
        if pat.search(registry_note):
            errors.append(f"registry note stale pattern: {pat.pattern!r}")
        if pat.search(runbook_text):
            errors.append(f"runbook stale pattern: {pat.pattern!r}")
    return errors


def check_dcf_companion(*, hard: bool = False) -> list[str]:
    if not CHANGELOG.is_file():
        return []
    block = _top_kg_flow_block(CHANGELOG.read_text(encoding="utf-8", errors="replace"))
    if not _is_dcf_kg_flow(block):
        return []

    errors: list[str] = []
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.is_file() else {}
    note = (reg.get("dcf.group_parent_last_child_e2e") or {}).get("note") or ""
    acc_note = ((reg.get("dcf.group_parent_last_child_e2e") or {}).get("acceptance") or {}).get("note") or ""
    rb = RUNBOOK_DCF.read_text(encoding="utf-8", errors="replace") if RUNBOOK_DCF.is_file() else ""
    gaps = GAPS.read_text(encoding="utf-8", errors="replace") if GAPS.is_file() else ""

    if any(k in block for k in ("EXTRA", "labd", "A2", "force-bill", "force_bill")):
        if not any(k in note for k in ("EXTRA", "labd", "A2", "non-last", "parent FB")):
            errors.append("registry dcf.group_parent_last_child_e2e note missing A2/EXTRA/labd/non-last markers")
        if "EXTRA" not in rb or "labd" not in rb:
            errors.append("runbook sdcp-10199 missing A2 EXTRA / B labd section")
        if "non-last" not in rb and "non-last" not in note:
            errors.append("runbook/registry missing non-last child DFC scenario (code supports any-child parent FB)")
        if "GAP-075" not in gaps and "EXTRA-net" not in gaps:
            errors.append("gaps missing GAP-075 / EXTRA-net RESOLVED row")
    elif any(k in block for k in ("DeathForeclosure", "deathForeclosure", "loanDeathForeclosure")):
        if "dcf.group_parent_last_child_e2e" not in REGISTRY.read_text(encoding="utf-8", errors="replace"):
            errors.append("DCF kg-flow but registry missing dcf.group_parent_last_child_e2e")
        if not RUNBOOK_DCF.is_file():
            errors.append("DCF kg-flow but sdcp-10199 runbook missing")

    errors.extend(check_stale_note_patterns(note + " " + acc_note, rb))

    if hard and E2E.is_file():
        src = E2E.read_text(encoding="utf-8", errors="replace")
        for bad in ('"  OK A2 netting', "'  OK A2 netting", "allow prin > amount", "prin > amount is OK"):
            if bad in src:
                errors.append(f"e2e reintroduced passing anti-pattern: {bad!r}")
        if "ACCEPTANCE_STRICT" not in src:
            errors.append("e2e missing ACCEPTANCE_STRICT gate")
    return errors


def check(*, hard: bool = False) -> int:
    errors = check_dcf_companion(hard=hard)
    if errors:
        print("registry-companion FAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("registry-companion PASS")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Registry/runbook companion gate")
    p.add_argument("cmd", nargs="?", default="check", choices=["check"])
    p.add_argument("--hard", action="store_true", help="Include e2e anti-pattern scan (money close)")
    args = p.parse_args()
    return check(hard=args.hard)


if __name__ == "__main__":
    raise SystemExit(main())
