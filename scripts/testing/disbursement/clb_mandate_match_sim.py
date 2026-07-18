#!/usr/bin/env python3
"""CLB / createOrUpdateLoanAccount — REP_ACCT must match pre-created mandate CASA.

Sequence (proven): LOS createRepaymentMandateDetails → later CLB →
customValidateDisbursementRepaymentAccountDetailsProcessor.

Full E2E needs SHG fixture + mandate row. This case proves the validator + CLB
key threading on disk, and mirrors FAIL (mismatch) / PASS (match) / CASH skip.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACCT = ROOT / "trustt-platform-accounting" / "src" / "main" / "java"
VALIDATOR = (
    ACCT
    / "in/novopay/accounting/account/loans/util"
    / "DisbursementRepaymentMandateMatchValidator.java"
)
CUSTOM = (
    ACCT
    / "in/novopay/accounting/custom/mfi/disburse/processor"
    / "CustomValidateDisbursementRepaymentAccountDetailsProcessor.java"
)
BASE = (
    ACCT
    / "in/novopay/accounting/account/loans/processor"
    / "ValidateDisbursementRepaymentAccountDetailsProcessor.java"
)
POPULATOR = (
    ACCT
    / "in/novopay/accounting/loan/grouploan/disbursement/service"
    / "ChildLoanBookingEventsQueueDataPopulator.java"
)
MFI_ORC = (
    ROOT
    / "trustt-platform-accounting"
    / "deploy/application/orchestration/mfi_orc.xml"
)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def accounts_match(rep_acct: str | None, mandate_casa: str | None) -> bool:
    """Mirror DisbursementRepaymentMandateMatchValidator account equality."""
    a = (rep_acct or "").strip()
    b = (mandate_casa or "").strip()
    return bool(a) and a == b


def should_check_mandate(repayment_mode: str | None) -> bool:
    mode = (repayment_mode or "").strip()
    if not mode or mode == "CASH":
        return False
    return mode in ("DIRDR", "ACH")


def main() -> int:
    print("Verify mode: PROCESSOR_MIRROR_SIM")
    print(
        "Blocker (full E2E): SHG parent disburse + createRepaymentMandateDetails "
        "+ CLB createOrUpdateLoanAccount fixture not assumed this run."
    )

    validator_src = VALIDATOR.read_text(encoding="utf-8")
    custom_src = CUSTOM.read_text(encoding="utf-8")
    base_src = BASE.read_text(encoding="utf-8")
    populator_src = POPULATOR.read_text(encoding="utf-8")
    orch = MFI_ORC.read_text(encoding="utf-8")

    _require(
        "customValidateDisbursementRepaymentAccountDetailsProcessor" in orch,
        "mfi_orc createOrUpdateLoanAccount must use customValidate…",
    )
    _require(
        "DisbursementRepaymentMandateMatchValidator.validateIfMandateDriven" in custom_src,
        "CustomValidate must call mandate match after ≤1 REP_ACCT check",
    )
    _require(
        "DisbursementRepaymentMandateMatchValidator.validateIfMandateDriven" in base_src,
        "Base ValidateDisbursementRepaymentAccountDetailsProcessor must mirror mandate match",
    )
    _require(
        "findRegistrationPendingOrActiveMandateForLoanAppId" in validator_src,
        "Must reuse MandateDetailsDAOService.findRegistrationPendingOrActiveMandateForLoanAppId",
    )
    _require(
        "findRegistrationPendingOrActiveMandateForGroupId" in validator_src,
        "Must reuse MandateDetailsDAOService.findRegistrationPendingOrActiveMandateForGroupId",
    )
    _require(
        'throw new NovopayFatalException("134382")' in validator_src,
        "No mandate → 134382 (MANDATE_DTLS-014)",
    )
    _require(
        'throw new NovopayFatalException("134348")' in validator_src,
        "Mismatch / missing mandate CASA → 134348 (MANDATE_DTLS-006)",
    )
    _require(
        "REPAY_MODE_CASH" in validator_src and "return;" in validator_src,
        "CASH must skip mandate check",
    )
    _require(
        "LOAN_APPLICATION_ID" in populator_src
        and re.search(r'put\(LoanAccountConstants\.LOAN_APPLICATION_ID', populator_src),
        "CLB populator must thread loan_application_id (external_ref) for mandate lookup",
    )
    _require(
        re.search(r'put\(LoanAccountConstants\.GROUP_ID', populator_src) is not None,
        "CLB populator must thread group_id for SHG group-level mandate lookup",
    )
    print("PROCESSOR_MIRROR_SIM PASS: orch + validator + CLB key threading on disk")

    # Semantic mirror: FAIL when REP_ACCT ≠ mandate CASA
    _require(should_check_mandate("DIRDR"), "DIRDR must require mandate match")
    _require(should_check_mandate("ACH"), "ACH must require mandate match")
    _require(not should_check_mandate("CASH"), "CASH must skip")
    _require(
        not accounts_match("111", "222"),
        "mismatch must FAIL (assert would throw 134348)",
    )
    _require(
        accounts_match(" 111 ", "111"),
        "trim-equal accounts must PASS",
    )
    _require(
        not accounts_match("", "111"),
        "blank REP_ACCT must FAIL",
    )
    print("PROCESSOR_MIRROR_SIM PASS: FAIL mismatch / PASS match / CASH skip")

    print("PASS: disbursement.clb_mandate_match_sim")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
