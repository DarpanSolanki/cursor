#!/usr/bin/env python3
"""Non-interactive universal invariants gate runner.

Runs the universal invariant sweep against a healthy LAN fixture baseline.
This is gate content (runtime safety), not the R0 detector self-proofs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/testing"))

from flowtest.invariants import run_universal_invariants  # noqa: E402


def _default_lans() -> list[str]:
    vals: list[str] = []
    for k in ("PARENT_LAN", "CHILD_LAN", "CHILD1_LAN", "CHILD2_LAN", "LAN"):
        v = (os.environ.get(k) or "").strip()
        if v and v not in vals:
            vals.append(v)
    if vals:
        return vals
    # Healthy local fixture defaults used across flowtest scenarios.
    return ["6000137433", "6000137440"]


def main() -> int:
    lans = _default_lans()
    verdict = run_universal_invariants(
        lans, baseline=None, label="flowtest.invariants_universal.gate", absolute_only=True
    )
    if verdict.get("skipped"):
        print(
            "FAIL: flowtest.invariants_universal was SKIPPED "
            f"({verdict.get('label')}) — relax flags never produce a Pass",
            file=sys.stderr,
        )
        return 1
    print(f"PASS: flowtest.invariants_universal gate lans={lans}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
