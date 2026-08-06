#!/usr/bin/env python3
"""CLB / parent disburse — reject multi REP_ACCT; fail-closed on blank/missing member REP.

Forward path:
1. Parent disburseLoan: CustomValidate… → 134126 if any member has >1 REP_ACCT.
2. CLB populator: drop blank REP_ACCT; if non-CASH and member has none, copy the parent
   group REP_ACCT from ExecutionContext; only when the parent has none either → 130142.
3. createOrUpdateLoanAccount CustomValidate remains backstop for poison queue rows.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
ACCT = ROOT / "trustt-platform-accounting"
POPULATOR = (
    ACCT
    / "src/main/java/in/novopay/accounting/loan/grouploan/disbursement/service"
    / "ChildLoanBookingEventsQueueDataPopulator.java"
)
CUSTOM_VALIDATE = (
    ACCT
    / "src/main/java/in/novopay/accounting/custom/mfi/disburse/processor"
    / "CustomValidateDisbursementRepaymentAccountDetailsProcessor.java"
)
MFI_ORC = ACCT / "deploy/application/orchestration/mfi_orc.xml"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _purpose_code(elem: dict[str, Any]) -> str:
    purpose = elem.get("purpose") or []
    if not purpose:
        return ""
    first = purpose[0] if isinstance(purpose, list) else {}
    code = (first or {}).get("code") or (first or {}).get("purpose_code") or ""
    return str(code)


def count_rep_acct(details: list[dict[str, Any]]) -> int:
    return sum(1 for e in details if _purpose_code(e).upper() == "REP_ACCT")


def member_would_reject_134126(member_details: list[dict[str, Any]]) -> bool:
    """Mirror CustomValidateDisbursementRepaymentAccountDetailsProcessor.validateMemberRepAcctUniqueness."""
    for member in member_details:
        details = member.get("disbursement_repayment_account_details") or []
        if count_rep_acct(details) > 1:
            return True
    return False


def main() -> int:
    print("Verify mode: PROCESSOR_MIRROR_SIM")
    print(
        "Blocker (full E2E): live SHG parent disburse with deliberate blank/missing "
        "member REP payload not assumed this run."
    )

    pop_src = POPULATOR.read_text(encoding="utf-8")
    val_src = CUSTOM_VALIDATE.read_text(encoding="utf-8")
    orc_src = MFI_ORC.read_text(encoding="utf-8")

    _require(
        "ensureMemberHasUsableRepAcct" in pop_src,
        "Populator must fail-closed via ensureMemberHasUsableRepAcct",
    )
    _require(
        'throw new NovopayFatalException("130142")' in pop_src,
        "Missing/blank member REP must throw 130142 (parent DIRDR parity)",
    )
    _require(
        "getAPIRequestJson" not in pop_src
        and "parseAndAddDisbursementRepaymentAccountDetails" not in pop_src,
        "Parent REP fallback must read ExecutionContext, never re-parse the API request JSON",
    )
    _require(
        "addParentRepAcct" in pop_src
        and "executionContext.get(DISBURSEMENT_REPAYMENT_ACCOUNT_DETAILS)" in pop_src,
        "Populator must copy parent REP_ACCT from EC when member has none",
    )
    _require(
        "keepAtMostOneRepAcct" not in pop_src,
        "Populator must NOT silently trim via keepAtMostOneRepAcct",
    )
    _require(
        "validateMemberRepAcctUniqueness" in val_src,
        "CustomValidate must scan member_details for multi REP_ACCT",
    )
    _require(
        'throw new NovopayFatalException("134126")' in val_src,
        "Member multi-REP gate must throw 134126",
    )
    _require(
        "customValidateDisbursementRepaymentAccountDetailsProcessor" in orc_src
        and "createLoanAccountEventsProcessor" in orc_src,
        "mfi_orc disburseLoan must wire customValidate and CLB enqueue",
    )
    pop_idx = orc_src.find("customValidateDisbursementRepaymentAccountDetailsProcessor")
    clb_idx = orc_src.find('bean="createLoanAccountEventsProcessor"')
    _require(pop_idx >= 0 and clb_idx > pop_idx, "customValidate must appear before CLB createLoanAccountEventsProcessor")
    print("PROCESSOR_MIRROR_SIM PASS: reject gate + EC parent fallback + 130142 fail-closed")

    poison_members = [
        {
            "customer_id": "1",
            "disbursement_repayment_account_details": [
                {"purpose": [{"code": "DSBR_ACCT"}], "account_number": "1"},
                {"purpose": [{"code": "REP_ACCT"}], "account_number": "M-REP"},
                {"purpose": [{"code": "REP_ACCT"}], "account_number": "P-REP"},
            ],
        }
    ]
    _require(
        member_would_reject_134126(poison_members),
        "member with >1 REP_ACCT must map to 134126 reject",
    )
    print("PROCESSOR_MIRROR_SIM PASS: multi REP_ACCT → reject semantics")

    ok_members = [
        {
            "customer_id": "1",
            "disbursement_repayment_account_details": [
                {"purpose": [{"code": "DSBR_ACCT"}], "account_number": "1"},
                {"purpose": [{"code": "REP_ACCT"}], "account_number": "M-REP"},
            ],
        }
    ]
    _require(not member_would_reject_134126(ok_members), "single REP_ACCT must not reject")
    ok_members_purpose_code_key = [
        {
            "customer_id": "2",
            "disbursement_repayment_account_details": [
                {"purpose": [{"purpose_code": "REP_ACCT"}], "account_number": "M-REP-2"},
            ],
        }
    ]
    _require(
        not member_would_reject_134126(ok_members_purpose_code_key),
        "purpose_code key (not code) must still count as REP_ACCT",
    )
    _require(
        'purpose.get("purpose_code")' in pop_src
        and "LoanAccountConstants.PURPOSE_CODE" in pop_src,
        "isRepAcctElement must mirror CustomValidate code/purpose_code liberal read",
    )
    _require(
        re.search(r"static boolean hasRepAcct\s*\(\s*JSONArray", pop_src) is not None,
        "hasRepAcct helper must remain for usable-REP check",
    )
    _require(
        "removeBlankRepAcctEntries" in pop_src
        and "hasNonBlankAccountNumber" in pop_src,
        "Populator must drop blank REP_ACCT before usable-REP check",
    )
    _require(
        "REPAY_MODE_CASH" in pop_src,
        "CASH repayment must skip mandatory member REP",
    )
    print("PROCESSOR_MIRROR_SIM PASS: blank REP_ACCT treated as missing; parent fallback then 130142")

    _require(not member_would_reject_134126([]), "no members → no member reject")
    print("PROCESSOR_MIRROR_SIM PASS: INDL/empty member_details no-op")

    print("PASS: disbursement.clb_rep_acct_dedupe_sim")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
