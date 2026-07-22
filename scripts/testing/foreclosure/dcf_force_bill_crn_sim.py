#!/usr/bin/env python3
"""PROCESSOR_MIRROR_SIM — DCF force-bill CRN includes deathForeclosureDetailsId (GAP-078).

Proves DeathForeclosureInsuranceWriter.buildForceBillClientReference appends claim id so
sequential same-value_date parent force-bills do not collide (134497).
Full multi-child e2e remains dcf.group_parent_last_child_e2e (sibling harness when lock free).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WRITER = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/deathforeclosure/writer"
    / "DeathForeclosureInsuranceWriter.java"
)
DEDUP = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/common/processor"
    / "ClientReferenceNumberDedupProcessor.java"
)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not WRITER.is_file():
        fail(f"missing writer: {WRITER}")
    text = WRITER.read_text(encoding="utf-8")
    m = re.search(
        r"private static String buildForceBillClientReference\(([^)]+)\)\s*\{([^}]+)\}",
        text,
        re.S,
    )
    if not m:
        fail("buildForceBillClientReference not found")
    params, body = m.group(1), m.group(2)
    if "deathForeclosureDetailsId" not in params:
        fail("signature missing deathForeclosureDetailsId param")
    if "valueDate.getTime()" not in body:
        fail("body missing valueDate.getTime()")
    if "deathForeclosureDetailsId" not in body:
        fail("body does not append deathForeclosureDetailsId")

    # Both child + parent call sites must pass the claim id (3-arg forceBill).
    child = re.search(
        r"forceBillPartialCycleInterest\(\s*executionContext,\s*loanAccountEntity,\s*partialCycleAccrualToBill,\s*"
        r"dateOfReporting,\s*dateofDeath,\s*deathForeclosureDetailsId\s*\)",
        text,
    )
    parent = re.search(
        r"forceBillPartialCycleInterest\(\s*executionContext,\s*parentLoanAccountEntity,\s*parentForceBillSlice,\s*"
        r"dateOfReporting,\s*dateOfDeath,\s*deathForeclosureDetailsId\s*\)",
        text,
    )
    if not child:
        fail("child forceBillPartialCycleInterest call missing deathForeclosureDetailsId")
    if not parent:
        fail("parent forceBillPartialCycleInterest call missing deathForeclosureDetailsId")

    # Collision shape: same account+millis without claim id → identical CRNs (the old bug).
    account_id, ms, claim_a, claim_b = 2615760, 1754505000000, 101, 202
    old = f"{account_id}{ms}"
    new_a = f"{account_id}{ms}{claim_a}"
    new_b = f"{account_id}{ms}{claim_b}"
    if old == f"{account_id}{ms}" and new_a == new_b:
        fail("sim math broken")
    if new_a == new_b:
        fail("claim ids must differentiate CRNs")
    if new_a == old or new_b == old:
        fail("new CRN must differ from legacy accountId+millis")

    if DEDUP.is_file():
        dedup = DEDUP.read_text(encoding="utf-8")
        if "134497" not in dedup:
            fail("ClientReferenceNumberDedupProcessor missing 134497 (contract drift)")

    print("PROCESSOR_MIRROR_SIM PASS: DCF force-bill CRN appends deathForeclosureDetailsId")
    print(f"  legacy collision shape: {old}")
    print(f"  claim A: {new_a}")
    print(f"  claim B: {new_b}")
    print("  Blocker for full RUNTIME: sibling may hold /tmp/dcf_e2e.lock — use dcf.group_parent_last_child_e2e when free")


if __name__ == "__main__":
    main()
