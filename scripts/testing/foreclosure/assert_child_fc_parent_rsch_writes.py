#!/usr/bin/env python3
"""TDPQA-72: audit the non-GL rows a member foreclosure + parent reschedule must write.

The GL assert proves the postings; this proves the ledger-adjacent state QA actually opens:
loan/account status, dues cleared, payment rows, closure row, and the parent part-prepayment row.
Every check is value-level against amounts derived from prepayment_details, never presence-only.

Usage: assert_child_fc_parent_rsch_writes.py --child-lan 6004167325
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
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

    parent_row = one(
        "SELECT pa.account_number FROM mfi_accounting.account a "
        "JOIN mfi_accounting.account pa ON pa.id=a.parent_account_id "
        f"WHERE a.account_number='{child}'")
    if not parent_row:
        raise SystemExit(f"FAIL: no parent for child {child}")
    parent = parent_row[0]
    print(f"child={child} parent={parent}")

    pd = one(
        "SELECT pd.pending_installment_amount_to_be_paid, pd.balance_principal_amount_to_be_paid, "
        "pd.bpi_amount_to_be_paid, pd.round_off_amount "
        "FROM mfi_accounting.prepayment_details pd "
        "JOIN mfi_accounting.loan_account la ON la.account_id=pd.loan_account_id "
        "JOIN mfi_accounting.account a ON a.id=la.account_id "
        f"WHERE a.account_number='{child}' ORDER BY pd.id DESC LIMIT 1")
    if not pd:
        raise SystemExit(f"FAIL: no prepayment_details for {child}")
    pending_inst, bal_prin, bpi, round_off = (dec(v) for v in pd)

    status = one(
        "SELECT la.loan_status, a.status FROM mfi_accounting.loan_account la "
        f"JOIN mfi_accounting.account a ON a.id=la.account_id WHERE a.account_number='{child}'")
    ck("child.loan_status", status[0] == "CLOSED", "CLOSED", status[0])
    ck("child.account_status", status[1] == "CLOSED", "CLOSED", status[1])

    dues = one(
        "SELECT COALESCE(SUM(ldd.due_amount - COALESCE(ldd.paid_amount,0) "
        "- COALESCE(ldd.waived_amount,0)),0) FROM mfi_accounting.loan_due_details ldd "
        "JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id "
        "JOIN mfi_accounting.account a ON a.id=la.account_id "
        f"WHERE a.account_number='{child}' AND COALESCE(ldd.is_deleted,false)=false")
    ck("child.dues_pending", dec(dues[0]) == 0, 0, dec(dues[0]),
       "foreclosure must leave no unsettled due on the closed member loan")

    unsettled = one(
        "SELECT COUNT(*) FROM mfi_accounting.loan_installment_details lid "
        "JOIN mfi_accounting.loan_account la ON la.account_id=lid.loan_account_id "
        "JOIN mfi_accounting.account a ON a.id=la.account_id "
        f"WHERE a.account_number='{child}' AND COALESCE(lid.is_deleted,false)=false "
        "AND COALESCE(lid.is_settled,false)=false")
    ck("child.unsettled_installments", int(unsettled[0]) == 0, 0, int(unsettled[0]))

    closure = one(
        "SELECT lacd.transaction_reference_number, lacd.identifier_type, COALESCE(lacd.is_reversed,false) "
        "FROM mfi_accounting.loan_account_closure_details lacd "
        "JOIN mfi_accounting.loan_account la ON la.account_id=lacd.loan_account_id "
        "JOIN mfi_accounting.account a ON a.id=la.account_id "
        f"WHERE a.account_number='{child}' ORDER BY lacd.id DESC LIMIT 1")
    ck("child.closure_row", closure is not None, "one closure row", "present" if closure else "ABSENT")
    if closure:
        ck("child.closure_identifier", closure[1] == "FORECLOSURE", "FORECLOSURE", closure[1])
        ck("child.closure_not_reversed", closure[2] in ("f", "false"), "false", closure[2])

    # amount is the gross collected; principal/interest/fee carry the business split and by design
    # exclude tax and round-off, so they are checked individually and never summed back to amount.
    # The member settles its own billed principal on top of the balance principal; the group loan
    # reschedules on the balance principal alone, so the two payment rows differ by design.
    gross = pending_inst + bal_prin + bpi + round_off
    for label, lan, exp_prin in (("child", child, bal_prin + pending_inst), ("parent", parent, bal_prin)):
        lapd = one(
            "SELECT lapd.amount, lapd.principal_amount, lapd.interest_amount, lapd.fee_amount "
            "FROM mfi_accounting.loan_account_payments_details lapd "
            "JOIN mfi_accounting.loan_account la ON la.account_id=lapd.loan_account_id "
            "JOIN mfi_accounting.account a ON a.id=la.account_id "
            f"WHERE a.account_number='{lan}' AND lapd.amount >= {gross} "
            "ORDER BY lapd.id DESC LIMIT 1")
        if not lapd:
            ck(f"{label}.foreclosure_payment_row", False, f"payment row >= {gross}", "ABSENT",
               "the foreclosure settlement must be recorded as a payment on both loans")
            continue
        amount, prin, interest, fee = (dec(v) for v in lapd)
        ck(f"{label}.payment_principal", prin == exp_prin, exp_prin, prin)
        ck(f"{label}.payment_interest", interest == bpi, bpi, interest)
        ck(f"{label}.payment_amount_covers_gross", amount >= gross, f">= {gross}", amount)

    ppd = one(
        "SELECT ppd.status, ppd.gross_amount, ppd.net_amount, ppd.bpi_amount "
        "FROM mfi_accounting.loan_account_part_prepayment_details ppd "
        "JOIN mfi_accounting.loan_account la ON la.account_id=ppd.loan_account_id "
        "JOIN mfi_accounting.account a ON a.id=la.account_id "
        f"WHERE a.account_number='{parent}' ORDER BY ppd.id DESC LIMIT 1")
    ck("parent.part_prepayment_row", ppd is not None, "one row", "present" if ppd else "ABSENT")
    if ppd:
        ck("parent.part_prepayment_status", ppd[0] == "DEPOSITED", "DEPOSITED", ppd[0])
        ck("parent.part_prepayment_net_eq_child_balance_principal", dec(ppd[2]) == bal_prin,
           bal_prin, dec(ppd[2]),
           "parent reschedules on the member's balance principal")

    pstatus = one(
        "SELECT la.loan_status FROM mfi_accounting.loan_account la "
        f"JOIN mfi_accounting.account a ON a.id=la.account_id WHERE a.account_number='{parent}'")
    ck("parent.stays_active", pstatus[0] == "ACTIVE", "ACTIVE", pstatus[0],
       "closing one member must not close the group loan")

    if failures:
        print(f"\n=== FAIL: {len(failures)} write assert(s) — {', '.join(failures[:8])}")
        return 1
    print("\n=== PASS: member foreclosure + parent reschedule non-GL writes ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
