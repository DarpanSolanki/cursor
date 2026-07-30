#!/usr/bin/env python3
"""W3-d — overlapping loanAccountBillingJob fires → no double labd for same installment.

Production contract: second overlapping fire no-ops or locks out; must not create
duplicate billing rows for the same loan_installment_details_id.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.asserts import assert_loan_status  # noqa: E402
from flowtest.dateroll import (  # noqa: E402
    CHAIN_EOD,
    declare_layers,
    eod_ms_ist,
    roll,
)
from flowtest.db import psql  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore, resolve_fixture  # noqa: E402
from flowtest.invariants import finish_scenario, snapshot_invariants  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402
from flowtest.runner import fire_batch, max_batch_execution_id  # noqa: E402

import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD1_LAN", "6000137440")
JOB = "loanAccountBillingJob"
# Accrual only — billing fired twice in parallel below
CHAIN_ACCRUAL_ONLY = (CHAIN_EOD[0], CHAIN_EOD[1])


def _open_billing_gap(account_id: int) -> tuple[int, date]:
    row = psql(
        f"""
SELECT lid.id::text || '|' || lid.installment_date::date::text
FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id={account_id}
  AND COALESCE(lid.is_deleted,false)=false
  AND COALESCE(lid.settled_amount,0) < COALESCE(lid.installment_amount,0)
  AND EXISTS (
    SELECT 1 FROM mfi_accounting.loan_account_billing_details labd
    WHERE labd.loan_installment_details_id=lid.id)
ORDER BY lid.installment_date ASC, lid.id ASC
LIMIT 1
"""
    )
    if row and "|" in row:
        lid_s, due_s = row.split("|", 1)
        lid = int(lid_s)
        psql(
            f"""
WITH d AS (
  DELETE FROM mfi_accounting.loan_account_billing_details
  WHERE loan_installment_details_id={lid}
  RETURNING 1
)
SELECT COUNT(*)::text FROM d
"""
        )
        print(f"  seed: cleared labd for lid={lid} due={due_s}")
        return lid, date.fromisoformat(due_s)
    row2 = psql(
        f"""
SELECT lid.id::text || '|' || lid.installment_date::date::text
FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id={account_id}
  AND COALESCE(lid.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.loan_account_billing_details labd
    WHERE labd.loan_installment_details_id=lid.id)
ORDER BY lid.installment_date ASC, lid.id ASC
LIMIT 1
"""
    )
    if not row2 or "|" not in row2:
        raise RuntimeError("no installment for billing gap")
    lid_s, due_s = row2.split("|", 1)
    return int(lid_s), date.fromisoformat(due_s)


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.w3_batch_billing_overlap (W3-d overlapping billing) ===")
    print(f"  parent={PARENT} child={CHILD}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    parent_id, ids, _lans = resolve_fixture(PARENT)
    child_id = int(
        psql(
            f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}';"
        ).strip()
    )
    inv_baseline = snapshot_invariants([PARENT, CHILD])
    assert_loan_status(CHILD, "ACTIVE")

    lid, due = _open_billing_gap(child_id)
    bill_day = due + timedelta(days=1)
    labd_before = int(
        psql(
            f"SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details WHERE loan_installment_details_id={lid};"
        )
        or "0"
    )
    print(f"  setup: lid={lid} due={due} bill_day={bill_day} labd_before={labd_before}")

    result = roll(
        bill_day,
        bill_day,
        chain=CHAIN_ACCRUAL_ONLY,
        quarantine_parent_id=int(parent_id),
        quarantine_child_ids=[int(x) for x in ids if int(x) != int(parent_id)],
        timeout_s=int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "90")),
        layers_seeded=["labd_gap_for_billing_boundary"],
    )
    declare_layers(result)

    jt = eod_ms_ist(bill_day)
    min_eid = max_batch_execution_id(JOB)

    def _fire_one(tag: str) -> tuple[str, str]:
        # Identical job_time = true overlap race on same as-of
        fire_batch("loanAccountBillingJob", job_time=jt)
        return tag, jt

    print(f"  stimulus: TWO parallel loanAccountBillingJob fires job_time={jt}")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_fire_one, t) for t in ("A", "B")]
        for fut in as_completed(futs):
            tag, _ = fut.result()
            print(f"  fired tag={tag}")

    deadline = time.time() + 180
    statuses: list[str] = []
    while time.time() < deadline:
        rows = psql(
            f"""
SELECT string_agg(je.status, ',' ORDER BY je.job_execution_id)
FROM mfi_batch.batch_job_execution je
JOIN mfi_batch.batch_job_instance ji ON ji.job_instance_id=je.job_instance_id
WHERE ji.job_name='{JOB}' AND je.job_execution_id > {min_eid};
"""
        ).strip()
        if rows:
            statuses = [s for s in rows.split(",") if s]
            if len(statuses) >= 1 and all(s in ("COMPLETED", "FAILED", "STOPPED") for s in statuses):
                if len(statuses) >= 2 or time.time() > deadline - 10:
                    break
        time.sleep(2)
    print(f"  batch statuses after overlap: {statuses}")

    labd_after = int(
        psql(
            f"SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details WHERE loan_installment_details_id={lid};"
        )
        or "0"
    )
    print(f"  DB truth: labd_after={labd_after} (contract ≤1)")

    if labd_after > 1:
        defect = ROOT / "scripts/testing/defects/LMS-DEFECT-w3-batch-billing-double.md"
        defect.write_text(
            f"""# LMS-DEFECT — overlapping billing double labd (W3-d)

**Case:** flowtest.w3_batch_billing_overlap
**lid:** {lid} labd_after={labd_after} statuses={statuses}
**Contract:** overlapping loanAccountBillingJob must not create >1 labd per installment.
**STOP:** no product edit this wave.
"""
        )
        raise RuntimeError(f"CONTRACT FAIL labd_after={labd_after} — {defect}")

    if labd_after < 1:
        print("=== PARTIAL: flowtest.w3_batch_billing_overlap (0 labd; no double) ===")
        finish_scenario([PARENT, CHILD], baseline=inv_baseline, label="w3.batch_overlap")
        return 0

    print("  PASS contract: labd_after≤1; overlap did not double-bill")
    finish_scenario([PARENT, CHILD], baseline=inv_baseline, label="w3.batch_overlap")
    print("=== PASS: flowtest.w3_batch_billing_overlap ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"=== FAIL: flowtest.w3_batch_billing_overlap — {e} ===")
        raise
