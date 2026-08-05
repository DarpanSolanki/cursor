#!/usr/bin/env python3
"""TDPQA-72: assert parent RSCH_LOAN_PREPAYMENT GL mirrors the child foreclosure GL.

Contract comes from the product sheet (ChildLoan1 Foreclosure GL / ParentLoan Part Prepayment GL):
the parent posts the same settlement the child posts -- one funding leg from DUE_TO_FC_B into the
termination suspense account, then every component debited from that account.

Value-level: every component amount and its credit GL must match the child leg for leg. Presence
checks are deliberately not used; the defect this encodes (missing unbilled principal, penal and
round-off legs, interest credited to AIR instead of billed interest) passes any presence check.

Usage:
  assert_child_fc_parent_rsch_gl.py --child-lan 6004132229
  assert_child_fc_parent_rsch_gl.py --child-txn 1871988 --parent-txn 1871989
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB = os.path.join(ROOT, "scripts", "db-local.sh")

# child foreclosure reference code -> parent RSCH reference code (product sheet vocabulary)
COMPONENT_MAP = {
    "INT_AMT": "BLD_INT_AMT",
    "PRIN_AMT": "BLD_PRIN_AMT",
    "POS": "UNBLD_PRIN_AMT",
    "Penal": "PINT_AMT",
    "CBC_AMT": "CBC_FEE_AMT",
    "ROUND_UP_AMT": "ROUND_UP_AMT",
    "ROUND_DOWN_AMT": "ROUND_DOWN_AMT",
    "FORCLSR_CHRG": "FORCLSR_CHRG",
    "FORCLSR_CHRG_GST": "FORCLSR_CHRG_TAX",
    "FORCLSR_CHRG_CGST": "FORCLSR_CHRG_CGST",
    "FORCLSR_CHRG_SGST": "FORCLSR_CHRG_SGST",
    "FORCLSR_CHRG_IGST": "FORCLSR_CHRG_IGST",
    "FORCLSR_CHRG_UTGST": "FORCLSR_CHRG_UTGST",
}
ZERO_AFTER_FORCE_BILL = ("BPI_AMT",)
CHILD_FUNDING = "TRMN_AMT"
PARENT_FUNDING = "TRMN_SUSP_AMT"
# GST split legs are funded from the GST control account, not from termination suspense
GST_SPLIT = {"FORCLSR_CHRG_CGST", "FORCLSR_CHRG_SGST", "FORCLSR_CHRG_IGST", "FORCLSR_CHRG_UTGST"}
# A whole-rupee split can round either way. ROUND_UP draws from termination suspense like every
# other settled component; ROUND_DOWN is the mirror image — the configured rule is
# ROUND_OFF -> TRMN_SUSP, so it *funds* suspense instead of drawing from it. Asserting the
# round-up shape on a round-down group fails a posting that matches its own accounting rule.
SUSPENSE_FUNDING_COMPONENTS = {"ROUND_DOWN_AMT"}
# Loan-side components resolve to the same internal account on both sides; the child stores it
# CG-prefixed. Charge and GST legs resolve to separate parent/child accounts by product config,
# so only their amounts are comparable.
GL_MIRRORED = {"BLD_INT_AMT", "BLD_PRIN_AMT", "UNBLD_PRIN_AMT", "PINT_AMT", "CBC_FEE_AMT",
               "ROUND_UP_AMT", "ROUND_DOWN_AMT"}
# Mirroring alone would still pass if both sides credited the same wrong account, so each
# component's credit GL name must also identify the right ledger. Substrings are matched
# case-insensitively against general_ledger.name.
GL_NAME_EXPECT = {
    "BLD_INT_AMT": ("bi", "billed interest"),
    "BLD_PRIN_AMT": ("bp", "billed principal"),
    "UNBLD_PRIN_AMT": ("la", "gross rcv", "unbilled"),
    "PINT_AMT": ("penal",),
    "CBC_FEE_AMT": ("cbc",),
    "ROUND_UP_AMT": ("round",),
    "ROUND_DOWN_AMT": ("termination suspense",),
    "FORCLSR_CHRG_CGST": ("cgst",),
    "FORCLSR_CHRG_SGST": ("sgst",),
    "FORCLSR_CHRG_IGST": ("igst",),
    "FORCLSR_CHRG_TAX": ("gst",),
}
PARENT_FUNDING_GL_NAME = ("termination suspense",)
PARENT_FUNDING_DEBIT_GL_NAME = ("due to fc",)


def q(sql: str) -> list[list[str]]:
    out = subprocess.run([DB, "--sql", sql], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit(f"db-local failed: {out.stderr.strip()[:400]}")
    rows = []
    for line in out.stdout.splitlines():
        if "|" not in line or set(line.strip()) <= set("-+"):
            continue
        cells = [c.strip() for c in line.split("|")]
        rows.append(cells)
    return rows[1:] if rows else []


def legs(txn: int) -> dict[str, dict]:
    rows = q(
        "SELECT p.reference_code, p.cr_dr_indicator, p.amount, p.gl_code "
        f"FROM mfi_accounting.transaction_partition_details p WHERE p.transaction_id={txn}"
    )
    out: dict[str, dict] = {}
    for ref, drcr, amt, gl in rows:
        entry = out.setdefault(ref, {})
        entry[drcr] = {"amount": Decimal(amt), "gl": gl}
    return out


def bare(gl: str) -> str:
    return gl[2:] if gl.startswith("CG") else gl


def gl_names(codes: set[str]) -> dict[str, str]:
    if not codes:
        return {}
    quoted = ",".join(f"'{c}'" for c in sorted(codes))
    rows = q(f"SELECT gl.code, gl.name FROM mfi_accounting.general_ledger gl WHERE gl.code IN ({quoted})")
    return {code: name for code, name in (r[:2] for r in rows if len(r) >= 2)}


def resolve_pair(args) -> tuple[int, int, str, str]:
    if args.child_txn and args.parent_txn:
        return args.child_txn, args.parent_txn, "?", "?"
    rows = q(
        "SELECT tm.id, a.account_number FROM mfi_accounting.transaction_master tm "
        "JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id "
        "JOIN mfi_accounting.transaction_partition_details p ON p.transaction_id=tm.id "
        "JOIN mfi_accounting.account a ON a.account_number=p.account_number "
        f"WHERE tc.type='LOAN_PREPAYMENT' AND p.account_number='{args.child_lan}' "
        "AND tm.status='SUCCESS' ORDER BY tm.id DESC LIMIT 1"
    )
    if not rows:
        raise SystemExit(f"FAIL: no SUCCESS LOAN_PREPAYMENT posting found for child {args.child_lan}")
    child_txn = int(rows[0][0])
    # A group parent carries one RSCH per member that has foreclosed. Taking the latest would
    # compare every member against the last member's posting, so pair on the first parent RSCH
    # at or after this child's own foreclosure posting.
    prow = q(
        "SELECT pa.account_number, tm.id FROM mfi_accounting.account a "
        "JOIN mfi_accounting.account pa ON pa.id=a.parent_account_id "
        "JOIN mfi_accounting.transaction_partition_details p ON p.account_number=pa.account_number "
        "JOIN mfi_accounting.transaction_master tm ON tm.id=p.transaction_id "
        "JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id "
        f"WHERE a.account_number='{args.child_lan}' AND tc.type='RSCH_LOAN_PREPAYMENT' "
        f"AND tm.status='SUCCESS' AND tm.id >= {child_txn} ORDER BY tm.id ASC LIMIT 1"
    )
    if not prow:
        raise SystemExit(f"FAIL: no SUCCESS RSCH_LOAN_PREPAYMENT posting found for parent of {args.child_lan}")
    return child_txn, int(prow[0][1]), args.child_lan, prow[0][0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--child-lan")
    ap.add_argument("--child-txn", type=int)
    ap.add_argument("--parent-txn", type=int)
    args = ap.parse_args()
    if not args.child_lan and not (args.child_txn and args.parent_txn):
        ap.error("give --child-lan or both --child-txn and --parent-txn")

    child_txn, parent_txn, child_lan, parent_lan = resolve_pair(args)
    child, parent = legs(child_txn), legs(parent_txn)
    print(f"child LOAN_PREPAYMENT txn={child_txn} lan={child_lan}")
    print(f"parent RSCH_LOAN_PREPAYMENT txn={parent_txn} lan={parent_lan}")

    failures: list[str] = []

    def ck(name: str, ok: bool, expected, actual, why: str = "") -> None:
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {name}: expected={expected} actual={actual}" + (f"  ({why})" if why and not ok else ""))
        if not ok:
            failures.append(name)

    fund_child = child.get(CHILD_FUNDING, {}).get("C")
    fund_parent = parent.get(PARENT_FUNDING, {}).get("C")
    ck(
        "parent.funding_leg_present",
        fund_parent is not None,
        f"{PARENT_FUNDING} credit leg",
        "present" if fund_parent else "ABSENT",
        "parent must fund termination suspense from DUE_TO_FC_B before settling components",
    )
    if fund_child and fund_parent:
        ck("parent.funding_amount_eq_child", fund_parent["amount"] == fund_child["amount"],
           fund_child["amount"], fund_parent["amount"])

    trmn_gl = fund_parent["gl"] if fund_parent else None

    wanted = {bare(v[s]["gl"]) for v in parent.values() for s in ("D", "C") if s in v}
    names = gl_names(wanted)

    def ck_gl_name(label: str, gl: str, patterns: tuple[str, ...]) -> None:
        name = names.get(bare(gl), "")
        ck(label, any(p in name.lower() for p in patterns), f"name matching {patterns}",
           f"{gl} '{name}'", "component posted to a ledger that does not identify it")

    if fund_parent:
        ck_gl_name("parent.funding.credit_gl_name", fund_parent["gl"], PARENT_FUNDING_GL_NAME)
        fund_debit = parent.get(PARENT_FUNDING, {}).get("D")
        if fund_debit:
            ck_gl_name("parent.funding.debit_gl_name", fund_debit["gl"], PARENT_FUNDING_DEBIT_GL_NAME)

    for child_code, parent_code in COMPONENT_MAP.items():
        c = child.get(child_code, {}).get("C")
        if c is None or c["amount"] == 0:
            continue
        p = parent.get(parent_code, {}).get("C")
        if p is None:
            ck(f"parent.{parent_code}.posted", False, f"{c['amount']} (child {child_code})", "ABSENT",
               "component the child settled is not posted on the parent")
            continue
        ck(f"parent.{parent_code}.amount", p["amount"] == c["amount"], c["amount"], p["amount"])
        if parent_code in GL_MIRRORED:
            ck(f"parent.{parent_code}.credit_gl", bare(p["gl"]) == bare(c["gl"]),
               bare(c["gl"]), bare(p["gl"]), "parent must credit the same account the child credits")
        if parent_code in GL_NAME_EXPECT:
            ck_gl_name(f"parent.{parent_code}.credit_gl_name", p["gl"], GL_NAME_EXPECT[parent_code])

        if trmn_gl and parent_code not in GST_SPLIT and parent_code != PARENT_FUNDING:
            if parent_code in SUSPENSE_FUNDING_COMPONENTS:
                ck(f"parent.{parent_code}.credits_termination_suspense",
                   p["gl"] == trmn_gl, trmn_gl, p["gl"],
                   "round-down funds termination suspense instead of drawing from it")
            else:
                d = parent.get(parent_code, {}).get("D")
                ck(f"parent.{parent_code}.debit_from_termination_suspense",
                   d is not None and d["gl"] == trmn_gl, trmn_gl, d["gl"] if d else "ABSENT")

    for code in ZERO_AFTER_FORCE_BILL:
        for label, side in (("child", child), ("parent", parent)):
            leg = side.get(code, {}).get("C")
            amount = leg["amount"] if leg else Decimal(0)
            ck(f"{label}.{code}.zero_after_force_bill", amount == 0, 0, amount,
               "force bill must cover the whole broken period; nothing may settle against AIR")

    if trmn_gl:
        drawn = sum(
            v["D"]["amount"] for k, v in parent.items()
            if "D" in v and v["D"]["gl"] == trmn_gl and k != PARENT_FUNDING
        )
        funded = fund_parent["amount"] if fund_parent else Decimal(0)
        funded += sum(
            v["C"]["amount"] for k, v in parent.items()
            if k in SUSPENSE_FUNDING_COMPONENTS and "C" in v and v["C"]["gl"] == trmn_gl
        )
        ck("parent.termination_suspense_fully_drawn", drawn == funded, funded, drawn,
           "difference is money funded into termination suspense that no leg settled")

    for label, side in (("child", child), ("parent", parent)):
        dr = sum(v["D"]["amount"] for v in side.values() if "D" in v)
        cr = sum(v["C"]["amount"] for v in side.values() if "C" in v)
        ck(f"{label}.double_entry", dr == cr, dr, cr)

    if failures:
        print(f"\n=== FAIL: {len(failures)} assert(s) — {', '.join(failures[:8])}"
              + (" ..." if len(failures) > 8 else ""))
        return 1
    print("\n=== PASS: parent RSCH GL mirrors child foreclosure GL (product sheet) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
