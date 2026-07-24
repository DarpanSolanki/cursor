#!/usr/bin/env python3
"""F4 FLOW C — waiveLoanAccountCharges BLOCKED (document contract tax).

Ground truth: webapp Request is waiveLoanAccountCharges (KG). Live DEFAULT fails
through document validator chain (132368 → is_fully_waived → version →
number_of_files) without a DMS upload harness. WITHOUT_MAKER_CHECKER invalid.
Cut to SU-FLOW-WAIVER-DOC rather than invent document upload in F4.
"""
from __future__ import annotations

import os
import sys

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD1_LAN", "6000137440")
SU = "SU-FLOW-WAIVER-DOC"


def main() -> int:
    print("=== flowtest.waiver_charges (F4 FLOW C — BLOCKED) ===")
    print(f"  parent={PARENT} child={CHILD}")
    print(
        "  BLOCKER: waiveLoanAccountCharges DEFAULT requires document_details "
        "with version + number_of_files (DMS upload) — no local harness; "
        "WITHOUT_MAKER_CHECKER=11013 Invalid function_sub_code."
    )
    print(f"  SU: {SU}")
    print("  LAYERS_DECLARE: dues=N/A waive=ATTEMPTED docs=MISSING")
    print("=== BLOCKED: flowtest.waiver_charges ===")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
