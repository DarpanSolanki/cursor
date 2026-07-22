#!/usr/bin/env python3
"""SDCP-11085 / TDPQA-127 — processor-mirror sim for SHG child sanction_date.

Full E2E needs parent+child SHG disburse + CLB batch on a fixture LAN.
This case proves the write-path fix on disk:

1. PROCESSOR_MIRROR_SIM — ChildLoanBookingEventsQueueDataPopulator puts
   sanction_date via getMemberOrParentValue (member first, else parent EC).
2. PROCESSOR_MIRROR_SIM — CreateLoanAccountProcessor still reads EC
   sanction_date and persists when non-null.
3. Flatten path — GroupLoanUtility.populateExecutionContextWithUpdatedData
   recurses JSONObject (so loan_details.sanction_date reaches top-level EC).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACCT = ROOT / "trustt-platform-accounting"
POPULATOR = (
    ACCT
    / "src/main/java/in/novopay/accounting/loan/grouploan/disbursement/service"
    / "ChildLoanBookingEventsQueueDataPopulator.java"
)
CREATE = (
    ACCT
    / "src/main/java/in/novopay/accounting/account/loans/processor"
    / "CreateLoanAccountProcessor.java"
)
UTILITY = (
    ACCT
    / "src/main/java/in/novopay/accounting/loan/grouploan/utility"
    / "GroupLoanUtility.java"
)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    print("Verify mode: PROCESSOR_MIRROR_SIM")
    print(
        "Blocker (full E2E): SHG parent+child disburse + childLoanEventProcessingBatchJob "
        "fixture not assumed this run."
    )

    pop = POPULATOR.read_text(encoding="utf-8")
    _require(
        'getMemberOrParentValue(memberDetails, executionContext, "sanction_date")' in pop,
        "Populator must resolve sanction_date via getMemberOrParentValue (member then parent)",
    )
    _require(
        'loanDetails.put("sanction_date"' in pop,
        "Populator must put sanction_date into loan_details for createLoanAccountRequest",
    )
    # Only stamp when present — do not invent INDL dates when LOS never sent one.
    _require(
        re.search(
            r'sanctionDate\s*=\s*getMemberOrParentValue[\s\S]*?'
            r'if\s*\(\s*sanctionDate\s*!=\s*null\s*&&\s*!sanctionDate\.isBlank\(\)\s*\)',
            pop,
        )
        is not None,
        "Populator must put sanction_date only when non-blank",
    )
    print("PROCESSOR_MIRROR_SIM PASS: ChildLoanBookingEventsQueueDataPopulator sanction_date")

    create = CREATE.read_text(encoding="utf-8")
    _require(
        'executionContext.getValue("sanction_date", String.class)' in create,
        "CreateLoanAccountProcessor must read EC sanction_date",
    )
    _require(
        "setSanctionDate(new Date(Long.parseLong(sanctionDate)))" in create,
        "CreateLoanAccountProcessor must persist sanction_date as epoch millis",
    )
    print("PROCESSOR_MIRROR_SIM PASS: CreateLoanAccountProcessor sanction_date persist")

    util = UTILITY.read_text(encoding="utf-8")
    _require(
        "value instanceof JSONObject" in util
        and "populateExecutionContextWithUpdatedData(executionContext, jsonValue)" in util,
        "GroupLoanUtility must flatten nested JSONObject into EC (loan_details.sanction_date)",
    )
    print("PROCESSOR_MIRROR_SIM PASS: GroupLoanUtility nested flatten")

    print("PASS: disbursement.child_sanction_date_sim (SDCP-11085)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
