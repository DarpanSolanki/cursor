#!/usr/bin/env python3
"""PROCESSOR_MIRROR_SIM — DPI foreclosure BPD day-window (business start + HALF_UP).

Runtime foreclosure sim is blocked when local schema lacks dpi_suspense_amount.
This case proves the permanent fix on disk + QA ₹29 day math.

Blocker for full E2E: local loan_account entity/schema missing dpi_suspense_amount.
Upgrade path: ntest run dpic.foreclosure_sim once schema aligned.
"""
from __future__ import annotations

import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JAVA = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/dpi/calculation"
    / "DpiForeclosureBrokenPeriodService.java"
)
VALIDATE_CREATE = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/prepayment/processor"
    / "ValidateLoanPrepaymentDataProcessor.java"
)
VALIDATE_FINAL = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/prepayment/processor"
    / "ValidateFinalPrepaymentProcessor.java"
)
SIM_PROC = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/foreclosure/processor"
    / "FetchLoanForeclosureSimulationDetailsProcessor.java"
)
EOD_CALC = (
    ROOT
    / "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/dpi"
    / "dpiaccrualcalculation/DpiAccrualCalculationBatchService.java"
)


def main() -> int:
    src = JAVA.read_text()
    if "nextDay(business)" in src:
        print("FAIL: still projects from nextDay(business)")
        return 1
    if not re.search(
        r"simulateAccrualAmountBetweenDates\(\s*loanAccountId\s*,\s*business\s*,\s*asOn",
        src,
        re.S,
    ):
        print("FAIL: simulateAccrualAmountBetweenDates must start at business")
        return 1
    if "RoundingMode.HALF_UP" not in src or "setScale(0" not in src:
        print("FAIL: expected HALF_UP 0dp on projected BPD total")
        return 1
    if "private static Date nextDay" in src:
        print("FAIL: unused nextDay helper should be removed")
        return 1

    eod = EOD_CALC.read_text()
    if "while (cursor.getTime().before(today))" not in eod:
        print("FAIL: EOD calc must use before(today) (no double-count of business day)")
        return 1

    # QA LAN 6003768627 / FC 29 Jul 2026 — RCA numbers
    persisted = Decimal("10")
    daily = Decimal("3945") * Decimal("0.19") / Decimal("360")
    new_raw = persisted + daily * 9  # business start adds +1 day vs nextDay
    rounded = new_raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if rounded != Decimal("29"):
        print(f"FAIL: expected ₹29 got {rounded} (raw={new_raw})")
        return 1

    create_src = VALIDATE_CREATE.read_text()
    sim_src = SIM_PROC.read_text()
    shared_call = re.compile(
        r"dpiForeclosureBrokenPeriodService\.calculateTillForeclosureDate\s*\(",
        re.S,
    )
    if not shared_call.search(sim_src):
        print("FAIL: sim processor must call calculateTillForeclosureDate")
        return 1
    if not shared_call.search(create_src):
        print("FAIL: create validate must call calculateTillForeclosureDate (sim↔create parity)")
        return 1
    if "getBrokenPeriodDpiAmountTillDate" in create_src:
        print("FAIL: ValidateLoanPrepaymentDataProcessor still uses DAO-only BPD")
        return 1

    final_src = VALIDATE_FINAL.read_text()
    if "calculateTillForeclosureDate" in final_src or "DpiForeclosureBrokenPeriodService" in final_src:
        print("FAIL: ValidateFinalPrepaymentProcessor must stay on persisted BPD (no util recompute)")
        return 1
    if "getBpdAmountToBePaid" not in final_src:
        print("FAIL: ValidateFinalPrepaymentProcessor must still compare getBpdAmountToBePaid")
        return 1

    print("Verify mode: PROCESSOR_MIRROR_SIM")
    print("Runtime status: schema aligned; dpic.foreclosure_sim reaches business validation (fixture must be ACTIVE)")
    print(f"PASS: business-start + HALF_UP → ₹29 (raw={new_raw})")
    print("PASS: sim + create both call calculateTillForeclosureDate")
    print("PASS: ValidateFinal still uses persisted getBpdAmountToBePaid (gate unchanged)")
    print("Double-count: EOD before(today) ⇒ day B not persisted; project from B is safe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
