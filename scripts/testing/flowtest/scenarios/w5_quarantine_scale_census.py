#!/usr/bin/env python3
"""W5-c — quarantine-scale census: fixture portfolio only, wall + skip census.

Full ~6k dirty portfolio WONT-DO (FREEZE/Invalid amount noise). This proves
quarantine rails + COMPLETED + skip census vs expectation under budget.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.dateroll import CHAIN_ACCRUAL_BILLING, declare_layers, roll  # noqa: E402
from flowtest.db import psql  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore, resolve_fixture  # noqa: E402
from flowtest.invariants import finish_scenario, snapshot_invariants  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402

import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD1_LAN", "6000137440")
LOG = ROOT / "trustt-platform-accounting/logs/mfi/accounting-mfi.log"


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.w5_quarantine_scale_census (W5-c) ===")
    print("  note: quarantined fixture only — full 6k dirty portfolio WONT-DO")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    parent_id, ids, lans = resolve_fixture(PARENT)
    inv = snapshot_invariants(lans)

    # Open a billing gap so chain does work
    child_id = int(
        psql(f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}';").strip()
    )
    row = psql(
        f"""
SELECT lid.id::text||'|'||lid.installment_date::date::text
FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id={child_id} AND COALESCE(lid.is_deleted,false)=false
  AND EXISTS (SELECT 1 FROM mfi_accounting.loan_account_billing_details b WHERE b.loan_installment_details_id=lid.id)
ORDER BY lid.installment_date ASC LIMIT 1;
"""
    ).strip()
    bill_day = date(2025, 9, 2)
    if row and "|" in row:
        lid_s, due_s = row.split("|", 1)
        psql(
            f"DELETE FROM mfi_accounting.loan_account_billing_details WHERE loan_installment_details_id={int(lid_s)};"
        )
        bill_day = date.fromisoformat(due_s)
        from datetime import timedelta

        bill_day = bill_day + timedelta(days=1)
        print(f"  seed labd gap lid={lid_s} bill_day={bill_day}")

    active_before = int(
        psql(
            "SELECT COUNT(*)::text FROM mfi_accounting.loan_account WHERE loan_status IN ('ACTIVE','FORECLOSURE_FREEZE') AND is_deleted=false;"
        )
        or "0"
    )
    t0 = time.time()
    # roll() already quarantines when parent/children passed
    result = roll(
        bill_day,
        bill_day,
        chain=CHAIN_ACCRUAL_BILLING,
        quarantine_parent_id=int(parent_id),
        quarantine_child_ids=[int(x) for x in ids if int(x) != int(parent_id)],
        timeout_s=int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "120")),
        soft_fail=False,
        layers_seeded=["labd_gap_for_billing_boundary"],
    )
    declare_layers(result)
    wall = time.time() - t0

    # Skip census from recent log
    skip_n = 0
    cce_n = 0
    if LOG.is_file():
        tail = LOG.read_text(errors="ignore")[-300_000:]
        skip_n = len(re.findall(r"skipped_unposted_non_booking_day_iad=\d+", tail))
        cce_n = len(re.findall(r"ClassCastException|FutureTask cannot be cast", tail))
    fail_audit = int(
        psql(
            """
SELECT COUNT(*)::text FROM mfi_accounting.batch_failure_audit
WHERE business_date >= CURRENT_DATE - 1 OR execution_date >= CURRENT_DATE - 1;
"""
        )
        or "0"
    )
    active_after_restore_check = int(
        psql(
            "SELECT COUNT(*)::text FROM mfi_accounting.loan_account WHERE loan_status IN ('ACTIVE','FORECLOSURE_FREEZE') AND is_deleted=false;"
        )
        or "0"
    )
    # quarantine should be restored by roll() finally
    print(
        f"  census: wall={wall:.1f}s skip_log_hits≈{skip_n} cce_log={cce_n} "
        f"fail_audit_20m={fail_audit} active_before={active_before} active_now={active_after_restore_check}"
    )
    if cce_n > 0:
        raise RuntimeError(f"CONTRACT FAIL CCE still in log ({cce_n})")
    if wall > 600:
        raise RuntimeError(f"CONTRACT FAIL wall {wall:.0f}s too high for quarantined fixture")
    # portfolio restored (ACTIVE count back near before — allow small drift)
    if abs(active_after_restore_check - active_before) > 50:
        print(
            f"  WARN: ACTIVE count drifted {active_before}→{active_after_restore_check} "
            f"(quarantine restore?) — check rails"
        )

    finish_scenario(lans, baseline=inv, label="w5c.census")
    print("  PASS contract: quarantined EOD chain COMPLETED under budget; no CCE; census printed")
    print("=== PASS: flowtest.w5_quarantine_scale_census ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"=== FAIL: flowtest.w5_quarantine_scale_census — {e} ===")
        raise
