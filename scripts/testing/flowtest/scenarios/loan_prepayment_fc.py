#!/usr/bin/env python3
"""F2 — foreclosure via individualChildLoanForeclosure on DCF group child.

Reshape: dpic DPI restore needs dpiAccrualCalculation orch (absent on acc 3.4.2.4).
Vikram loanPrepayment parent AUTO settle hits 134207. Lift ICF ntest onto restored
dcf_bak child instead (BRE stub + foreclosure PTC setup).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.asserts import (  # noqa: E402
    assert_gl_balanced_txn,
    assert_loan_status,
    assert_webapp_summary_accrued_le_original,
    snapshot_dues,
)
from flowtest.db import psql  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402

import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD2_LAN", "6000137441")
DEATH_DATE = os.environ.get("DEATH_DATE", "2025-08-02")


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    os.environ["FLOWTEST_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.loan_prepayment_fc (F2 — ICF on DCF child) ===")
    print(f"  parent={PARENT} child={CHILD}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    subprocess.check_call(["bash", str(ROOT / "scripts/bin/foreclosure-local-setup.sh")])
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.prepare_fixture_pint_free(PARENT)
    dcf.ensure_fixture_accounts_active(PARENT)

    # ICF needs valueDate <= FD < maturity AND an INTEREST due AFTER prevDueDate
    # (134292 / 134291 / 132381 / "No current installment"). DCF bak matured
    # 2026-05-01; platform today is past that — push last schedule+dues past today.
    fc_date = dcf._vikram_fc_date(DEATH_DATE)  # >= platform today
    n = psql(
        f"""
WITH la AS (
  SELECT account_id FROM mfi_accounting.loan_account
  WHERE la_account_number = '{CHILD}'
),
last_lid AS (
  SELECT lid.id
  FROM mfi_accounting.loan_installment_details lid
  JOIN la ON lid.loan_account_id = la.account_id
  WHERE lid.is_deleted = false
  ORDER BY lid.installment_date DESC
  LIMIT 1
),
u1 AS (
  UPDATE mfi_accounting.loan_account x
  SET maturity_date = (CURRENT_DATE + INTERVAL '180 days')::timestamp,
      updated_on = NOW(), updated_by = 'FLOWTEST_F2_FC_WINDOW'
  FROM la WHERE x.account_id = la.account_id
    AND x.maturity_date::date <= CURRENT_DATE + INTERVAL '60 days'
  RETURNING 1
),
u2 AS (
  UPDATE mfi_accounting.loan_installment_details lid
  SET installment_date = (CURRENT_DATE + INTERVAL '30 days')::timestamp,
      updated_on = NOW(), updated_by = 'FLOWTEST_F2_FC_WINDOW'
  FROM last_lid
  WHERE lid.id = last_lid.id
    AND lid.installment_date::date <= CURRENT_DATE + INTERVAL '7 days'
  RETURNING 1
),
u3 AS (
  UPDATE mfi_accounting.loan_due_details ldd
  SET due_date = (CURRENT_DATE + INTERVAL '30 days')::timestamp,
      overdue_date = (CURRENT_DATE + INTERVAL '30 days')::timestamp,
      updated_on = NOW(), updated_by = 'FLOWTEST_F2_FC_WINDOW'
  FROM last_lid
  WHERE ldd.loan_installment_details_id = last_lid.id
    AND ldd.is_deleted = false
    AND ldd.due_date::date <= CURRENT_DATE + INTERVAL '7 days'
  RETURNING 1
)
SELECT (SELECT COUNT(*) FROM u1)::text || ',' ||
       (SELECT COUNT(*) FROM u2)::text || ',' ||
       (SELECT COUNT(*) FROM u3)::text;
"""
    ).strip()
    print(f"  FC window hygiene: maturity/lid/dues bumps={n}")
    fd_ms = dcf._eod_ms_ist(fc_date)
    print(f"  ICF FD={fc_date} ({fd_ms} ms) death={DEATH_DATE}")
    os.environ["ICF_LAN"] = CHILD
    os.environ["ICF_FORECLOSURE_DATE"] = fd_ms
    os.environ["ICF_EXPECT_CODE"] = os.environ.get("ICF_EXPECT_CODE", "30267")
    os.environ["ICF_OFFICE_ID"] = os.environ.get("ICF_OFFICE_ID", "2")

    before = snapshot_dues(CHILD, "before-icf")
    if before["loan_status"] != "ACTIVE":
        raise RuntimeError(f"expected ACTIVE child after restore, got {before['loan_status']}")

    # Lift DCF Sim A (ICF) — uses _lp_build_request + loan office_id (avoids 132268
    # from ntest total mismatch). loanPrepayment Vikram stays SU-FLOW-PREPAY-VIKRAM.
    os.environ["ICF_USE_LOAN_PREPAYMENT"] = "0"
    dcf.VIKRAM_USE_LOAN_PREPAYMENT = False
    dcf._run_child_fc_via_individual_child(CHILD, DEATH_DATE)

    assert_loan_status(CHILD, "CLOSED", label="after-ICF")
    after = snapshot_dues(CHILD, "after-icf")
    if after["prin_pending"] != 0:
        raise AssertionError(f"dues not zeroed prin_pending={after['prin_pending']}")
    print("  dues PASS: prin_pending=0")

    # Closure refs via lacd / LOAN_PREPAYMENT (tm has no created_on)
    try:
        from flowtest.asserts import assert_gl_balance_for_loan  # noqa: WPS433

        assert_gl_balance_for_loan(CHILD, ["LOAN_PREPAYMENT"])
    except AssertionError:
        ref = psql(
            f"""
SELECT lacd.transaction_reference_number
FROM mfi_accounting.loan_account_closure_details lacd
JOIN mfi_accounting.loan_account la ON la.account_id = lacd.loan_account_id
WHERE la.la_account_number = '{CHILD}'
ORDER BY lacd.id DESC LIMIT 1;
"""
        ).strip()
        if not ref:
            raise AssertionError("no closure txn ref after ICF") from None
        assert_gl_balanced_txn(ref, f"{CHILD}/icf-closure")
    assert_loan_status(PARENT, "ACTIVE", label="parent-active")
    assert_webapp_summary_accrued_le_original(CHILD, role="icf-child")

    print("=== PASS: flowtest.loan_prepayment_fc ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, RuntimeError, subprocess.CalledProcessError) as e:
        print(f"\nFAIL: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
