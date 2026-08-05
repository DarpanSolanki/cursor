#!/usr/bin/env python3
"""TDPQA-72: assert the group parent closes when its last remaining member forecloses.

Before the last-child branch existed, parentLoanAccountPartPrepayment still rescheduled. With no
principal left EquatedRepaymentScheduleGenerator threw 134203, stranding the member in
FORECLOSURE_FREEZE and the parent in FORECLOSURE_FREEZE_RSCH. This asserts the settled contract:
the parent still posts its RSCH mirror, nets to zero, and closes — and no schedule is regenerated.

Usage: assert_last_child_parent_closure.py --child-lan 6004169927
"""
from __future__ import annotations

import argparse
import os
import subprocess
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB = os.path.join(ROOT, "scripts", "db-local.sh")


def q(sql: str) -> list[list[str]]:
    out = subprocess.run([DB, "--sql", sql], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit(f"db-local failed: {out.stderr.strip()[:400]}")
    rows = []
    for line in out.stdout.splitlines():
        stripped = line.strip()
        if not stripped or set(stripped) <= set("-+") or stripped.startswith("("):
            continue
        rows.append([c.strip() for c in line.split("|")])
    return rows[1:] if rows else []


def one(sql: str) -> list[str] | None:
    rows = q(sql)
    return rows[0] if rows else None


def dec(value: str | None) -> Decimal:
    if value is None or value == "" or value.lower() == "null":
        return Decimal(0)
    return Decimal(value)


def txn_reference(transaction_id: str | None) -> str | None:
    if not transaction_id:
        return None
    row = one(f"SELECT reference_number FROM mfi_accounting.transaction_master WHERE id={transaction_id}")
    return row[0] if row else None


def payment_row_for(loan_account_id: str, reference_number: str | None) -> list[str] | None:
    """Pick the payment row written by a specific posting.

    Yugabyte hands out ids from cached sequence blocks, so `ORDER BY id DESC` does not mean
    "most recent" — a row created earlier can carry a higher id. Selecting the tip that way made
    this assert compare the group closure against whichever child row happened to win the id
    race. Anchor on the posting's own reference instead.
    """
    columns = "amount, principal_amount, interest_amount, COALESCE(fee_amount,0)"
    if reference_number:
        row = one(f"SELECT {columns} FROM mfi_accounting.loan_account_payments_details "
                  f"WHERE loan_account_id={loan_account_id} "
                  f"AND transaction_reference_number='{reference_number}' LIMIT 1")
        if row:
            return row
    return one(f"SELECT {columns} FROM mfi_accounting.loan_account_payments_details "
               f"WHERE loan_account_id={loan_account_id} ORDER BY created_on DESC, id DESC LIMIT 1")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--child-lan", required=True)
    args = ap.parse_args()
    child = args.child_lan
    failures: list[str] = []

    def ck(name: str, ok: bool, expected, actual, why: str = "") -> None:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}: expected={expected} actual={actual}"
              + (f"  ({why})" if why and not ok else ""))
        if not ok:
            failures.append(name)

    row = one(
        "SELECT pa.account_number, pa.id, a.id FROM mfi_accounting.account a "
        "JOIN mfi_accounting.account pa ON pa.id=a.parent_account_id "
        f"WHERE a.account_number='{child}'")
    if not row:
        raise SystemExit(f"FAIL: no parent for child {child}")
    parent, parent_id, child_id = row[0], row[1], row[2]
    print(f"child={child} parent={parent}")

    siblings = one(
        "SELECT COUNT(*) FROM mfi_accounting.loan_account "
        f"WHERE parent_loan_account_id={parent_id} AND account_id != {child_id} "
        "AND loan_status='ACTIVE' AND is_deleted=false")
    ck("fixture.child_was_last_active", dec(siblings[0]) == 0, 0, siblings[0],
       "this assert only means anything when no other member was still active")

    child_state = one(
        "SELECT la.loan_status, a.status FROM mfi_accounting.loan_account la "
        f"JOIN mfi_accounting.account a ON a.id=la.account_id WHERE la.la_account_number='{child}'")
    ck("child.loan_status", child_state[0] == "CLOSED", "CLOSED", child_state[0],
       "134203 leaves the last member stranded in FORECLOSURE_FREEZE")
    ck("child.account_status", child_state[1] == "CLOSED", "CLOSED", child_state[1])

    parent_state = one(
        "SELECT la.loan_status, a.status, la.la_closing_date FROM mfi_accounting.loan_account la "
        f"JOIN mfi_accounting.account a ON a.id=la.account_id WHERE la.la_account_number='{parent}'")
    ck("parent.loan_status", parent_state[0] == "CLOSED", "CLOSED", parent_state[0],
       "the group loan must close with its last member, not sit in FORECLOSURE_FREEZE_RSCH")
    ck("parent.account_status", parent_state[1] == "CLOSED", "CLOSED", parent_state[1])
    ck("parent.closing_date_set", bool(parent_state[2]) and parent_state[2].lower() != "null",
       "a date", parent_state[2] or "NULL")

    open_prin = one(
        "SELECT COALESCE(SUM(due_amount - paid_amount - COALESCE(waived_amount,0)),0) "
        f"FROM mfi_accounting.loan_due_details WHERE loan_account_id={parent_id} "
        "AND component_type='PRIN' AND is_deleted=false")
    ck("parent.open_principal_zero", dec(open_prin[0]) == 0, 0, open_prin[0],
       "the parent must net to zero once the last member has settled")

    rsch = one(
        "SELECT COUNT(*) FROM mfi_accounting.transaction_partition_details p "
        "JOIN mfi_accounting.transaction_master tm ON tm.id=p.transaction_id "
        "JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id "
        f"WHERE p.account_number='{parent}' AND tc.type='RSCH_LOAN_PREPAYMENT' AND tm.status='SUCCESS'")
    members_closed = one(
        "SELECT COUNT(*) FROM mfi_accounting.loan_account "
        f"WHERE parent_loan_account_id={parent_id} AND is_deleted=false AND loan_status='CLOSED'")
    ck("parent.rsch_posted_per_member", dec(rsch[0]) == dec(members_closed[0]),
       members_closed[0], rsch[0],
       "closure must still post the parent RSCH mirror, not skip it with the reschedule")

    pending = one(
        "SELECT COUNT(*) FROM mfi_accounting.loan_account_reschedule_details "
        f"WHERE loan_account_id={parent_id} AND batch_status='PENDING'")
    ck("parent.no_pending_reschedule", dec(pending[0]) == 0, 0, pending[0],
       "closure must not leave a reschedule queued against a closed loan")

    # The closure branch writes the group payment row from EC amounts, not from the posting it
    # just made. Reconcile every money column against that posting's own legs so a wrong EC key
    # (interest_amount fed from the wrong source) fails here instead of reaching QA.
    # One RSCH posting per closed member, and ids are not ordered by recency on Yugabyte.
    # The closure mirror carries the originating member (<child crn>_<child lan>), so match that.
    txn = one(
        "SELECT tm.id FROM mfi_accounting.transaction_partition_details p "
        "JOIN mfi_accounting.transaction_master tm ON tm.id=p.transaction_id "
        "JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id "
        f"WHERE p.account_number='{parent}' AND tc.type='RSCH_LOAN_PREPAYMENT' "
        f"AND tm.status='SUCCESS' AND tm.client_reference_number LIKE '%\\_{child}' "
        "ORDER BY tm.id DESC LIMIT 1") or one(
        "SELECT tm.id FROM mfi_accounting.transaction_partition_details p "
        "JOIN mfi_accounting.transaction_master tm ON tm.id=p.transaction_id "
        "JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id "
        f"WHERE p.account_number='{parent}' AND tc.type='RSCH_LOAN_PREPAYMENT' "
        "AND tm.status='SUCCESS' ORDER BY tm.transaction_date DESC, tm.id DESC LIMIT 1")
    if not txn:
        ck("parent.closure_posting_present", False, "a SUCCESS RSCH posting", "ABSENT")
        return 1
    legs = {
        r[0]: dec(r[1])
        for r in q("SELECT reference_code, amount FROM mfi_accounting.transaction_partition_details "
                   f"WHERE transaction_id={txn[0]} AND cr_dr_indicator='C'")
    }
    pay = payment_row_for(parent_id, txn_reference(txn[0]))
    leg_principal = legs.get("UNBLD_PRIN_AMT", Decimal(0)) + legs.get("BLD_PRIN_AMT", Decimal(0))
    leg_interest = legs.get("BLD_INT_AMT", Decimal(0)) + legs.get("ADV_BLD_INT_AMT", Decimal(0))
    ck("parent.payment_amount_eq_funding", dec(pay[0]) == legs.get("TRMN_SUSP_AMT", Decimal(0)),
       legs.get("TRMN_SUSP_AMT", Decimal(0)), dec(pay[0]),
       "group payment row must record what the closure posting funded")
    ck("parent.payment_principal_eq_legs", dec(pay[1]) == leg_principal, leg_principal, dec(pay[1]))
    ck("parent.payment_interest_eq_legs", dec(pay[2]) == leg_interest, leg_interest, dec(pay[2]),
       "interest_amount must equal the interest the posting actually settled")
    ck("parent.payment_fee_eq_legs", dec(pay[3]) == legs.get("FORCLSR_CHRG", Decimal(0)),
       legs.get("FORCLSR_CHRG", Decimal(0)), dec(pay[3]))

    child_txn = one(
        "SELECT tm.id FROM mfi_accounting.transaction_partition_details p "
        "JOIN mfi_accounting.transaction_master tm ON tm.id=p.transaction_id "
        "JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id "
        f"WHERE p.account_number='{child}' AND tc.type='LOAN_PREPAYMENT' "
        "AND tm.status='SUCCESS' ORDER BY tm.id DESC LIMIT 1")
    child_pay = payment_row_for(child_id, txn_reference(child_txn[0]) if child_txn else None)
    ck("parent.payment_row_mirrors_child",
       [dec(x) for x in pay] == [dec(x) for x in child_pay],
       [str(dec(x)) for x in child_pay], [str(dec(x)) for x in pay],
       "the group settles exactly what the last member settled")

    print()
    if failures:
        print(f"=== FAIL: {len(failures)} assert(s) — {', '.join(failures)}")
        return 1
    print("=== PASS: last member closed the group parent (no 134203, parent netted and closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
