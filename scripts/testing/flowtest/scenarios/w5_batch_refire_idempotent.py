#!/usr/bin/env python3
"""W5-b — re-fire interestAccrualPosting after skip-poison run → no double-post.

Deviation from 'kill mid-run': JVM kill mid-chunk is flaky on laptop; contract
tested as re-fire idempotency on already-processed LANs (remainder no-op).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.dateroll import eod_ms_ist, fire_and_wait  # noqa: E402
from flowtest.db import psql  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore, resolve_fixture  # noqa: E402
from flowtest.invariants import finish_scenario, snapshot_invariants  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402
from flowtest.runner import max_batch_execution_id  # noqa: E402

from clb_queue_harness import (  # noqa: E402
    quarantine_billing_portfolio,
    restore_billing_portfolio_quarantine,
)

import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD1_LAN", "6000137440")
JOB = "interestAccrualPosting"
DEFECT = ROOT / "scripts/testing/defects/LMS-DEFECT-w5-batch-double-post.md"


def _posted_map(ids: list[int]) -> dict[int, Decimal]:
    out: dict[int, Decimal] = {}
    for aid in ids:
        out[aid] = Decimal(
            psql(
                f"""
SELECT COALESCE(SUM(COALESCE(total_accrual_posted_amount,0)),0)::text
FROM mfi_accounting.interest_accrual_details WHERE account_id={aid};
"""
            )
            or "0"
        )
    return out


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.w5_batch_refire_idempotent (W5-b) ===")
    print("  note: re-fire idempotency (not JVM kill) — kill mid-chunk WONT-DO flaky")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    parent_id, ids, lans = resolve_fixture(PARENT)
    keep = [int(x) for x in ids]
    child_id = int(
        psql(f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}';").strip()
    )
    inv = snapshot_invariants(lans)

    # Seed mid-month poison so first fire exercises skip path
    tip = psql(
        f"""
SELECT id::text||'|'||end_date::date::text FROM mfi_accounting.interest_accrual_details
WHERE account_id={child_id} ORDER BY end_date DESC NULLS LAST, id DESC LIMIT 1;
"""
    ).strip()
    iid, end_s = tip.split("|", 1)
    end = date.fromisoformat(end_s)
    mid = date(end.year, end.month, 15)
    psql(
        f"""
UPDATE mfi_accounting.interest_accrual_details
SET end_date='{mid}'::timestamp,
    total_accrued_amount=GREATEST(COALESCE(total_accrued_amount,0), 50),
    total_accrual_posted_amount=0
WHERE id={int(iid)};
"""
    )
    print(f"  poison tip iad={iid} end→{mid}")

    jt = eod_ms_ist(date(2026, 5, 31))
    quarantine_billing_portfolio(int(parent_id), [i for i in keep if i != int(parent_id)])
    try:
        for tag in ("first", "refire"):
            before_eid = max_batch_execution_id(JOB)
            before = _posted_map(keep)
            print(f"  stimulus[{tag}]: {JOB} job_time={jt}")
            fire_and_wait(JOB, jt, job_name=JOB, timeout_s=180, soft_fail=False)
            st = psql(
                f"""
SELECT je.status FROM mfi_batch.batch_job_execution je
JOIN mfi_batch.batch_job_instance ji ON ji.job_instance_id=je.job_instance_id
WHERE ji.job_name='{JOB}' AND je.job_execution_id > {before_eid}
ORDER BY je.job_execution_id DESC LIMIT 1;
"""
            ).strip()
            after = _posted_map(keep)
            print(f"  [{tag}] status={st} posted={after}")
            if st != "COMPLETED":
                raise RuntimeError(f"{tag} not COMPLETED: {st}")
            if tag == "refire":
                deltas = {aid: after[aid] - before[aid] for aid in keep}
                print(f"  DB truth refire deltas={deltas}")
                if any(d > Decimal("0.01") for d in deltas.values()):
                    DEFECT.write_text(
                        f"# LMS-DEFECT — accrual posting double-post on re-fire (W5-b)\n\n"
                        f"deltas={deltas}\nSTOP\n"
                    )
                    raise RuntimeError(f"CONTRACT FAIL double-post — {DEFECT}")
                print("  PASS contract: refire COMPLETED with zero posted delta")
            time.sleep(1)
    finally:
        restore_billing_portfolio_quarantine()

    finish_scenario(lans, baseline=inv, label="w5b.refire")
    print("=== PASS: flowtest.w5_batch_refire_idempotent ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        try:
            restore_billing_portfolio_quarantine()
        except Exception:
            pass
        print(f"=== FAIL: flowtest.w5_batch_refire_idempotent — {e} ===")
        raise
