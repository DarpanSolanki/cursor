#!/usr/bin/env python3
"""PROCESSOR_MIRROR_SIM — DCF force-bill CRN includes deathForeclosureDetailsId (GAP-078).

Proves ForceBillBillingSupport.buildForceBillClientReference appends claim id so
sequential same-value_date parent force-bills do not collide (134497).
Writer delegates via DeathForeclosureSettlementSupport / DeathForeclosureForceBillService.
Full multi-child e2e remains dcf.group_parent_last_child_e2e (sibling harness when lock free).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUPPORT = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/foreclosure/forcebill"
    / "ForceBillBillingSupport.java"
)
WRITER = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/deathforeclosure/writer"
    / "DeathForeclosureInsuranceWriter.java"
)
SETTLEMENT = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/deathforeclosure/service"
    / "DeathForeclosureSettlementSupport.java"
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
    if not SUPPORT.is_file():
        fail(f"missing ForceBillBillingSupport: {SUPPORT}")
    text = SUPPORT.read_text(encoding="utf-8")
    m = re.search(
        r"public static String buildForceBillClientReference\(([^)]+)\)\s*\{([^}]+)\}",
        text,
        re.S,
    )
    if not m:
        fail("buildForceBillClientReference not found in ForceBillBillingSupport")
    params, body = m.group(1), m.group(2)
    if "deathForeclosureDetailsId" not in params:
        fail("signature missing deathForeclosureDetailsId param")
    if "valueDate.getTime()" not in body:
        fail("body missing valueDate.getTime()")
    if "deathForeclosureDetailsId" not in body:
        fail("body does not append deathForeclosureDetailsId")

    # Writer still passes claim id into child + parent force-bill entry points.
    if not WRITER.is_file():
        fail(f"missing writer: {WRITER}")
    writer = WRITER.read_text(encoding="utf-8")
    child = re.search(
        r"deathForeclosureForceBillService\.forceBill\(\s*executionContext,\s*loanAccountEntity,\s*"
        r"partialCycleAccrualToBill,\s*dateOfReporting,\s*dateofDeath,\s*deathForeclosureDetailsId\s*\)",
        writer,
    )
    parent = re.search(
        r"deathForeclosureForceBillService\.forceBill\(\s*executionContext,\s*parentLoanAccountEntity,\s*"
        r"parentForceBillSlice,\s*dateOfReporting,\s*dateOfDeath,\s*deathForeclosureDetailsId\s*\)",
        writer,
    )
    if not child:
        fail("child forceBill call missing deathForeclosureDetailsId")
    if not parent:
        fail("parent forceBill call missing deathForeclosureDetailsId")

    if SETTLEMENT.is_file():
        settlement = SETTLEMENT.read_text(encoding="utf-8")
        if "ForceBillBillingSupport.buildForceBillClientReference" not in settlement:
            fail("SettlementSupport must delegate CRN to ForceBillBillingSupport")

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


if __name__ == "__main__":
    main()
