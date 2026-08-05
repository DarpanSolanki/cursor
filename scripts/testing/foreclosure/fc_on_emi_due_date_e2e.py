#!/usr/bin/env python3
"""TDPQA-240: foreclose an INDL loan on an EMI due date the billing job already billed.

The day's billing sweeps every accrual period of that installment into the EMI. Force-bill must
then bill nothing: a second labd on the same installment bills interest the quote never charged,
so the settlement legs draw more out of termination suspense than the customer paid.

Fixture is a brand-new INDL loan (real disburse, real accrual/posting/billing) aged to its first
EMI; accrual is run through the EMI date and billing on the day after, so the newest accrual
period ends on the foreclosure date exactly as it does on the reported account.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "dcf_sanity"))

import create_fresh_dcf_group_fixture as fixture  # noqa: E402
import group_parent_last_child_dfc_local_e2e as fc  # noqa: E402
from clb_queue_harness import quarantine_billing_portfolio, restore_billing_portfolio_quarantine  # noqa: E402

TOL = Decimal("0.01")
CANONICAL_INDL = ROOT / "scripts/disbursement/payloads/canonical/disburse_loan_sanity_request_370164.json"
SCRATCH = ROOT / "scripts/scratch/tdpqa-240"


def pick_loan_and_next_due() -> tuple[str, str, str]:
    """Standalone loan whose next installment after the last billed one is still unbilled.

    Ageing that one installment with the real EOD chain reproduces the reported shape: a single
    accrual period ending on the EMI date, swept whole into that EMI by the billing job. The
    force-bill resolver under test is shared by every product, so the product is reported rather
    than pinned; set FC_ON_DUE_PRODUCT to pin it.
    """
    product = os.environ.get("FC_ON_DUE_PRODUCT", "")
    product_filter = f"AND lp.product_id = '{product}'" if product else ""
    row = fc.psql(f"""
WITH candidate AS (
  SELECT la.account_id,
         a.account_number,
         lp.product_id,
         (SELECT MAX(lid.installment_date::date)
            FROM mfi_accounting.loan_installment_details lid
            JOIN mfi_accounting.loan_account_billing_details b
              ON b.loan_installment_details_id = lid.id
           WHERE lid.loan_account_id = la.account_id AND lid.is_deleted = false) AS last_billed
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.account a ON a.id = la.account_id
  JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
  WHERE la.loan_status = 'ACTIVE' {product_filter}
    AND la.parent_loan_account_id IS NULL AND la.has_child_accounts = false
    AND la.is_deleted = false
    AND EXISTS (SELECT 1 FROM mfi_accounting.interest_accrual_details i WHERE i.account_id = la.account_id)
)
SELECT c.account_number || '|' || to_char(n.next_due, 'YYYY-MM-DD') || '|' || c.product_id
FROM candidate c
CROSS JOIN LATERAL (
  SELECT MIN(lid.installment_date::date) AS next_due
  FROM mfi_accounting.loan_installment_details lid
  WHERE lid.loan_account_id = c.account_id AND lid.is_deleted = false
    AND lid.installment_date::date > c.last_billed
    AND NOT EXISTS (SELECT 1 FROM mfi_accounting.loan_account_billing_details b
                     WHERE b.loan_installment_details_id = lid.id)
) n
WHERE c.last_billed IS NOT NULL AND n.next_due IS NOT NULL
  AND (SELECT COUNT(*) FROM mfi_accounting.loan_installment_details lid
        WHERE lid.loan_account_id = c.account_id AND lid.is_deleted = false
          AND lid.installment_date::date > n.next_due) >= 3
ORDER BY c.account_id DESC
LIMIT 1;
""")
    if not row:
        raise SystemExit("no standalone ACTIVE loan with an unbilled next installment on local")
    lan, due, product = row.split("|")
    return lan, due, product


def pick_customer() -> str:
    cust = fc.psql("""
SELECT c.id::text
FROM mfi_actor.customer c
LEFT JOIN mfi_accounting.loan_account la
  ON la.customer_id = c.id
 AND la.loan_product_id = (SELECT id FROM mfi_accounting.loan_product WHERE product_id = '45' LIMIT 1)
 AND la.loan_status = 'ACTIVE'
 AND la.is_deleted = false
WHERE c.status = 'ACTIVE' AND c.is_deleted = false AND la.account_id IS NULL
ORDER BY c.id DESC
LIMIT 1;
""")
    if not cust:
        raise SystemExit("no ACTIVE customer without an ACTIVE INDL loan on local")
    return cust


def build_indl_payload(dates: dict[str, str]) -> Path:
    """Canonical INDL identity is kept: --reset-before voids the previous loan and re-disburses."""
    data = json.loads(CANONICAL_INDL.read_text(encoding="utf-8"))
    req = data["request"]
    crn = str(int(time.time() * 1000))
    req["loan_details"]["sanction_date"] = dates["disburse_ms"]
    req["disbursement_details"]["expected_disbursement_date"] = dates["disburse_ms"]
    req["disbursement_details"]["client_reference_number"] = crn
    req["repayment_details"]["first_repayment_date"] = dates["first_emi_ms"]
    data["headers"]["stan"] = crn
    data["headers"]["transmission_datetime"] = dates["disburse_ms"]
    SCRATCH.mkdir(parents=True, exist_ok=True)
    path = SCRATCH / "disburse_indl.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def emi_today_dates() -> dict[str, str]:
    """loanPrepayment requires foreclosure_date == the system date (132282), so the EMI must be today."""
    today = date.today()
    disburse = today - timedelta(days=60)
    return {
        "disburse_date": disburse.isoformat(),
        "disburse_ms": fixture._midnight_ms(disburse),
        "first_emi_date": today.isoformat(),
        "first_emi_ms": fixture._midnight_ms(today),
    }


def create_fresh_indl_loan() -> tuple[str, str]:
    dates = emi_today_dates()
    payload = build_indl_payload(dates)
    data = json.loads(payload.read_text(encoding="utf-8"))
    cust = data["request"]["loan_details"]["customer_id"]
    print(f"  fresh INDL: customer={cust} disburse={dates['disburse_date']} first_emi={dates['first_emi_date']}")
    before = fc.psql(f"""
SELECT COALESCE(MAX(la.account_id), 0)::text FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
WHERE la.customer_id = {cust} AND lp.product_id = '45';
""") or "0"
    fixture.run_disburse(payload, SCRATCH / "disburse_report.json")
    lan = fc.psql(f"""
SELECT la.la_account_number FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
WHERE la.customer_id = {cust} AND lp.product_id = '45'
  AND la.account_id > {before} AND la.is_deleted = false
ORDER BY la.account_id DESC LIMIT 1;
""")
    if not lan:
        raise SystemExit(f"disburse did not create a new INDL loan for customer {cust}")
    return lan, dates["first_emi_date"]


def create_fresh_group_child_due_today() -> tuple[str, str, str, list[int]]:
    """Fresh SHG group whose first EMI lands today.

    loanPrepayment requires foreclosure_date == the system date (132282), so the only way to
    foreclose *on* an EMI date is to disburse a loan whose EMI is today. plan_disburse_dates
    always puts the first EMI strictly before today, so the dates are built here.
    """
    today = date.today()
    disburse = today - timedelta(days=60)
    dates = {
        "disburse_date": disburse.isoformat(),
        "disburse_ms": fixture._midnight_ms(disburse),
        "first_emi_date": today.isoformat(),
        "first_emi_ms": fixture._midnight_ms(today),
    }
    ts = int(time.time() * 1000)
    ext_ref = f"TDPQA240{ts}"
    group_id = str(ts)[-8:]
    custs = fixture.pick_customers(3)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    print(f"  fresh SHG group: disburse={dates['disburse_date']} first_emi={dates['first_emi_date']}")
    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    payload = fixture.build_disburse_payload(
        parent_cust=custs[0], member_custs=custs[1:], dates=dates,
        ext_ref=ext_ref, group_id=group_id, scratch_path=SCRATCH / f"disburse_{ts}.json",
    )
    fixture.run_disburse(payload, SCRATCH / f"report_{ts}.json")
    parent_lan, children = fixture.resolve_parent_and_children(ext_ref, expected=2)
    fixture.drive_child_events(parent_lan, expected=2)
    keep = [account_id(parent_lan)] + [account_id(c) for c in children]
    return children[0], today.isoformat(), "44", keep


def account_id(lan: str) -> int:
    return int(fc.psql(f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{lan}';"))


def installment_for_due(acct: int, due: str) -> int:
    row = fc.psql(f"""
SELECT lid.id::text FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id = {acct} AND lid.is_deleted = false
  AND lid.installment_date::date = DATE '{due}'
LIMIT 1;
""")
    if not row:
        raise SystemExit(f"account {acct} has no installment on {due}")
    return int(row)


def accrued_for_installment(acct: int, installment: int) -> Decimal:
    return Decimal(fc.psql(f"""
SELECT COALESCE(SUM(total_accrued_amount), 0)::text
FROM mfi_accounting.interest_accrual_details
WHERE account_id = {acct} AND loan_installment_details_id = {installment};
""") or "0")


def billed_for_installment(installment: int) -> Decimal:
    return Decimal(fc.psql(f"""
SELECT COALESCE(SUM(interest_amount), 0)::text
FROM mfi_accounting.loan_account_billing_details
WHERE loan_installment_details_id = {installment} AND reversed = false;
""") or "0")


def labd_count(installment: int) -> int:
    return int(fc.psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details
WHERE loan_installment_details_id = {installment};
""") or "0")


def newest_accrual_end(acct: int) -> str:
    return fc.psql(f"""
SELECT to_char(MAX(end_date), 'YYYY-MM-DD')
FROM mfi_accounting.interest_accrual_details WHERE account_id = {acct};
""") or ""


def age_to_first_emi(acct: int, due: str, keep: list[int] | None = None) -> None:
    """Accrue through the EMI date, bill on the day after (billing at due-date EOD 333s locally)."""
    keep = keep or [acct]
    quarantine_billing_portfolio(keep[0], keep[1:])
    try:
        jt_due = fixture._eod_ms(date.fromisoformat(due))
        for api in ("interestAccrualCalculation", "interestAccrualPosting"):
            print(f"  batch {api} @ {due}")
            fc.fire_batch(api, jt_due)
            time.sleep(2)
        bill_day = (date.fromisoformat(due) + timedelta(days=1)).isoformat()
        print(f"  batch loanAccountBillingJob @ {bill_day}")
        fc.fire_batch("loanAccountBillingJob", fixture._eod_ms(date.fromisoformat(bill_day)))
        time.sleep(2)
    finally:
        restore_billing_portfolio_quarantine()


def settle_parent_overdue_if_group(lan: str) -> None:
    """A member cannot foreclose while the group carries overdue (433); settle it via real repayment."""
    parent_lan = fc.psql(f"""
SELECT p.la_account_number
FROM mfi_accounting.loan_account c
JOIN mfi_accounting.loan_account p ON p.account_id = c.parent_loan_account_id
WHERE c.la_account_number = '{lan}';
""")
    if not parent_lan:
        return
    print(f"  settling group overdue on {parent_lan} (real loanRepayment)")
    fc.settle_parent_overdue_before_vikram_fc(parent_lan, account_id(parent_lan))


def foreclose(lan: str, due: str) -> None:
    fd_ms = fc._eod_ms_ist(due)
    sim = fc._lp_simulate(lan, fd_ms)
    receipt = f"tdpqa240{int(time.time()) % 10**10:010d}"
    request = fc._lp_build_request(sim, lan, fd_ms, receipt)
    ok = frozenset({"000", "30365", "30364", "30267", "30366"})
    for step in ("DEFAULT", "APPROVE_TASK", "APPROVE"):
        stan = f"tdpqa240_{step.lower()}_{lan}_{int(time.time())}"
        resp = fc._acct_post("loanPrepayment", {"headers": fc._lp_headers(stan, function_code=step), "request": request})
        status = resp.get("response_status", {})
        code, st = status.get("code"), status.get("status")
        print(f"  loanPrepayment {step}: {code}/{st} — {str(status.get('message',''))[:140]}")
        if code not in ok and st != "SUCCESS":
            raise AssertionError(f"loanPrepayment {step} failed for {lan}: {code}/{st}")
        time.sleep(1)


def assert_pass_through_gls_net_zero(ref: str) -> None:
    rows = fc.psql(f"""
SELECT tpd.gl_code || '|' || tpd.cr_dr_indicator || '|' || COALESCE(tpd.amount,0)::text
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
WHERE tm.reference_number = '{ref}';
""")
    if not rows:
        raise AssertionError(f"no GL partition rows for LOAN_PREPAYMENT ref={ref}")
    net: dict[str, Decimal] = {}
    sides: dict[str, set[str]] = {}
    for line in rows.split("\n"):
        gl, ind, amt = line.strip().split("|")
        signed = Decimal(amt) if ind.upper().startswith("D") else -Decimal(amt)
        net[gl] = net.get(gl, Decimal(0)) + signed
        sides.setdefault(gl, set()).add(ind.upper()[:1])
    for gl, n in sorted(net.items()):
        print(f"    gl {gl}: net {n} sides={''.join(sorted(sides[gl]))}")
    bad = {gl: n for gl, n in net.items() if len(sides[gl]) > 1 and abs(n) > TOL}
    if bad:
        raise AssertionError(
            f"pass-through GL left a residue on ref={ref}: {bad} — "
            f"settlement legs draw more than the customer paid (TDPQA-240)"
        )


def assert_billed_interest_leg(ref: str, acct: int) -> None:
    leg = Decimal(fc.psql(f"""
SELECT COALESCE(SUM(tpd.amount), 0)::text
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
WHERE tm.reference_number = '{ref}' AND tpd.reference_code = 'INT_AMT'
  AND tpd.cr_dr_indicator ILIKE 'C%';
""") or "0")
    charged = Decimal(fc.psql(f"""
SELECT COALESCE(billed_interest_amount_to_be_paid, 0)::text
FROM mfi_accounting.prepayment_details
WHERE loan_account_id = {acct} AND prepayment_status = 'APPROVED'
ORDER BY id DESC LIMIT 1;
""") or "0")
    print(f"    INT_AMT credited {leg} vs billed interest charged {charged}")
    if abs(leg - charged) > TOL:
        raise AssertionError(
            f"billed interest settled {leg} but the customer was charged {charged} "
            f"(TDPQA-240: force-bill re-billed an already-billed cycle)"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lan", default=os.environ.get("FC_ON_DUE_LAN"))
    ap.add_argument("--due", default=os.environ.get("FC_ON_DUE_DATE"))
    args = ap.parse_args()

    product, keep = "unknown", None
    if args.lan and args.due:
        lan, due = args.lan, args.due
    elif os.environ.get("FC_ON_DUE_EXISTING") == "1":
        lan, due, product = pick_loan_and_next_due()
    elif os.environ.get("FC_ON_DUE_GROUP") == "1":
        print("--- fresh fixture: group disbursed 60 days back, first EMI today (real disburse) ---")
        lan, due, product, keep = create_fresh_group_child_due_today()
    else:
        print("--- fresh fixture: INDL disbursed 60 days back, first EMI today (real disburse) ---")
        lan, due = create_fresh_indl_loan()
        product = "45"
    acct = account_id(lan)
    print(f"=== TDPQA-240 FC-on-EMI-due-date: lan={lan} account={acct} product={product} emi_due={due} ===")

    print("--- age to the EMI due date (real accrual + posting + billing) ---")
    age_to_first_emi(acct, due, keep)

    installment = installment_for_due(acct, due)
    accrued = accrued_for_installment(acct, installment)
    billed = billed_for_installment(installment)
    before = labd_count(installment)
    end = newest_accrual_end(acct)
    print(f"  installment {installment} | accrued {accrued} | billed {billed} | labd rows {before} | newest accrual ends {end}")

    if accrued <= 0 or before == 0:
        raise SystemExit(
            f"fixture did not reach the reported shape: accrued={accrued} labd_rows={before} on "
            f"installment {installment} — the EMI billing must have swept a non-zero accrual"
        )
    if abs(accrued - billed) > TOL:
        raise SystemExit(
            f"fixture did not reach the reported shape: {accrued - billed} of accrual still unbilled "
            f"on installment {installment} — this case needs the whole cycle billed"
        )
    if end != due:
        raise SystemExit(
            f"fixture did not reach the reported shape: newest accrual ends {end}, foreclosure is {due}"
        )

    print("--- foreclose on that same date (real loanPrepayment) ---")
    settle_parent_overdue_if_group(lan)
    foreclose(lan, due)

    after = labd_count(installment)
    print(f"  labd rows on installment: {before} -> {after}")
    if after != before:
        raise AssertionError(
            f"force-bill wrote {after - before} extra labd row(s) on installment {installment}: "
            f"the EMI billing had already billed the whole cycle (TDPQA-240)"
        )

    ref, _ = fc.latest_txn(lan, "LOAN_PREPAYMENT")
    print(f"--- assert settlement GL on LOAN_PREPAYMENT ref={ref} ---")
    assert_pass_through_gls_net_zero(ref)
    assert_billed_interest_leg(ref, acct)

    print(f"PASS foreclosure.fc_on_emi_due_date lan={lan} product={product} due={due}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
