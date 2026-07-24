#!/usr/bin/env python3
"""Fail-closed: harness_ready=YES only when registry expects PASS/PARTIAL (green).

Convention was insufficient (F4 notes). Cheapest enforcement for doctor / ntest validate.
Exit 0 OK, 1 FAIL, 2 WARN-only mode.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COV = ROOT / "scripts/testing/flow_coverage.json"
REG = ROOT / "scripts/testing/registry.json"


def check(*, warn_only: bool = False) -> int:
    cov = json.loads(COV.read_text(encoding="utf-8"))
    reg = json.loads(REG.read_text(encoding="utf-8"))
    bad: list[str] = []
    for row in cov.get("flows") or []:
        ready = (row.get("harness_ready") or "").upper()
        if ready != "YES":
            continue
        key = row.get("registry")
        if not key:
            bad.append(f"{row.get('flow')}: YES but registry=null")
            continue
        case = reg.get(key) or {}
        expect = (case.get("expect") or {}).get("status") or ""
        if str(expect).upper() not in ("PASS", "PARTIAL"):
            bad.append(
                f"{row.get('flow')}: YES but registry {key} expect.status={expect!r} "
                f"(must be PASS/PARTIAL after green fresh run)"
            )
    if not bad:
        print("OK flow_coverage YES↔registry expect PASS/PARTIAL")
        return 0
    for b in bad:
        print(("WARN " if warn_only else "FAIL ") + b)
    return 2 if warn_only else 1


if __name__ == "__main__":
    warn = "--warn" in sys.argv
    raise SystemExit(check(warn_only=warn))
