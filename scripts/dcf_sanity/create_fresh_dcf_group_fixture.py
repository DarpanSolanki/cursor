#!/usr/bin/env python3
"""
Provision a brand-new SHG group (product_id=44 / loan_product_id=70) for DCF e2e.

Real flow only:
  disburseLoan (parent + 2 member_details[]) → childLoanEventProcessingBatchJob
  → LIFE_INSUR harness on children → EOD billing sync through mid-schedule death window.

Usage (standalone):
  python3 scripts/dcf_sanity/create_fresh_dcf_group_fixture.py

Returns parent + child LANs + death_date on stdout (also exported as env vars when sourced).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))
from clb_queue_harness import (  # noqa: E402
    child_labd_count,
    dedupe_clb_rep_acct_for_parent,
    max_batch_execution_id,
    quarantine_billing_portfolio,
    restore_billing_portfolio_quarantine,
    wait_batch_after,
)

IST = ZoneInfo("Asia/Kolkata")

PG_ENV = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
PG = [
    "psql", "-h", os.environ.get("YB_HOST", "localhost"),
    "-p", os.environ.get("YB_PORT", "5433"),
    "-U", os.environ.get("YB_USER", "yugabyte"),
    "-d", os.environ.get("YB_DB", "yugabyte"),
    "-v", "ON_ERROR_STOP=1", "-t", "-A",
]

BLOCKLIST_PARENTS = frozenset(
    lan.strip()
    for lan in os.environ.get(
        "DCF_FIXTURE_BLOCKLIST",
        "6003896527,6003973025",
    ).split(",")
    if lan.strip()
)

CANONICAL_SHG = ROOT / "scripts/disbursement/payloads/canonical/disburse_loan_sanity_request_shg_41333333.json"


def psql(sql: str) -> str:
    out = subprocess.check_output([*PG, "-c", sql], env=PG_ENV, text=True)
    return out.strip().split("\n")[0] if out.strip() else ""


def psql_multi(sql: str) -> None:
    subprocess.check_call([*PG[:-2], "-v", "ON_ERROR_STOP=1", "-c", sql], env=PG_ENV)


def _eod_ms(d: date) -> str:
    return str(int(datetime(d.year, d.month, d.day, 18, 0, 0, tzinfo=IST).timestamp() * 1000))


def _midnight_ms(d: date) -> str:
    return str(int(datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=IST).timestamp() * 1000))


def plan_disburse_dates(anchor: date | None = None) -> dict[str, str]:
    """Align disburse + EMI dates so death can land mid-schedule with billable history.

    Default first EMI is two calendar months before the latest past EMI-day so the schedule
    has ≥2 past installments. That lets SEED_EXTRA settle a *past* advance INT via
    loanRepayment (future dues post as EXCESS_AMT and never raise advance_int_paid).
    Override with DCF_FRESH_EMI_MONTHS_BACK=1 for single-past-EMI spines (SEED_EXTRA=0).
    """
    anchor = anchor or date.today()
    emi_day = int(os.environ.get("DCF_FRESH_EMI_DAY", "14"))
    months_back = int(os.environ.get("DCF_FRESH_EMI_MONTHS_BACK", "2"))
    if months_back < 1:
        months_back = 1

    def _shift_month(d: date, delta: int) -> date:
        y, m = d.year, d.month + delta
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        return date(y, m, emi_day)

    # Latest EMI-day on/before anchor, then walk back (months_back - 1) more months.
    first_emi = date(anchor.year, anchor.month, emi_day)
    if first_emi >= anchor:
        first_emi = _shift_month(first_emi, -1)
    first_emi = _shift_month(first_emi, -(months_back - 1))
    disburse = first_emi - timedelta(days=60)
    second_emi = _shift_month(first_emi, 1)
    third_emi = _shift_month(first_emi, 2)
    return {
        "disburse_date": disburse.isoformat(),
        "disburse_ms": _midnight_ms(disburse),
        "first_emi_date": first_emi.isoformat(),
        "first_emi_ms": _midnight_ms(first_emi),
        "second_emi_date": second_emi.isoformat(),
        "third_emi_date": third_emi.isoformat(),
        "anchor_date": anchor.isoformat(),
    }


def pick_customers(count: int = 3) -> list[str]:
    rows = subprocess.check_output(
        [*PG, "-c", """
SELECT c.id::text
FROM mfi_actor.customer c
WHERE c.status = 'ACTIVE' AND c.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.loan_account la
    JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
    WHERE la.customer_id = c.id AND la.is_deleted = false
      AND la.loan_status = 'ACTIVE' AND lp.product_id = '44'
  )
ORDER BY c.id DESC
LIMIT 20;
"""],
        env=PG_ENV,
        text=True,
    ).strip().split("\n")
    ids = [r.strip() for r in rows if r.strip()]
    if len(ids) < count:
        raise RuntimeError(f"need {count} available SHG customers, found {len(ids)}")
    return ids[:count]


def split_member_amounts(total: int, members: int) -> list[int]:
    base = total // members
    amounts = [base] * members
    amounts[0] += total - base * members
    return amounts


def build_disburse_payload(
    *,
    parent_cust: str,
    member_custs: list[str],
    dates: dict[str, str],
    ext_ref: str,
    group_id: str,
    scratch_path: Path,
) -> Path:
    data = json.loads(CANONICAL_SHG.read_text(encoding="utf-8"))
    req = data["request"]
    crn = str(int(time.time() * 1000))
    req["loan_details"]["customer_id"] = parent_cust
    req["loan_details"]["sanction_date"] = dates["disburse_ms"]
    req["disbursement_details"]["external_ref_number"] = ext_ref
    req["disbursement_details"]["expected_disbursement_date"] = dates["disburse_ms"]
    req["disbursement_details"]["client_reference_number"] = crn
    req["repayment_details"]["first_repayment_date"] = dates["first_emi_ms"]
    req["group_details"]["group_id"] = group_id
    req["group_details"]["primary_sig_lan"] = f"LAN{group_id[-6:]}"
    template = req.get("member_details") or []
    if len(template) < 2:
        raise RuntimeError("canonical SHG payload needs 2 member_details[] rows")
    amounts = (
        [int(m["loan_amount"]) for m in template]
        if len(member_custs) == len(template)
        else split_member_amounts(int(req["loan_details"]["loan_amount"]), len(member_custs))
    )
    members = []
    for index, (cust, amount) in enumerate(zip(member_custs, amounts)):
        member = json.loads(json.dumps(template[index % len(template)]))
        member["customer_id"] = cust
        member["external_ref_number"] = f"{ext_ref}M{index + 1}"
        for field in ("loan_amount", "approved_amount", "requested_amount"):
            member[field] = str(amount)
        for account in member.get("disbursement_repayment_account_details") or []:
            codes = {p.get("code") for p in account.get("purpose") or []}
            if "DSBR_ACCT" in codes:
                account["account_number"] = f"{account['account_number'][:-2]}{index:02d}"
                if account.get("external_account_number"):
                    account["external_account_number"] = f"{account['external_account_number'][:-2]}{index:02d}"
        members.append(member)
    req["member_details"] = members
    data["headers"]["stan"] = crn
    data["headers"]["transmission_datetime"] = dates["disburse_ms"]
    scratch_path.parent.mkdir(parents=True, exist_ok=True)
    scratch_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return scratch_path


def run_disburse(payload_path: Path, report_path: Path) -> None:
    subprocess.check_call(
        [
            "bash", str(ROOT / "scripts/bin/agent-ops.sh"), "before-test", "disburseLoan",
        ],
        cwd=str(ROOT),
    )
    lock = Path("/tmp/disburse_loan_sanity.lock")
    if lock.exists():
        lock.unlink()
    cmd = [
        "python3", str(ROOT / "scripts/disburse_loan_sanity.py"),
        "--request-file", str(payload_path),
        "--stage-suite", "minimal",
        "--simulator-profile", "success",
        "--reset-before",
        "--reset-target-disb-status", "LAN_CREATED",
        "--http-timeout-s", "45",
        "--wait-timeout-s", "180",
        "--poll-s", "2.0",
        "--report-json", str(report_path),
        "--fail-fast",
    ]
    print(f"  disburse: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(ROOT))


def resolve_parent_and_children(ext_ref: str, expected: int = 2) -> tuple[str, list[str]]:
    parent_id = psql(f"""
SELECT la.account_id::text FROM mfi_accounting.loan_account la
WHERE la.external_ref_number LIKE '{ext_ref}%' AND la.has_child_accounts = true
  AND la.is_deleted = false
ORDER BY la.account_id DESC LIMIT 1;
""")
    if not parent_id:
        raise RuntimeError(f"disburse did not create parent for ext_ref={ext_ref}")
    parent_lan = psql(f"SELECT la_account_number FROM mfi_accounting.loan_account WHERE account_id={parent_id};")
    kids = subprocess.check_output(
        [*PG, "-c", f"""
SELECT la_account_number FROM mfi_accounting.loan_account
WHERE parent_loan_account_id={parent_id} AND is_deleted=false
ORDER BY la_account_number;
"""],
        env=PG_ENV,
        text=True,
    ).strip().split("\n")
    children = [k.strip() for k in kids if k.strip()]
    if len(children) != expected:
        raise RuntimeError(f"expected {expected} children under {parent_lan}, got {children}")
    return parent_lan, children


def drive_child_events(parent_lan: str, expected: int = 2, timeout_s: int = 180) -> None:
    """Run childLoanEventProcessingBatchJob until every child is COMPLETED/ACTIVE with schedule."""
    parent_id = int(psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}';"
    ))
    dedupe_clb_rep_acct_for_parent(parent_id)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ready_cnt = psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account c
WHERE c.parent_loan_account_id={parent_id} AND c.is_deleted=false
  AND c.disbursement_status IN ('COMPLETED','CHILD_SUCCESS','ACTIVE')
  AND EXISTS (
    SELECT 1 FROM mfi_accounting.loan_installment_details lid
    WHERE lid.loan_account_id=c.account_id AND lid.is_deleted=false
  );
""")
        if ready_cnt == str(expected):
            print(f"  child events OK: parent={parent_lan} children disbursed with schedule")
            return
        dedupe_clb_rep_acct_for_parent(parent_id)
        before_id = max_batch_execution_id("childLoanEventProcessingBatchJob")
        subprocess.check_call(
            ["python3", str(ROOT / "scripts/testing/api-fire.py"),
             "childLoanEventProcessingBatchJob", "--batch",
             "--job-time", str(int(time.time() * 1000))],
            cwd=str(ROOT),
        )
        wait_batch_after("childLoanEventProcessingBatchJob", before_id, timeout_s=min(120, timeout_s))
        time.sleep(2)
    raise RuntimeError(f"childLoanEventProcessingBatchJob timeout for parent {parent_lan}")


def ensure_life_insurance(child_lans: list[str]) -> None:
    """Harness: clone LIFE_INSUR row shape from a known-good fixture child (not DFC state)."""
    template_id = psql("""
SELECT ins.id FROM mfi_accounting.loan_account_insurance_details ins
JOIN mfi_accounting.loan_account la ON la.account_id=ins.loan_account_id
WHERE ins.policy_type='LIFE_INSUR' AND ins.is_deleted=false
  AND la.loan_status IN ('ACTIVE','CLOSED')
ORDER BY ins.id DESC LIMIT 1;
""")
    if not template_id:
        raise RuntimeError("no LIFE_INSUR template row in DB for harness clone")
    for child_lan in child_lans:
        account_id = psql(
            f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';"
        )
        exists = psql(f"""
SELECT 1 FROM mfi_accounting.loan_account_insurance_details
WHERE loan_account_id={account_id} AND policy_type='LIFE_INSUR' AND is_deleted=false LIMIT 1;
""")
        if exists == "1":
            continue
        psql_multi(f"""
INSERT INTO mfi_accounting.loan_account_insurance_details (
  loan_account_id, applicable_for, insurance_product_code, insurance_provider_code,
  premium_calc_code, policy_type, insured_gender, insured_age, insured_duration_frequency,
  insured_duration, sum_assured, premium_amount, total_tax_amount, policy_number,
  is_deleted, insured_name, insured_dob, insured_address, insured_mobile_no, insured_pob,
  status, policy_start_date, policy_end_date, is_posted, created_on, created_by, updated_on, updated_by
)
SELECT
  {account_id}, t.applicable_for, t.insurance_product_code, t.insurance_provider_code,
  t.premium_calc_code, t.policy_type, t.insured_gender, t.insured_age, t.insured_duration_frequency,
  t.insured_duration, t.sum_assured, t.premium_amount, t.total_tax_amount,
  'DCF{child_lan[-6:]}',
  false, t.insured_name, t.insured_dob, t.insured_address, t.insured_mobile_no, t.insured_pob,
  'PENDING', la.expected_disbursement_date,
  la.expected_disbursement_date + INTERVAL '12 months',
  false, NOW(), 'DCF_FRESH_GROUP', NOW(), 'DCF_FRESH_GROUP'
FROM mfi_accounting.loan_account_insurance_details t
JOIN mfi_accounting.loan_account la ON la.account_id = {account_id}
WHERE t.id = {template_id};
""")
        print(f"  LIFE_INSUR harness applied on {child_lan}")


def fire_batch(api: str, job_time: str) -> None:
    # Wait by execution id, not wall-clock vs create_time — timestamp-without-tz
    # EXTRACT(EPOCH) is ~+5.5h vs time.time() and was matching old FAILED rows.
    before_id = max_batch_execution_id(api)
    rc = subprocess.call(
        ["python3", str(ROOT / "scripts/testing/api-fire.py"), api, "--batch", "--job-time", job_time],
        cwd=str(ROOT),
    )
    if rc != 0:
        raise RuntimeError(f"batch {api} HTTP fire failed rc={rc}")
    wait_batch_after(api, before_id, timeout_s=180)


def sync_billing_for_group(parent_lan: str, child_lans: list[str], through_date: str) -> None:
    """Real accrual + loanAccountBillingJob through through_date for parent + children."""
    parent_id = int(psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}';"
    ))
    child_ids = [
        int(psql(f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{lan}';"))
        for lan in child_lans
    ]
    lans = [parent_lan, *child_lans]
    due_dates: set[str] = set()
    for lan in lans:
        rows = subprocess.check_output(
            [*PG, "-c", f"""
SELECT DISTINCT to_char(lid.installment_date::date, 'YYYY-MM-DD')
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_account la ON la.account_id = lid.loan_account_id
WHERE la.la_account_number = '{lan}' AND lid.is_deleted = false
  AND lid.installment_date::date <= DATE '{through_date}'
ORDER BY 1;
"""],
            env=PG_ENV,
            text=True,
        ).strip().split("\n")
        due_dates.update(r.strip() for r in rows if r.strip())

    print(f"  billing quarantine (local harness) parent_id={parent_id} keep={len(child_ids)+1} loans")
    quarantine_billing_portfolio(parent_id, child_ids)
    try:
        for row in sorted(due_dates):
            d = date.fromisoformat(row)
            # Bill on EOD day after installment due — billing on due-date EOD returns 333 locally.
            bill_d = d + timedelta(days=1)
            if bill_d.isoformat() > through_date:
                continue
            jt = _eod_ms(bill_d)
            print(f"  billing sync group job_date={bill_d.isoformat()} ({jt})")
            fire_batch("interestAccrualCalculation", jt)
            try:
                fire_batch("interestAccrualPosting", jt)
            except RuntimeError as e:
                if os.environ.get("FIXTURE_STRICT") == "1":
                    raise
                print(f"  WARN: interestAccrualPosting skipped ({e}) — continuing to billing")
            try:
                fire_batch("loanAccountBillingJob", jt)
            except RuntimeError as e:
                if os.environ.get("FIXTURE_STRICT") == "1":
                    raise
                print(f"  WARN: loanAccountBillingJob failed ({e}) — EMI labd harness may apply")
            time.sleep(1)
    finally:
        restore_billing_portfolio_quarantine()

    missing = [lan for lan in child_lans
               if child_labd_count(int(psql(
                   f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{lan}';"
               ))) == 0]
    for lan in missing:
        print(f"  WARN: billing produced no labd for {lan} — EMI labd harness (real installment + due amounts)")
        ensure_emi_labd_harness(lan)


def ensure_emi_labd_harness(child_lan: str) -> None:
    """Harness: insert one EMI-shaped labd from real schedule when billing batch cannot run locally.

    This writes the row the billing job was supposed to write, so any assert that reads billed
    amounts downstream is proving the harness, not the product. Callers that need billing to be
    real must set FIXTURE_STRICT=1, which refuses the fallback instead of faking it.
    """
    if os.environ.get("FIXTURE_STRICT") == "1":
        raise RuntimeError(
            f"FIXTURE_STRICT: loanAccountBillingJob produced no labd for {child_lan}; "
            "refusing to hand-insert one. Fix the billing run — do not seed the outcome."
        )
    account_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';"
    )
    if not account_id or child_labd_count(int(account_id)) > 0:
        return
    row = psql(f"""
SELECT lid.id::text,
       to_char(lid.installment_date,'YYYY-MM-DD'),
       COALESCE(SUM(CASE WHEN ldd.component_type='PRIN' THEN ldd.due_amount ELSE 0 END),0)::text,
       COALESCE(SUM(CASE WHEN ldd.component_type='INT' THEN ldd.due_amount ELSE 0 END),0)::text
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_account la ON la.account_id = lid.loan_account_id
LEFT JOIN mfi_accounting.loan_due_details ldd
  ON ldd.loan_installment_details_id = lid.id AND ldd.is_deleted = false
WHERE la.la_account_number = '{child_lan}' AND lid.is_deleted = false
GROUP BY lid.id, lid.installment_date
ORDER BY lid.installment_date
LIMIT 1;
""")
    if not row:
        raise RuntimeError(f"EMI labd harness: no installment for {child_lan}")
    lid_id, inst_date, prin, interest = row.split("|", 3)
    billing_amt = Decimal(prin) + Decimal(interest)
    emi_ref = f"EMI_HARNESS_{child_lan}_{inst_date.replace('-', '')}"
    psql_multi(f"""
INSERT INTO mfi_accounting.loan_account_billing_details (
  account_id, loan_installment_details_id, billing_amount, principal_amount,
  interest_amount, transaction_value_date, transaction_reference_number, reversed,
  created_on, created_by, updated_on, updated_by
)
SELECT {account_id}, {lid_id}, {billing_amt}, {prin}, {interest},
       lid.installment_date, '{emi_ref}', false,
       NOW(), 'DCF_FRESH_EMI_LABD', NOW(), 'DCF_FRESH_EMI_LABD'
FROM mfi_accounting.loan_installment_details lid WHERE lid.id = {lid_id};
""")
    print(f"  EMI labd harness: {child_lan} lid={lid_id} ref={emi_ref} amt={billing_amt}")


def compute_death_date(parent_lan: str) -> str:
    parent_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}';"
    )
    death = psql(f"""
WITH d AS (
  SELECT DISTINCT ldd.due_date
  FROM mfi_accounting.loan_due_details ldd
  JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
  WHERE c.parent_loan_account_id={parent_id} AND ldd.component_type='PRIN' AND ldd.is_deleted=false
  ORDER BY ldd.due_date
), cand AS (
  SELECT (due_date + INTERVAL '1 day')::date AS death_d FROM d
), ok AS (
  SELECT cand.death_d FROM cand
  WHERE EXISTS (
    SELECT 1 FROM mfi_accounting.loan_due_details ldd
    JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
    WHERE c.parent_loan_account_id={parent_id}
      AND ldd.component_type='INT' AND ldd.is_deleted=false
      AND ldd.due_date::date > (cand.death_d - INTERVAL '1 day')
      AND ldd.due_date::date <= CURRENT_DATE
      AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)) > 0
  )
  AND EXISTS (
    SELECT 1 FROM mfi_accounting.loan_due_details ldd
    JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
    WHERE c.parent_loan_account_id={parent_id}
      AND ldd.component_type='PRIN' AND ldd.is_deleted=false
      AND ldd.due_date::date < cand.death_d
  )
  AND EXISTS (
    SELECT 1 FROM mfi_accounting.loan_due_details ldd
    JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
    WHERE c.parent_loan_account_id={parent_id}
      AND ldd.component_type='PRIN' AND ldd.is_deleted=false
      AND ldd.due_date::date >= cand.death_d
  )
  ORDER BY cand.death_d LIMIT 1
)
SELECT to_char(death_d,'YYYY-MM-DD') FROM ok;
""")
    if not death:
        # Fallback: day after first PRIN due (mid-schedule; EXTRA path may need manual repay)
        death = psql(f"""
SELECT to_char((MIN(ldd.due_date) + INTERVAL '1 day')::date, 'YYYY-MM-DD')
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
WHERE c.parent_loan_account_id={parent_id} AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or date.today().isoformat()
        print(f"  WARN: death_date fallback (EXTRA may be 0): {death}")
    return death


def create_fresh_dcf_group_fixture(members: int = 2) -> tuple[str, list[str], str]:
    ts = int(time.time() * 1000)
    ext_ref = os.environ.get("DCF_FRESH_EXT_REF", f"DCFGRP{ts}")
    group_id = os.environ.get("DCF_FRESH_GROUP_ID", str(ts)[-8:])
    dates = plan_disburse_dates()
    custs = pick_customers(members + 1)
    parent_cust, member_custs = custs[0], custs[1:]
    scratch = ROOT / "scripts/scratch/dcf_fresh_group" / f"disburse_{ts}.json"
    report = ROOT / "scripts/scratch/dcf_fresh_group" / f"report_{ts}.json"

    print("=== create fresh DCF group fixture (real disburse + billing) ===")
    print(f"  ext_ref={ext_ref} group_id={group_id} dates={dates}")
    print(f"  customers parent={parent_cust} members={member_custs}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    subprocess.check_call(["bash", str(ROOT / "scripts/bin/novopay-service.sh"), "ensure", "task"])

    payload = build_disburse_payload(
        parent_cust=parent_cust,
        member_custs=member_custs,
        dates=dates,
        ext_ref=ext_ref,
        group_id=group_id,
        scratch_path=scratch,
    )
    run_disburse(payload, report)
    parent_lan, children = resolve_parent_and_children(ext_ref, expected=members)
    if parent_lan in BLOCKLIST_PARENTS:
        raise RuntimeError(f"fresh disburse landed on blocklisted parent {parent_lan}")

    drive_child_events(parent_lan, expected=members)
    ensure_life_insurance(children)

    death_date = compute_death_date(parent_lan)
    billing_through = psql(f"""
SELECT to_char(GREATEST(DATE '{death_date}', (
  SELECT MIN(lid.installment_date::date) + INTERVAL '1 day'
  FROM mfi_accounting.loan_installment_details lid
  JOIN mfi_accounting.loan_account c ON c.account_id = lid.loan_account_id
  WHERE c.parent_loan_account_id = (
    SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number = '{parent_lan}'
  ) AND lid.is_deleted = false
))::date, 'YYYY-MM-DD');
""")
    # Do NOT extend group billing_through to CURRENT_DATE for SEED_EXTRA.
    # That left sticky billed PRIN past death/reporting on *all* children before any DCF.
    # Non-last DCF then sees inflated getUnpaidBilledPrincipalForDeathForeClosure and
    # DeathForeclosureInsuranceWriter.doParentPartPrePayment appropriates
    # pendingInstallment+unpaidBilled → parent prin_paid > child principal (S_C Δ1532).
    # EXTRA seed bills the *last* child's advance EMI only via
    # seed_extra_via_loan_repayment → _ensure_advance_installment_billed (after non-last).
    # Opt-in repro of the poison: SEED_EXTRA_EXTEND_GROUP_BILLING=1.
    if (
        os.environ.get("SEED_EXTRA", "0") != "0"
        and os.environ.get("SEED_EXTRA_EXTEND_GROUP_BILLING", "0") != "0"
    ):
        billing_through = psql(f"""
SELECT to_char(GREATEST(
  DATE '{billing_through}',
  CURRENT_DATE,
  (
    SELECT (lid.installment_date::date + INTERVAL '1 day')
    FROM mfi_accounting.loan_installment_details lid
    JOIN mfi_accounting.loan_account c ON c.account_id = lid.loan_account_id
    WHERE c.parent_loan_account_id = (
      SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number = '{parent_lan}'
    ) AND lid.is_deleted = false
    ORDER BY lid.installment_date
    OFFSET 1 LIMIT 1
  )
)::date, 'YYYY-MM-DD');
""")
        print(f"  SEED_EXTRA_EXTEND_GROUP_BILLING billing_through → {billing_through}")
    sync_billing_for_group(parent_lan, children, billing_through)

    print(f"=== FRESH FIXTURE READY parent={parent_lan} children={children} death_date={death_date} ===")
    return parent_lan, children, death_date


def main() -> int:
    try:
        members = int(os.environ.get("DCF_FIXTURE_MEMBERS", "2"))
        parent, children, death = create_fresh_dcf_group_fixture(members)
        print(f"PARENT_LAN={parent}")
        for index, child in enumerate(children):
            print(f"CHILD{index + 1}_LAN={child}")
        print(f"DEATH_DATE={death}")
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
