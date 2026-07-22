#!/usr/bin/env python3
"""TDPQA-102 — code-backed simulation for child loan reopen payment components.

Prefer: full SHG foreclosure → loanAccountReopening APPROVE → child events batch
→ DB assert on loan_account_payments_details for child reversal txn.

When that E2E cannot run (no fixture / checker / events batch), this case proves
the fix on disk by:

1. ORCH_SIBLING_SIM — childLoanReopening must include the same payment-details +
   tax reversal processors as parent loanAccountReopening approve path
   (real XML on disk).
2. PROCESSOR_MIRROR_SIM — LoanAccountPaymentsDetailsReversalProcessor still copies
   the component amount fields the UI reads (parsed from Java, not guessed).

Verify mode labels printed for ship / JIRA honesty.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/testing"))

from lib.orch_sibling_parity import (  # noqa: E402
    assert_copy_fields_present,
    assert_sibling_contains_required,
)

ACCT = ROOT / "trustt-platform-accounting"
LOANS_ORC = ACCT / "deploy/application/orchestration/loans_orc.xml"
GROUP_ORC = ACCT / "deploy/application/orchestration/group_mfi_orc.xml"
PAYMENTS_REV_JAVA = (
    ACCT
    / "src/main/java/in/novopay/accounting/loan/reopening/processor"
    / "LoanAccountPaymentsDetailsReversalProcessor.java"
)

# Beans that populate loan_account_payments_details components on reopen reverse txn.
# Proven on parent path (commit cdd7f1ffe / loans_orc loanAccountReopening APPROVE).
REQUIRED_REOPEN_TAIL = [
    "initiateClosureTaxReversalProcessor",
    "loanAccountPaymentsDetailsReversalProcessor",
]

# Component amount fields the transaction-entry / payments-details row exposes.
# Must match setters in LoanAccountPaymentsDetailsReversalProcessor.copyUnchangedFields.
COMPONENT_COPY_FIELDS = [
    "PrincipalAmount",
    "InterestAmount",
    "PenaltyAmount",
    "FeeAmount",
    "ExcessAmount",
    "Amount",
]


def main() -> int:
    blockers = [
        "Full SHG reopen E2E needs foreclosed parent+child LANs + checker APPROVE "
        "+ childLoanEvents batch — not assumed available this run.",
    ]
    print("Verify mode: ORCH_SIBLING_SIM + PROCESSOR_MIRROR_SIM")
    print("Blocker (full E2E):", blockers[0])

    result = assert_sibling_contains_required(
        parent_xml=LOANS_ORC,
        parent_request="loanAccountReopening",
        child_xml=GROUP_ORC,
        child_request="childLoanReopening",
        required_beans=REQUIRED_REOPEN_TAIL,
    )
    print("ORCH_SIBLING_SIM PASS:", result)

    found = assert_copy_fields_present(PAYMENTS_REV_JAVA, COMPONENT_COPY_FIELDS)
    print("PROCESSOR_MIRROR_SIM PASS: copy fields", found)

    print("PASS: reopening.child_payments_parity_sim (TDPQA-102)")
    print(
        "Upgrade path: add reopening.child_e2e when SHG fixture + events batch "
        "can assert lapd rows for child reversal txn_ref."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — surface fail clearly for ntest
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
