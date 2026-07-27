#!/usr/bin/env python3
"""F3 FLOW B — penalInterestAccrualCalculation → Booking (BLOCKED — SU backlog).

Ground truth (2026-07-25 local):
  Batch reader PARTITION_DATA_QUERY requires ACTIVE ∧ past_due_days>0.
  Even after seeding past_due_days≥15 on DCF child 2615865 and quarantining the
  portfolio, the job repeatedly partitions only DPI LAN 8060160 (minId=maxId)
  and writes 0 PIAD rows for the fixture child. Product-scheme / reader join
  eligibility for this SHG bak is unresolved without service-code or a dedicated
  penal fixture — out of F3 workspace-scripts scope.

Exit 2 = harness blocked (not a flake). Capability CHAIN_PENAL remains in
dateroll.py for a future fixture.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))

SU = "SU-FLOW-PENAL-READER-ELIG"
SCOPE = "out"  # permanent user scope cut — WONT-DO
PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD1_LAN", "6000137440")


def main() -> int:
    print("=== flowtest.penal_accrual (F3 FLOW B — BLOCKED) ===")
    print(f"  parent={PARENT} child={CHILD}")
    print(
        f"  BLOCKER: penal calc reader selects DPI LAN 8060160 only; "
        f"0 PIAD on DCF child after seed+quarantine+REAL jobs."
    )
    print(f"  SU: {SU} — need penal-eligible fixture or reader join fix (not F3).")
    print(
        "  LAYERS_DECLARE: jobs=ATTEMPTED(penal_calc,penal_booking) "
        "fixture=INELIGIBLE aging=N/A"
    )
    print("=== BLOCKED: flowtest.penal_accrual ===")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
