#!/usr/bin/env python3
"""F3 FLOW A — accrual calc → posting → billing across one billing boundary.

Uses dateroll with synthetic job_time (due+1 EOD). Quarantines portfolio to
fixture LANs. Asserts: labd created, IAD formula vs product day-count, GL on
new INTEREST/BILLING txns.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.asserts import assert_gl_balanced_txn, assert_loan_status  # noqa: E402
from flowtest.dateroll import (  # noqa: E402
    CHAIN_ACCRUAL_BILLING,
    declare_layers,
    roll,
)
from flowtest.db import psql, psql_raw  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore, resolve_fixture  # noqa: E402
from flowtest.invariants import finish_scenario, snapshot_invariants  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402

import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD1_LAN", "6000137440")


def _open_billing_boundary(account_id: int) -> tuple[int, date]:
    """Ensure ≥1 billing boundary: delete labd on first unsettled installment.

    Bak often already has labd for every EMI — without this gap, billing is a no-op.
    Coverage: labd_gap=SEEDED, jobs=REAL.
    """
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
    if not row or "|" not in row:
        # Fallback: any installment without labd
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
            raise RuntimeError(f"no installment to open billing boundary for account_id={account_id}")
        lid_s, due_s = row2.split("|", 1)
        return int(lid_s), date.fromisoformat(due_s)

    lid_s, due_s = row.split("|", 1)
    lid = int(lid_s)
    # Soft-remove labd only (txn purge left to fixture restore next run).
    n = psql(
        f"""
WITH d AS (
  DELETE FROM mfi_accounting.loan_account_billing_details
  WHERE loan_installment_details_id={lid}
  RETURNING 1
)
SELECT COUNT(*)::text FROM d
"""
    )
    print(f"  seed: removed labd count={n} for lid={lid} due={due_s} (SEEDED billing gap)")
    return lid, date.fromisoformat(due_s)


def _assert_iad_formula(account_id: int) -> None:
    """Assert one IAD period ≈ base * rate/100 / day_count * days (±₹2).

    Tries 360-day (common MFI) then 365-day conventions.
    """
    row = psql(
        f"""
SELECT base_amount::text || '|' || interest_rate::text || '|' ||
       total_accrued_amount::text || '|' ||
       (end_date::date - start_date::date)::text || '|' || end_date::date::text
FROM mfi_accounting.interest_accrual_details
WHERE account_id={account_id} AND COALESCE(total_accrued_amount,0) > 0
ORDER BY end_date DESC
LIMIT 1
"""
    )
    if not row:
        raise AssertionError("IAD formula FAIL: no positive total_accrued_amount row")
    base_s, rate_s, accrued_s, days_s, end_s = row.split("|")
    base = Decimal(base_s)
    rate = Decimal(rate_s)
    accrued = Decimal(accrued_s).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    days = int(days_s)
    if days <= 0:
        raise AssertionError(f"IAD formula FAIL: non-positive days={days} end={end_s}")
    best = None
    for day_count in (360, 365):
        expected = (base * rate / Decimal("100") / Decimal(day_count) * Decimal(days)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        diff = abs(expected - accrued)
        if best is None or diff < best[0]:
            best = (diff, expected, day_count)
        if diff <= Decimal("2"):
            print(
                f"  IAD formula PASS: end={end_s} accrued={accrued} ≈ {expected} "
                f"(base={base} rate={rate}% days={days} /{day_count})"
            )
            return
    assert best is not None
    raise AssertionError(
        f"IAD formula FAIL end={end_s}: expected≈{best[1]} (/{best[2]}) got={accrued} "
        f"base={base} rate={rate} days={days} diff={best[0]}"
    )


def _new_txn_refs(lan: str, txn_type: str, since_id: int) -> list[str]:
    out = psql_raw(
        f"""
SELECT DISTINCT tm.reference_number
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id=tm.id
WHERE td.account_number='{lan}' AND tc.type='{txn_type}' AND tm.id > {since_id}
ORDER BY 1
"""
    ).strip()
    return [r.strip() for r in out.splitlines() if r.strip()]


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    os.environ["FLOWTEST_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.accrual_billing (F3 FLOW A) ===")
    print(f"  parent={PARENT} child={CHILD}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    assert_loan_status(CHILD, "ACTIVE")
    inv_baseline = snapshot_invariants([PARENT, CHILD])

    parent_id, ids, _lans = resolve_fixture(PARENT)
    child_id = int(
        psql(
            f"SELECT account_id FROM mfi_accounting.loan_account "
            f"WHERE la_account_number='{CHILD}' AND is_deleted=false"
        )
    )
    lid, due = _open_billing_boundary(child_id)
    bill_day = due + timedelta(days=1)
    print(f"  billing boundary lid={lid} due={due} job_day={bill_day} (due+1)")

    max_tm = int(
        psql("SELECT COALESCE(MAX(id),0) FROM mfi_accounting.transaction_master") or "0"
    )

    result = roll(
        bill_day,
        bill_day,
        chain=CHAIN_ACCRUAL_BILLING,
        quarantine_parent_id=int(parent_id),
        quarantine_child_ids=[int(x) for x in ids if int(x) != int(parent_id)],
        timeout_s=int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "90")),
        layers_seeded=["labd_gap_for_billing_boundary"],
    )
    declare_layers(result)

    labd = psql(
        f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details
WHERE loan_installment_details_id={lid}
"""
    )
    if int(labd or "0") < 1:
        raise AssertionError(f"labd FAIL: no billing row for lid={lid} after roll")
    print(f"  labd PASS: count={labd} for lid={lid}")

    _assert_iad_formula(child_id)

    billing_refs = _new_txn_refs(CHILD, "BILLING", max_tm)
    interest_refs = _new_txn_refs(CHILD, "INTEREST", max_tm)
    if not billing_refs:
        raise AssertionError("GL FAIL: no new BILLING txn after billing boundary roll")
    for ref in billing_refs:
        assert_gl_balanced_txn(ref, f"{CHILD}/BILLING")
    for ref in interest_refs:
        assert_gl_balanced_txn(ref, f"{CHILD}/INTEREST", allow_empty=False)

    print(
        f"  LAYERS_DECLARE: jobs=REAL(accrual_calc,accrual_post,billing) "
        f"aging=N/A labd_gap=SEEDED formula=on_IAD_row"
    )
    finish_scenario([PARENT, CHILD], baseline=inv_baseline, label="flowtest.accrual_billing")
    print("=== PASS: flowtest.accrual_billing ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"=== FAIL: flowtest.accrual_billing: {exc} ===")
        raise
