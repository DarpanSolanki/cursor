#!/usr/bin/env python3
"""F1 pilot — RSTCRE spine via childLoanEventProcessingBatchJob (runtime).

Why not loanPrepayment/FC first: Vikram FC needs BRE + simulate/approve task surface;
RSTCRE drain already proven inside DFC — this isolates extraction cost, not new plumbing.

Flow:
  restore dcf_bak fixture → seed ONE non-last child DFC (SQL inbound + approve job)
  → fire childLoanEventProcessingBatchJob → assert RSTCRE drained + parent ACTIVE.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.asserts import (  # noqa: E402
    assert_account_status,
    assert_loan_status,
    snapshot_dues,
)
from flowtest.db import psql  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore  # noqa: E402
from flowtest.invariants import finish_scenario, snapshot_invariants  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.profiles import RSTCRE_SPINE  # noqa: E402
from flowtest.runner import fire_batch, max_batch_execution_id, wait_batch  # noqa: E402

# DFC-specific seed helpers (not extracted — stay in DFC monolith)
import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402


PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD_NON_LAST = os.environ.get("CHILD2_LAN", "6000137441")  # non-last in default DFC order
CHILD_REMAINING = os.environ.get("CHILD1_LAN", "6000137440")
DEATH_DATE = os.environ.get("DEATH_DATE", "2025-08-02")


def _ensure_stack() -> None:
    env = {**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"}
    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env=env,
    )


def assert_rstcre_drained(ctx: dict) -> None:
    parent_id = ctx["parent_id"]
    baseline = ctx["baseline_queue_id"]
    child = ctx["child_lan"]
    rows = dcf._rstcre_rows_since(parent_id, baseline)
    if not rows:
        raise AssertionError(
            f"RSTCRE drain FAIL: no RSTCRE row parent_id={parent_id} after {child} "
            f"(baseline={baseline})"
        )
    bad = []
    for row in rows:
        parts = row.split("|")
        if len(parts) < 5:
            continue
        qid, _etype, estatus, _ref, filler1 = parts[0], parts[1], parts[2], parts[3], parts[4]
        if estatus != "C":
            bad.append(f"id={qid} status={estatus}")
        if filler1 != "NULL":
            bad.append(f"id={qid} filler_1={filler1}")
    if bad:
        raise AssertionError(f"RSTCRE drain FAIL: {bad}; rows={rows}")
    print(f"  RSTCRE drain PASS: child={child} parent_id={parent_id} rows={rows}")


def main() -> int:
    acquire_flowtest_lock()
    # Nested DCF helpers that flock must see held
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    os.environ["FLOWTEST_E2E_LOCK_HELD"] = "1"
    # Pilot does not need EXTRA / EMI dirty seeds
    os.environ.setdefault("SEED_EXTRA", "0")
    os.environ.setdefault("DCF_SEED_EMI_LABD", "0")
    os.environ.setdefault("ACCEPTANCE_STRICT", "1")

    print("=== flowtest.rstcre_spine (F1 pilot) ===")
    print(f"  parent={PARENT} non_last={CHILD_NON_LAST} remaining={CHILD_REMAINING} death={DEATH_DATE}")

    inv_lans = [PARENT, CHILD_NON_LAST, CHILD_REMAINING]

    _ensure_stack()
    ensure_snapshot_or_restore(PARENT, RSTCRE_SPINE, force_restore=True)
    inv_baseline = snapshot_invariants(inv_lans)
    print(f"  invariants baseline: lans={inv_lans}")

    dcf.cleanup_abandoned_staging([CHILD_NON_LAST, CHILD_REMAINING])
    parent_id = dcf.parent_account_id(PARENT)
    dcf.cleanup_stale_rstcre_events(parent_id)
    dcf.reset_child_dfc_if_needed(CHILD_NON_LAST)
    dcf.prepare_fixture_pint_free(PARENT)

    snapshot_dues(PARENT, "parent-before")
    snapshot_dues(CHILD_NON_LAST, "child-before")

    baseline = dcf.latest_parent_event_id(PARENT)
    dfd_id, staging_id = dcf.seed_dfc_child(CHILD_NON_LAST, DEATH_DATE)
    dcf.cleanup_abandoned_staging(
        [CHILD_NON_LAST, CHILD_REMAINING], keep_staging_id=staging_id
    )
    dcf.run_inbound_approve_only(CHILD_NON_LAST, dfd_id, staging_id, DEATH_DATE)
    dcf.assert_child_closed(CHILD_NON_LAST)

    # Drain RSTCRE via shared runner fire/wait
    for attempt in range(1, 4):
        before = max_batch_execution_id("childLoanEventProcessingBatchJob")
        jt = fire_batch("childLoanEventProcessingBatchJob")
        print(f"  RSTCRE fire attempt={attempt} job_time={jt}")
        try:
            wait_batch("childLoanEventProcessingBatchJob", before, timeout_s=180)
        except RuntimeError as exc:
            print(f"  WARN: batch: {exc}")
        time.sleep(2)
        pending = psql(
            f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_events_queue
WHERE parent_account_id={parent_id} AND event_type='RSTCRE' AND is_deleted=false
  AND event_status NOT IN ('C', 'COMPLETED');
"""
        )
        if pending == "0":
            break
        if attempt == 3:
            raise RuntimeError(f"RSTCRE still PENDING={pending} after {attempt} fires")
        time.sleep(3)

    ctx = {
        "parent_id": parent_id,
        "baseline_queue_id": baseline,
        "child_lan": CHILD_NON_LAST,
    }
    assert_rstcre_drained(ctx)
    assert_loan_status(PARENT, "ACTIVE", label="parent-after-rstcre")
    assert_account_status(PARENT, "ACTIVE", label="parent-after-rstcre")
    assert_loan_status(CHILD_REMAINING, "ACTIVE", label="remaining-child")
    snapshot_dues(PARENT, "parent-after")

    print("=== PASS: flowtest.rstcre_spine ===")
    finish_scenario(inv_lans, baseline=inv_baseline, label="flowtest.rstcre_spine")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, RuntimeError, subprocess.CalledProcessError) as e:
        print(f"\nFAIL: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
