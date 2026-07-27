#!/usr/bin/env python3
"""S-D: sibling closed via full loanRepayment (+ auto-closure) then last-child DFC.

Harness-only. Does not patch product. Documents BLOCKED if PTC/auto-closure prevents close.

Env:
  DCF_FRESH_GROUP=1 (default)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    env = {
        **os.environ,
        "DCF_FRESH_GROUP": os.environ.get("DCF_FRESH_GROUP", "1"),
        "VIKRAM_PATH": "0",
        "SEED_EXTRA": "0",
        "DCF_SEED_EMI_LABD": "0",
        "ACCEPTANCE_STRICT": "1",
        "ACCEPTANCE_SCOPE": "obs123",
        "DCF_E2E_NO_SNAPSHOT": "1",
        # Signal for future e2e hook — today we document and run dual-DFC as control.
        "CHILD1_CLOSE_MODE": "REPAY",
    }
    print("=== S-D repay-close attempt ===")
    print(
        "NOTE: Full SHG child CLOSE via normal EMI/loanRepayment alone is not yet wired "
        "as a first-class path in group_parent_last_child_dfc_local_e2e (needs multi-cycle "
        "EMI + loanAccountAutoClosureBatchJob). QA4 Vikram shape uses FORECLOSURE "
        "(LOAN_PREPAYMENT) for sibling — covered by dcf.vikram_fc_rstcre_dfc_e2e."
    )
    print(
        "STATUS: BLOCKED/HARNESS_GAP — not a proven product defect. "
        "Next: implement real-flow repay-to-zero + auto-closure then last DFC without "
        "soft-passing. Until then run Vikram (FC) + dual-DFC as sibling-close coverage."
    )
    # Self-learn sticky note via stdout for matrix summary; caller may test-learn.
    Path("scripts/scratch/dfc-full-matrix/S_D_repay_close_BLOCKED.txt").write_text(
        "BLOCKED harness gap: repay-to-close sibling before last DCF not implemented as "
        "real-flow yet. QA4 SoT sibling close = FORECLOSURE/LOAN_PREPAYMENT (Vikram).\n"
    )
    return 2  # blocked / not verified


if __name__ == "__main__":
    raise SystemExit(main())
