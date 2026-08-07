#!/usr/bin/env python3
"""loanAccountExcessAmountRefund DEFAULT -> APPROVE, driven for real against local accounting.

Seeds only the precondition (the loan holds excess). Every asserted row is written by the
API run: loan_account_excess_amount_refund_details, loan_account_payments_details, and the
loan_account.excess_amount drawdown.
"""
from __future__ import annotations

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib_call import hdr, post, psql, st, write_sql  # noqa: E402

REFUND = Decimal(os.environ.get("REFUND_AMOUNT", "500"))
REFUND_MODE = os.environ.get("REFUND_MODE", "TRANSFER_TO_INCOME_GL")
ASSERT_SQL = HERE / "assert_excess_refund.sql"

CANDIDATE_SQL = f"""
SELECT la.la_account_number FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
WHERE la.loan_status='ACTIVE' AND a.status='ACTIVE' AND la.is_deleted=false
  AND lp.excess_amount_refund_allowed=true AND la.refund_allowed=true
  AND la.has_child_accounts=false AND la.parent_loan_account_id IS NULL
  AND COALESCE(lp.minimum_refund_amount,0) <= {REFUND}
  AND NOT EXISTS (SELECT 1 FROM mfi_accounting.loan_account_payments_details p
                  WHERE p.loan_account_id=la.account_id AND p.excess_amount > 0)
  AND NOT EXISTS (SELECT 1 FROM mfi_accounting.loan_account_excess_amount_refund_details r
                  WHERE r.loan_account_id=la.account_id AND r.status='PENDING_FOR_APPR')
ORDER BY la.account_id LIMIT 1
"""


def resolve_lan() -> str:
    """A same-day excess payment row trips the refund lock-in gate (134393), so a LAN is
    single-use per lock-in window. Pick one the gate will let through."""
    lan = os.environ.get("ACCOUNT_NUMBER", "")
    if lan:
        return lan
    lan = psql(CANDIDATE_SQL)
    if not lan:
        raise RuntimeError("no refund-eligible LAN available (all have excess payment rows)")
    return lan


def main() -> int:
    LAN = resolve_lan()
    print(f"=== excess_refund.loan_account_excess_amount_refund_e2e lan={LAN} refund={REFUND} ===")
    aid = psql(
        f"SELECT account_id::text FROM mfi_accounting.loan_account "
        f"WHERE la_account_number='{LAN}' AND is_deleted=false"
    )
    if not aid:
        raise RuntimeError(f"LAN {LAN} not found")

    dues = Decimal(
        psql(
            f"SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)::text "
            f"FROM mfi_accounting.loan_due_details WHERE loan_account_id={aid} AND is_deleted=false "
            f"AND due_date::date<=CURRENT_DATE AND due_amount>paid_amount+waived_amount"
        )
    )
    since_refund_id = psql(
        "SELECT COALESCE(MAX(id),0)::text FROM mfi_accounting.loan_account_excess_amount_refund_details"
    )
    since_lapd_id = psql(
        "SELECT COALESCE(MAX(id),0)::text FROM mfi_accounting.loan_account_payments_details"
    )
    seeded = dues + REFUND
    write_sql(
        f"UPDATE mfi_accounting.loan_account SET excess_amount={seeded}, updated_on=now() "
        f"WHERE account_id={aid};",
        "seed_excess",
    )
    print(f"  fixture: dues_open_today={dues} excess seeded={seeded} (refundable={REFUND})")

    ms = str(int(time.time() * 1000))
    req = {
        "account_number": LAN,
        "refund_effective_date": ms,
        "refund_mode": REFUND_MODE,
        "total_refund_amount": str(REFUND),
        "reason": "OTHR",
        "notes": "excess refund e2e",
    }
    for fc, want in (("DEFAULT", "30421"), ("APPROVE", "30422")):
        r = post(
            "loanAccountExcessAmountRefund",
            {"headers": hdr(f"EXR{fc}{ms}", function_code=fc), "request": req},
        )
        code, status, msg = st(r)
        print(f"  loanAccountExcessAmountRefund {fc}: {code}/{status} {msg}")
        if status != "SUCCESS" or code != want:
            raise RuntimeError(f"{fc} failed: {code}/{status} {msg}")
        time.sleep(2)

    sql = (
        ASSERT_SQL.read_text()
        .replace("${ACCOUNT_NUMBER}", LAN)
        .replace("${SINCE_REFUND_ID}", since_refund_id)
        .replace("${SINCE_LAPD_ID}", since_lapd_id)
    )
    verdict = psql(sql)
    print(f"  db_assert: {verdict}")
    print(
        "  LAYERS_DECLARE: jobs=REAL(loanAccountExcessAmountRefund:DEFAULT,"
        "loanAccountExcessAmountRefund:APPROVE)"
    )
    if verdict != "SUCCESS":
        raise AssertionError(f"excess refund money assert FAILED: {verdict}")
    print("=== PASS: excess_refund.loan_account_excess_amount_refund_e2e ===")
    print(json.dumps({"lan": LAN, "account_id": aid, "refund": str(REFUND)}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, RuntimeError) as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        sys.exit(1)
