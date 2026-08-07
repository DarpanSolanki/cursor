#!/usr/bin/env python3
"""childLoanTransactionReversal driven for real through childLoanEventProcessingBatchJob.

Real: the loanRepayment that creates the appropriation, and the batch job that dispatches
childLoanTransactionReversal (LoanAccountEventsQueueEntity.EVENT_TYPE_ORC_API_MAP TXNREV).
Fixture: the TXNREV queue row, built from the columns the real repayment wrote, in the exact
shape ChildLoanTransactionReversalEventsQueueDataPopulator emits.
"""
from __future__ import annotations

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts/testing"))

from lib_call import hdr, post, psql, st, write_sql  # noqa: E402
from flowtest.runner import fire_batch, max_batch_execution_id, wait_batch  # noqa: E402

CHILD = os.environ.get("CHILD_LAN", "6004087126")
PARENT = os.environ.get("PARENT_LAN", "6004087025")
ASSERT_SQL = HERE / "assert_child_txn_reversal.sql"


def _values(rows: list[str], casts: tuple[str, ...]) -> str:
    out = []
    for row in rows:
        if not row.strip():
            continue
        parts = row.split("|")
        out.append("(" + ",".join(f"{p}::{c}" for p, c in zip(parts, casts)) + ")")
    if not out:
        raise RuntimeError("empty baseline")
    return ",".join(out)


def main() -> int:
    print(f"=== reversal.child_txn_reversal_e2e parent={PARENT} child={CHILD} ===")
    cid = psql(
        f"SELECT account_id::text FROM mfi_accounting.loan_account "
        f"WHERE la_account_number='{CHILD}' AND is_deleted=false"
    )
    pid = psql(
        f"SELECT account_id::text FROM mfi_accounting.loan_account "
        f"WHERE la_account_number='{PARENT}' AND is_deleted=false"
    )
    if not cid or not pid:
        raise RuntimeError(f"child/parent not resolved: child={cid} parent={pid}")

    dues_baseline = _values(
        psql(
            f"SELECT id||'|'||paid_amount||'|'||waived_amount FROM mfi_accounting.loan_due_details "
            f"WHERE loan_account_id={cid} AND is_deleted=false ORDER BY id"
        ).splitlines(),
        ("bigint", "numeric", "numeric"),
    )
    inst_baseline = _values(
        psql(
            f"SELECT id||'|'||settled_amount FROM mfi_accounting.loan_installment_details "
            f"WHERE loan_account_id={cid} AND is_deleted=false ORDER BY id"
        ).splitlines(),
        ("bigint", "numeric"),
    )
    print("  baseline captured: dues + installments (pre-repayment)")

    amount = Decimal(os.environ.get("REPAY_AMOUNT", "0")) or (
        Decimal(
            psql(
                f"SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)::text "
                f"FROM mfi_accounting.loan_due_details WHERE loan_account_id={cid} "
                f"AND is_deleted=false AND due_date::date<=CURRENT_DATE "
                f"AND due_amount>paid_amount+waived_amount"
            )
        )
        * Decimal("0.6")
    ).quantize(Decimal("1"))
    if amount <= 0:
        raise RuntimeError(f"no open dues on {CHILD} to repay")

    ms = str(int(time.time() * 1000))
    crn = f"CTRREP{int(time.time())}"
    header = hdr(f"CTR{ms}", function_sub_code="WITHOUT_MAKER_CHECKER")
    header["actor_type"] = "CUSTOMER"
    r = post(
        "loanRepayment",
        {
            "headers": header,
            "request": {
                "loan_repayment_details": {
                    "account_number": CHILD,
                    "repayment_amount": str(amount),
                    "repayment_time": ms,
                    "value_date": ms,
                    "repayment_mode": "CASH",
                    "receipt_number": crn,
                    "client_reference_number": crn,
                }
            },
        },
    )
    code, status, msg = st(r)
    print(f"  loanRepayment {amount}: {code}/{status} {msg}")
    if status != "SUCCESS":
        raise RuntimeError(f"loanRepayment failed: {code}/{status} {msg}")
    time.sleep(2)

    lapd_id = psql(
        f"SELECT id::text FROM mfi_accounting.loan_account_payments_details "
        f"WHERE client_reference_number='{crn}' ORDER BY id DESC LIMIT 1"
    )
    if not lapd_id:
        raise RuntimeError(f"no payment row for {crn}")
    cols = psql(
        f"SELECT transaction_reference_number||'|'||client_reference_number||'|'||amount||'|'"
        f"||principal_amount||'|'||interest_amount||'|'||penalty_amount||'|'||fee_amount||'|'"
        f"||excess_amount||'|'||(EXTRACT(EPOCH FROM value_date)*1000)::bigint "
        f"FROM mfi_accounting.loan_account_payments_details WHERE id={lapd_id}"
    ).split("|")
    ref, pay_crn, amt, prin, intr, pen, fee, exc, vdate = cols
    print(f"  repayment wrote lapd={lapd_id} ref={ref} prin={prin} int={intr}")

    rev_ms = str(int(time.time() * 1000))
    payload = json.dumps(
        [
            {
                "transaction_reference_no": ref,
                "transaction_reversal_date": rev_ms,
                "channel_code": "WEB",
                "reason": "OTHR",
                "client_reference_number": pay_crn,
                "reversal_created_by": "SYSTEM",
                "account_number": CHILD,
                "reversal_created_on": rev_ms,
                "transaction_value_date": vdate,
                "transaction_amount": amt,
                "interest_amount": intr,
                "principal_amount": prin,
                "penalty_amount": pen,
                "fee_amount": fee,
                "excess_amount": exc,
            }
        ]
    ).replace("'", "''")
    write_sql(
        f"INSERT INTO mfi_accounting.loan_account_events_queue "
        f"(parent_account_id, data, event_type, event_status, is_deleted, created_by, created_on, "
        f"updated_by, updated_on) VALUES ({pid}, '{payload}', 'TXNREV', 'P', false, "
        f"'flowtest', now(), 'flowtest', now());",
        "seed_txnrev",
    )
    qid = psql(
        f"SELECT MAX(id)::text FROM mfi_accounting.loan_account_events_queue "
        f"WHERE parent_account_id={pid} AND event_type='TXNREV'"
    )
    print(f"  TXNREV queue row seeded id={qid}")

    before = max_batch_execution_id("childLoanEventProcessingBatchJob")
    fire_batch("childLoanEventProcessingBatchJob")
    wait_batch("childLoanEventProcessingBatchJob", before, timeout_s=240)
    time.sleep(3)

    sql = (
        ASSERT_SQL.read_text()
        .replace("${CHILD_LAN}", CHILD)
        .replace("${DUES_BASELINE}", dues_baseline)
        .replace("${INST_BASELINE}", inst_baseline)
        .replace("${QUEUE_ID}", qid)
        .replace("${ORIG_LAPD_ID}", lapd_id)
    )
    verdict = psql(sql)
    print(f"  db_assert: {verdict}")
    print("  LAYERS_DECLARE: jobs=REAL(loanRepayment,childLoanEventProcessingBatchJob>childLoanTransactionReversal)")
    if verdict != "SUCCESS":
        raise AssertionError(f"child reversal money assert FAILED: {verdict}")
    print("=== PASS: reversal.child_txn_reversal_e2e ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, RuntimeError) as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        sys.exit(1)
