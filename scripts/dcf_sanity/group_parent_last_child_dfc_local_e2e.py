#!/usr/bin/env python3
"""
SDCP-10199 — real local e2e: SHG/group parent + 2 children through deathForeclosureInsuranceJob.

Drives production-shaped insurance batches (outbound → inbound patch → approve job).
Verifies DB: loan status, dues paid/waived, DEATH_FORECLOSURE + RSCH_DEATH_FORECLOSURE postings.

Usage:
  python3 scripts/dcf_sanity/group_parent_last_child_dfc_local_e2e.py
  PARENT_LAN=6003973025 CHILD1_LAN=6003973329 CHILD2_LAN=6003973330 python3 ...

Requires: local accounting up, mfi_batch schema, target loans ACTIVE with LIFE_INSUR.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PG_ENV = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
PG = [
    "psql", "-h", os.environ.get("YB_HOST", "localhost"),
    "-p", os.environ.get("YB_PORT", "5433"),
    "-U", os.environ.get("YB_USER", "yugabyte"),
    "-d", os.environ.get("YB_DB", "yugabyte"),
    "-v", "ON_ERROR_STOP=1", "-t", "-A",
]


def psql(sql: str) -> str:
    out = subprocess.check_output([*PG, "-c", sql], env=PG_ENV, text=True)
    return out.strip().split("\n")[0] if out.strip() else ""


def psql_multi(sql: str) -> None:
    subprocess.check_call([*PG[:-2], "-v", "ON_ERROR_STOP=1", "-c", sql], env=PG_ENV)


def fire_batch(api: str, job_time: str) -> None:
    cmd = [
        "python3", str(ROOT / "scripts/testing/api-fire.py"),
        api, "--batch", "--job-time", job_time,
    ]
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        raise RuntimeError(f"batch {api} HTTP fire failed rc={rc}")



def snapshot_dues(lan: str, label: str) -> dict:
    row = psql(f"""
SELECT COALESCE(SUM(CASE WHEN ldd.component_type='PRIN' THEN ldd.paid_amount ELSE 0 END),0),
       COALESCE(SUM(CASE WHEN ldd.component_type='PRIN' THEN ldd.waived_amount ELSE 0 END),0),
       COALESCE(SUM(CASE WHEN ldd.component_type='PRIN' THEN ldd.due_amount-ldd.paid_amount-ldd.waived_amount ELSE 0 END),0),
       COALESCE(SUM(CASE WHEN ldd.component_type='INT' THEN ldd.waived_amount ELSE 0 END),0),
       la.loan_status
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{lan}' AND ldd.is_deleted=false
GROUP BY la.loan_status;
""")
    parts = row.split("|") if row else ["0", "0", "0", "0", ""]
    snap = {
        "label": label,
        "lan": lan,
        "prin_paid": Decimal(parts[0] or "0"),
        "prin_waived": Decimal(parts[1] or "0"),
        "prin_pending": Decimal(parts[2] or "0"),
        "int_waived": Decimal(parts[3] or "0"),
        "loan_status": parts[4] if len(parts) > 4 else "",
    }
    print(f"  [{label}] {lan} status={snap['loan_status']} prin_paid={snap['prin_paid']} "
          f"prin_waived={snap['prin_waived']} prin_pending={snap['prin_pending']} int_waived={snap['int_waived']}")
    return snap


def latest_txn(lan: str, txn_type: str) -> tuple[str, str]:
    """Closure txns link via loan_account_closure_details; RSCH uses client_reference_number suffix."""
    if txn_type == "DEATH_FORECLOSURE":
        row = psql(f"""
SELECT tm.reference_number, tm.original_amount::text
FROM mfi_accounting.loan_account_closure_details lacd
JOIN mfi_accounting.loan_account la ON la.account_id = lacd.loan_account_id
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = lacd.transaction_reference_number
WHERE la.la_account_number = '{lan}' AND lacd.identifier_type = '{txn_type}'
ORDER BY lacd.id DESC LIMIT 1;
""")
    elif txn_type == "RSCH_DEATH_FORECLOSURE":
        row = psql(f"""
SELECT tm.reference_number, tm.original_amount::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE tc.type = '{txn_type}' AND tm.client_reference_number LIKE '%_{lan}'
ORDER BY tm.id DESC LIMIT 1;
""")
    else:
        row = psql(f"""
SELECT tm.reference_number, tm.original_amount::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
WHERE td.account_number = '{lan}' AND tc.type = '{txn_type}'
ORDER BY tm.id DESC LIMIT 1;
""")
    if not row:
        return "", ""
    ref, amt = row.split("|", 1)
    return ref, amt


def partition_codes(ref: str) -> list[str]:
    if not ref:
        return []
    rows = subprocess.check_output(
        [*PG, "-c", f"""
SELECT reference_code||':'||COALESCE(tpd.amount,0)::text||':'||COALESCE(tpd.cr_dr_indicator,'')
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id=tpd.transaction_id
WHERE tm.reference_number='{ref}' ORDER BY reference_code;
"""],
        env=PG_ENV, text=True,
    ).strip()
    return [r for r in rows.split("\n") if r]


def child_already_closed_from_dfc(child_lan: str) -> bool:
    st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';")
    if st != "CLOSED":
        return False
    ref, _ = latest_txn(child_lan, "DEATH_FORECLOSURE")
    return bool(ref)


def cleanup_abandoned_staging(child_lans: list[str], keep_staging_id: int | None = None) -> None:
    """Stop insurance reader from re-picking stale inbound rows (batch min/max id window)."""
    lan_list = ",".join(f"'{lan}'" for lan in child_lans)
    keep_clause = f"AND s.id <> {keep_staging_id}" if keep_staging_id else ""
    psql_multi(f"""
UPDATE mfi_accounting.death_foreclosure_insurance_staging_details s
SET claim_status = 'APPROVED', status = 'COMPLETED', updated_on = NOW(), updated_by = 'LOCAL_E2E'
FROM mfi_accounting.death_foreclosure_details dfd
JOIN mfi_accounting.loan_account la ON la.account_id = dfd.loan_account_id
WHERE s.death_foreclosure_details_id = dfd.id
  AND la.la_account_number IN ({lan_list})
  {keep_clause}
  AND s.inout_status = 'INBOUND_SUCCESS'
  AND s.claim_status NOT IN ('APPROVED', 'REJECTED', 'PENDING')
  AND (s.status IS NULL OR s.status NOT IN ('COMPLETED', 'PROCESSING'));
""")


def quarantine_all_other_inbound_staging(keep_staging_id: int) -> None:
    """Global guard: the approve reader scans by id window and may re-pick INBOUND_SUCCESS rows
    left behind by earlier/aborted fixtures. Mark every other in-flight inbound row COMPLETED so
    only keep_staging_id is processed. Script-only; touches staging bookkeeping, not loan money."""
    psql_multi(f"""
UPDATE mfi_accounting.death_foreclosure_insurance_staging_details
SET claim_status='APPROVED', status='COMPLETED', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE id <> {keep_staging_id}
  AND inout_status='INBOUND_SUCCESS'
  AND (status IS NULL OR status NOT IN ('COMPLETED','PROCESSING'));
""")


def wait_batch_by_start(job_name: str, started_epoch: int, timeout_s: int = 300) -> str:
    """Poll batch_job_execution by job name + start time (Spring param is `time`, not request job_time)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        row = psql(f"""
SELECT bje.status
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = '{job_name}'
  AND EXTRACT(EPOCH FROM bje.create_time)::bigint >= {started_epoch}
ORDER BY bje.job_execution_id DESC
LIMIT 1;
""")
        if row == "COMPLETED":
            print(f"  batch {job_name} COMPLETED")
            return row
        if row in ("FAILED", "STOPPED", "ABANDONED"):
            raise RuntimeError(f"batch {job_name} {row}")
        time.sleep(2)
    raise RuntimeError(f"batch {job_name} timeout after {timeout_s}s")

def reset_child_dfc_if_needed(child_lan: str) -> None:
    """Remove in-flight DFC seed so sibling ACTIVE count is correct for last-child detection."""
    row = psql(f"""
SELECT dfd.id, la.loan_status FROM mfi_accounting.death_foreclosure_details dfd
JOIN mfi_accounting.loan_account la ON la.account_id=dfd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND dfd.death_foreclosure_status NOT IN ('APPROVED','REJECTED')
LIMIT 1;
""")
    if not row:
        if psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';") == "DEATH_FORECLOSURE_FREEZE":
            psql_multi(f"""
UPDATE mfi_accounting.loan_account SET loan_status='ACTIVE', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE la_account_number='{child_lan}';
""")
            print(f"  reset {child_lan} FREEZE → ACTIVE (no open DFD)")
        return
    dfd_id, status = row.split("|", 1)
    psql_multi(f"""
UPDATE mfi_accounting.death_foreclosure_insurance_staging_details SET is_deleted=true, updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE death_foreclosure_details_id={dfd_id} AND COALESCE(is_deleted,false)=false;
UPDATE mfi_accounting.death_foreclosure_details SET death_foreclosure_status='REJECTED', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE id={dfd_id};
UPDATE mfi_accounting.loan_account SET loan_status='ACTIVE', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE la_account_number='{child_lan}';
""")
    print(f"  reset in-flight DFC child={child_lan} dfd_id={dfd_id} was_status={status}")


def seed_dfc_child(child_lan: str, death_date: str) -> tuple[int, int]:
    """Insert DFD + staging (PENDING, no inout) for approve reader."""
    account_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}' AND is_deleted=false;"
    )
    if not account_id:
        raise RuntimeError(f"child LAN not found: {child_lan}")

    existing = psql(f"""
SELECT dfd.id FROM mfi_accounting.death_foreclosure_details dfd
JOIN mfi_accounting.loan_account la ON la.account_id=dfd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND dfd.death_foreclosure_status NOT IN ('REJECTED','APPROVED')
LIMIT 1;
""")
    if existing:
        dfd_id = int(existing)
        staging_id = psql(f"""
SELECT id FROM mfi_accounting.death_foreclosure_insurance_staging_details
WHERE death_foreclosure_details_id={dfd_id} AND COALESCE(is_deleted,false)=false
ORDER BY id DESC LIMIT 1;
""")
        if staging_id:
            return dfd_id, int(staging_id)

    dfd_id = int(psql(f"""
WITH ins AS (
  INSERT INTO mfi_accounting.death_foreclosure_details (
    loan_account_id, deceased_person, deceased_person_name, date_of_death, claim_type, cause_of_death,
    is_nominee_under_age, death_foreclosure_status, task_status, created_on, created_by, updated_on, updated_by,
    outstanding_loan_balance, balance_claim_amount, death_claim_form_document_id, place_of_death, date_of_birth
  )
  SELECT {account_id}, 'BORROWER', 'LOCAL_DFC_E2E', '{death_date}'::timestamp, 'NATURAL', 'NATURAL_DEATH',
    false, 'INITIATED_INSURACE_CLAIM', 'PENDING',
    ('{death_date}'::timestamp + INTERVAL '5 days'), 'LOCAL_E2E', NOW(), 'LOCAL_E2E',
    0, 0, 150437, 'Local', '1995-01-01'::timestamp
  RETURNING id
)
SELECT id FROM ins;
"""))

    li = psql(f"""
SELECT policy_number, sum_assured::text FROM mfi_accounting.loan_account_insurance_details
WHERE loan_account_id={account_id} AND policy_type='LIFE_INSUR' AND is_deleted=false LIMIT 1;
""")
    policy, sum_assured = (li.split("|") + ["POL{account_id}", "20000"])[:2]
    claim_num = f"E2E{child_lan}{int(time.time())}"

    staging_id = int(psql(f"""
WITH ins AS (
  INSERT INTO mfi_accounting.death_foreclosure_insurance_staging_details (
    death_foreclosure_details_id, policy_number, product_code, loan_account_number, claim_type, cause_of_event,
    date_of_event, date_of_reporting, sum_assured, original_loan_amount, outstanding_loan_balance,
    balance_claim_amount, ifsc_code, account_number, claim_status, claim_number, inout_status,
    created_on, created_by, updated_on, updated_by, is_deleted
  )
  VALUES (
    {dfd_id}, '{policy}', 'SHGDL', '{child_lan}', 'NATURAL', 'NATURAL_DEATH',
    '{death_date}'::timestamp, NOW(), {sum_assured}, {sum_assured}, 0,
    0, 'ICIC0001417', '141701521467', 'PENDING', '{claim_num}', NULL,
    NOW(), 'LOCAL_E2E', NOW(), 'LOCAL_E2E', false
  )
  RETURNING id
)
SELECT id FROM ins;
"""))

    psql_multi(f"""
UPDATE mfi_accounting.loan_account SET loan_status='DEATH_FORECLOSURE_FREEZE', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE la_account_number='{child_lan}';
""")
    print(f"  seeded child {child_lan} dfd_id={dfd_id} staging_id={staging_id}")
    return dfd_id, staging_id


def compute_outstanding_rounded(child_lan: str, death_date: str) -> str:
    """SQL component sum aligned with dcf_amount_reconcile.sql (read-only buckets)."""
    overdue = psql(f"""
SELECT COALESCE(SUM(ldd.due_amount-ldd.paid_amount-ldd.waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.is_deleted=false
  AND ldd.component_type IN ('PRIN','INT') AND ldd.due_date < '{death_date}'::date
  AND (ldd.due_amount-ldd.paid_amount-ldd.waived_amount)>0;
""")
    future_prin = psql(f"""
SELECT COALESCE(SUM(ldd.due_amount-ldd.paid_amount-ldd.waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='PRIN'
  AND ldd.due_date >= '{death_date}'::date AND ldd.is_deleted=false;
""")
    pint = psql(f"""
SELECT COALESCE(SUM(GREATEST(ldd.due_amount-ldd.paid_amount-ldd.waived_amount,0)),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='PINT'
  AND ldd.due_date <= '{death_date}'::date AND ldd.is_deleted=false;
""")
    fee = psql(f"""
SELECT COALESCE(SUM(GREATEST(ldd.due_amount-ldd.paid_amount-ldd.waived_amount,0)),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='FEE'
  AND ldd.due_date <= '{death_date}'::date AND ldd.is_deleted=false;
""")
    total = Decimal(overdue or "0") + Decimal(future_prin or "0") + Decimal(pint or "0") + Decimal(fee or "0")
    rounded = total.quantize(Decimal("1"), rounding="ROUND_HALF_UP")
    print(f"  computed outstanding child={child_lan} overdue={overdue} future_prin={future_prin} "
          f"pint={pint} fee={fee} rounded={rounded}")
    return str(rounded)


def run_inbound_approve_only(child_lan: str, dfd_id: int, staging_id: int, death_date: str) -> None:
    os_bal = compute_outstanding_rounded(child_lan, death_date)
    account_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';"
    )
    sum_assured = psql(f"""
SELECT COALESCE(sum_assured::text,'0') FROM mfi_accounting.loan_account_insurance_details
WHERE loan_account_id={account_id} AND policy_type='LIFE_INSUR' AND is_deleted=false LIMIT 1;
""") or "0"
    bal_claim = str((Decimal(sum_assured) - Decimal(os_bal)).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
    psql_multi(f"""
UPDATE mfi_accounting.death_foreclosure_details
SET outstanding_loan_balance = {os_bal}, balance_claim_amount = {bal_claim}, updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE id={dfd_id};

UPDATE mfi_accounting.death_foreclosure_insurance_staging_details
SET claim_status='Claim Closed', inout_status='INBOUND_SUCCESS',
    payment_amount_for_nominee = {bal_claim},
    outstanding_loan_balance = {os_bal},
    updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE id={staging_id};
""")

    quarantine_all_other_inbound_staging(staging_id)
    jt = str(int(time.time() * 1000))
    fire_batch("deathForeclosureInsuranceJob", jt)
    # Source of truth = the child reaching CLOSED. glCBSIntegration (bank CBS) is best-effort and
    # logs connection-refused locally without rolling back the closure, so batch_job_execution can
    # read FAILED even though the DFC committed. Poll the loan instead.
    wait_loan_closed(child_lan, timeout_s=300)


def wait_loan_closed(child_lan: str, timeout_s: int = 300) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';")
        if st == "CLOSED":
            print(f"  child {child_lan} CLOSED (batch committed)")
            return
        if st == "ACTIVE":
            # FREEZE reset by a rollback → real failure (not the benign CBS log)
            raise RuntimeError(f"child {child_lan} back to ACTIVE — DFC rolled back")
        time.sleep(2)
    raise RuntimeError(f"child {child_lan} not CLOSED after {timeout_s}s (status stuck at FREEZE)")


def assert_child_closed(child_lan: str) -> None:
    st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';")
    if st != "CLOSED":
        raise AssertionError(f"child {child_lan} expected CLOSED got {st!r}")
    pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.is_deleted=false;
""") or "0")
    if pending != 0:
        raise AssertionError(f"child {child_lan} pending dues {pending} != 0")
    for comp in ("INT", "PINT", "PRIN"):
        comp_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='{comp}' AND ldd.is_deleted=false;
""") or "0")
        if comp_pending != 0:
            raise AssertionError(f"child {child_lan} {comp} pending {comp_pending} != 0")
    prin_waived = Decimal(psql(f"""
SELECT COALESCE(SUM(waived_amount),0) FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or "0")
    ref, amt = latest_txn(child_lan, "DEATH_FORECLOSURE")
    parts = partition_codes(ref)
    print(f"  child {child_lan} DEATH_FORECLOSURE ref={ref} amount={amt} partitions={parts}")
    if not ref:
        raise AssertionError(f"child {child_lan} missing DEATH_FORECLOSURE txn")
    print(f"  child {child_lan} PRIN waived={prin_waived} (expect 0 on child path)")


def assert_parent_last_child(parent_lan: str) -> None:
    st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}';")
    if st != "CLOSED":
        raise AssertionError(f"parent {parent_lan} expected CLOSED got {st!r}")
    closing = psql(f"""
SELECT CASE WHEN la_closing_date IS NULL THEN 'no' ELSE 'yes' END
FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}';
""")
    if closing != "yes":
        raise AssertionError(f"parent {parent_lan} missing la_closing_date")
    prin_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or "0")
    prin_waived = Decimal(psql(f"""
SELECT COALESCE(SUM(waived_amount),0) FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or "0")
    prin_paid = Decimal(psql(f"""
SELECT COALESCE(SUM(paid_amount),0) FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or "0")
    if prin_pending != 0:
        raise AssertionError(f"parent PRIN pending {prin_pending} != 0")
    if prin_waived != 0:
        raise AssertionError(f"parent PRIN waived {prin_waived} != 0 (insurance must pay PRIN)")
    neg_prin = psql(f"""
SELECT COUNT(*) FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false
  AND (ldd.due_amount < 0 OR ldd.paid_amount < 0 OR ldd.waived_amount < 0);
""") or "0"
    if int(neg_prin) > 0:
        raise AssertionError(f"parent {parent_lan} has {neg_prin} negative PRIN due row(s)")
    all_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.is_deleted=false;
""") or "0")
    if all_pending != 0:
        raise AssertionError(f"parent {parent_lan} total pending dues {all_pending} != 0")
    ref, amt = latest_txn(parent_lan, "RSCH_DEATH_FORECLOSURE")
    parts = partition_codes(ref)
    print(f"  parent {parent_lan} RSCH_DEATH_FORECLOSURE ref={ref} amount={amt}")
    print(f"  parent partitions: {parts}")
    if not ref:
        raise AssertionError(f"parent {parent_lan} missing RSCH_DEATH_FORECLOSURE txn")
    payment_principal = psql(f"""
SELECT lapd.principal_amount::text
FROM mfi_accounting.loan_account_payments_details lapd
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = lapd.transaction_reference_number
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.loan_account la ON la.account_id = lapd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND tc.type='RSCH_DEATH_FORECLOSURE'
ORDER BY tm.id DESC LIMIT 1;
""")
    if not payment_principal:
        raise AssertionError(f"parent {parent_lan} missing RSCH payment details row")
    txn_amt = Decimal(amt or "0")
    prin = Decimal(payment_principal or "0")
    if txn_amt > 0 and prin >= txn_amt * 2 - Decimal("0.01"):
        raise AssertionError(
            f"parent RSCH principal_amount {prin} looks doubled vs txn {txn_amt} "
            f"(saveLoanAccountPaymentsDetails net_amount+principal_amount on last child)"
        )
    if prin > txn_amt + Decimal("0.01"):
        raise AssertionError(f"parent RSCH principal_amount {prin} exceeds txn amount {txn_amt}")
    account_status = psql(f"""
SELECT a.status FROM mfi_accounting.account a
JOIN mfi_accounting.loan_account la ON la.account_id=a.id
WHERE la.la_account_number='{parent_lan}';
""")
    if account_status != "CLOSED":
        raise AssertionError(f"parent account.status {account_status!r} expected CLOSED (Loan 360 banner)")
    account_closing = psql(f"""
SELECT CASE WHEN a.closing_date IS NULL THEN 'no' ELSE 'yes' END
FROM mfi_accounting.account a
JOIN mfi_accounting.loan_account la ON la.account_id=a.id
WHERE la.la_account_number='{parent_lan}';
""")
    if account_closing != "yes":
        raise AssertionError(f"parent account.closing_date missing")
    unsettled = psql(f"""
SELECT COUNT(*) FROM mfi_accounting.loan_installment_details
WHERE loan_account_id=(SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}')
  AND is_deleted=false AND is_settled=false;
""")
    if int(unsettled or "0") > 0:
        raise AssertionError(f"parent has {unsettled} unsettled installment(s) after last-child close")
    asset_class = psql(f"""
SELECT acs.classification FROM mfi_accounting.loan_account la
JOIN mfi_accounting.asset_classification_slabs acs ON acs.id = la.asset_classification_slabs_id
WHERE la.la_account_number='{parent_lan}';
""") or ""
    npa_days = psql(f"""
SELECT COALESCE(npa_ageing_days,0) FROM mfi_accounting.loan_account
WHERE la_account_number='{parent_lan}';
""") or "0"
    if asset_class != "STD":
        raise AssertionError(
            f"parent {parent_lan} asset classification {asset_class!r} expected STD after closure"
        )
    if int(npa_days) != 0:
        raise AssertionError(f"parent {parent_lan} npa_ageing_days {npa_days} expected 0 after closure")
    print(f"  parent PRIN paid={prin_paid} waived={prin_waived} pending={prin_pending} "
          f"classification={asset_class} npa_ageing_days={npa_days}")


def discover_fresh_fixture() -> tuple[str, str, str, str]:
    """Pick a live ACTIVE group parent (product 70) with exactly 2 ACTIVE LIFE_INSUR children.

    Fixtures are consumed by a full run (loans close), so each run auto-discovers a fresh one
    instead of hard-coding LANs. death_date = day after the children's last PRIN due (all
    principal in settlement scope). No service code / no loan mutation here — pure read.
    """
    parent_id = psql("""
SELECT p.account_id
FROM mfi_accounting.loan_account p
JOIN mfi_accounting.loan_account c ON c.parent_loan_account_id = p.account_id
  AND c.loan_status='ACTIVE' AND c.is_deleted=false
LEFT JOIN mfi_accounting.loan_account_insurance_details ins
  ON ins.loan_account_id=c.account_id AND ins.policy_type='LIFE_INSUR' AND ins.is_deleted=false
WHERE p.has_child_accounts=true AND p.loan_status='ACTIVE' AND p.is_deleted=false
  AND p.loan_product_id=70
GROUP BY p.account_id
HAVING COUNT(c.account_id)=2 AND SUM(CASE WHEN ins.id IS NOT NULL THEN 1 ELSE 0 END)=2
ORDER BY p.account_id LIMIT 1;
""")
    if not parent_id:
        raise RuntimeError("no fresh ACTIVE product-70 parent with 2 insured children found")
    parent = psql(f"SELECT la_account_number FROM mfi_accounting.loan_account WHERE account_id={parent_id};")
    kids = subprocess.check_output(
        [*PG, "-c", f"""
SELECT la_account_number FROM mfi_accounting.loan_account
WHERE parent_loan_account_id={parent_id} AND loan_status='ACTIVE' AND is_deleted=false
ORDER BY la_account_number;
"""], env=PG_ENV, text=True).strip().split("\n")
    child1, child2 = kids[0].strip(), kids[1].strip()
    # death_date must fall WITHIN the schedule with a valid "next installment", else
    # InterestCalculationUtil throws "No current installment". An EXACT due date trips a different
    # branch that can throw; the proven-good shape (matches manual QA, e.g. 2025-11-03) is a
    # mid-schedule PRIN due date + 1 day — a real mid-tenure death that leaves overdue rows before
    # it and future-principal rows after it, with a guaranteed subsequent installment.
    death_date = psql(f"""
WITH d AS (
  SELECT DISTINCT ldd.due_date
  FROM mfi_accounting.loan_due_details ldd
  JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
  WHERE c.parent_loan_account_id={parent_id} AND ldd.component_type='PRIN' AND ldd.is_deleted=false
  ORDER BY ldd.due_date
), n AS (SELECT COUNT(*) cnt FROM d),
mid AS (
  SELECT due_date FROM (SELECT due_date, row_number() OVER (ORDER BY due_date) rn FROM d) x, n
  WHERE rn = GREATEST(1, (n.cnt/2)) LIMIT 1
)
SELECT to_char((SELECT due_date FROM mid) + INTERVAL '1 day','YYYY-MM-DD');
""") or "2026-04-01"
    print(f"  discovered fresh fixture: parent={parent} child1={child1} child2={child2} death_date={death_date}")
    return parent, child1, child2, death_date


def main() -> int:
    if os.environ.get("PARENT_LAN"):
        parent = os.environ["PARENT_LAN"]
        child1 = os.environ.get("CHILD1_LAN", "6003973329")
        child2 = os.environ.get("CHILD2_LAN", "6003973330")
        death_date = os.environ.get("DEATH_DATE", "2026-04-01")
    else:
        parent, child1, child2, death_date = discover_fresh_fixture()
    # Non-last child must run first: last-child detection counts ACTIVE siblings only.
    children_in_order = [child2, child1]

    print("=== SDCP-10199 group parent last-child DFC local e2e (real batches) ===")
    print(f"parent={parent} child1={child1} child2={child2} death_date={death_date}")

    # Retest-on-same-LANs provision (dcf_fixture_backup.py):
    #   * first run on a LAN  → snapshot pristine state (parent + ALL children, every mutated table)
    #   * every later run     → RESTORE to that pristine snapshot first, so the same LANs re-run clean
    # The snapshot is never overwritten once taken, so a burned run can always be reverted.
    # Skip entirely with DCF_E2E_NO_SNAPSHOT=1. Force revert at end with DCF_E2E_RESTORE=1.
    backup_py = str(ROOT / "scripts/dcf_sanity/dcf_fixture_backup.py")
    snapshot_enabled = os.environ.get("DCF_E2E_NO_SNAPSHOT") != "1"
    if snapshot_enabled:
        has_snapshot = psql(
            f"SELECT 1 FROM information_schema.schemata WHERE schema_name='dcf_bak_{parent}';") == "1"
        if has_snapshot:
            print(f"--- snapshot exists → RESTORE {parent} to pristine before run ---")
            subprocess.check_call(["python3", backup_py, "restore", parent], env=PG_ENV)
        else:
            subprocess.check_call(["python3", backup_py, "snapshot", parent], env=PG_ENV)

    try:
        subprocess.check_call(
            ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
            env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
        )

        cleanup_abandoned_staging([child1, child2])

        print("\n--- RESET partial / in-flight DFC on both children ---")
        reset_child_dfc_if_needed(child1)
        reset_child_dfc_if_needed(child2)

        print("\n--- BEFORE ---")
        snapshot_dues(parent, "parent-before")
        snapshot_dues(child1, "child1-before")
        snapshot_dues(child2, "child2-before")

        for idx, child in enumerate(children_in_order, start=1):
            print(f"\n--- CHILD {idx} {child}: seed + approve job ---")
            if child_already_closed_from_dfc(child):
                print(f"  skip batch — {child} already CLOSED with DEATH_FORECLOSURE (prior run)")
                assert_child_closed(child)
            else:
                dfd_id, staging_id = seed_dfc_child(child, death_date)
                cleanup_abandoned_staging([child1, child2], keep_staging_id=staging_id)
                run_inbound_approve_only(child, dfd_id, staging_id, death_date)
                assert_child_closed(child)
            snapshot_dues(parent, f"parent-after-child{idx}")
            if idx == 1:
                pst = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{parent}';")
                if pst != "ACTIVE":
                    print(f"  WARN: parent after child1 status={pst} (expected ACTIVE until last child)")

        print("\n--- PARENT last-child assertions ---")
        assert_parent_last_child(parent)

        print("\n=== PASS: SDCP-10199 group parent last-child DFC local e2e ===")
        return 0
    finally:
        if snapshot_enabled:
            if os.environ.get("DCF_E2E_RESTORE") == "1":
                print(f"\n--- RESTORE fixture {parent} to pristine (DCF_E2E_RESTORE=1) ---")
                subprocess.check_call(["python3", backup_py, "restore", parent], env=PG_ENV)
            else:
                print(f"\nRetest tip: this fixture auto-restores on next run, or revert now with →\n"
                      f"  python3 scripts/dcf_sanity/dcf_fixture_backup.py restore {parent}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, RuntimeError) as e:
        print(f"\nFAIL: {e}", file=sys.stderr)
        sys.exit(1)
