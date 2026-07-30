#!/usr/bin/env python3
"""W4-b — repay BEFORE vs AFTER same billing EOD: both orders coherent.

Contract: both arms SUCCESS with balanced GL, no orphan dues; appropriation leaves
paid≤due. Orders may differ in INT/PRIN split when billing intervenes — that is OK
if both are money-coherent (not identical).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.asserts import assert_gl_balanced_txn, assert_loan_status, snapshot_dues  # noqa: E402
from flowtest.dateroll import CHAIN_ACCRUAL_BILLING, declare_layers, roll  # noqa: E402
from flowtest.db import psql  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore, resolve_fixture  # noqa: E402
from flowtest.invariants import finish_scenario, snapshot_invariants  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.loan_state import force_regular_asset_slab  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402

import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD1_LAN", "6000137440")
ACCT_URL = os.environ.get("ACCOUNTING_URL", "http://localhost:8002/accounting/api/v1")


def _post(api: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{ACCT_URL}/{api}", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def _hdr(stan: str) -> dict:
    return {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "end_channel_code": "NOVOPAY",
        "function_code": "DEFAULT",
        "function_sub_code": "WITHOUT_MAKER_CHECKER",
        "run_mode": "REAL",
        "operation_mode": "SELF",
        "locale": "en-in",
        "stan": stan,
        "transmission_datetime": str(int(time.time() * 1000)),
        "user_id": os.environ.get("ICF_USER_ID", "103"),
        "actor_type": "CUSTOMER",
        "user_handle_value": os.environ.get("ICF_USER_ID", "103"),
        "office_id": os.environ.get("ICF_OFFICE_ID", "2"),
    }


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
ORDER BY lid.installment_date ASC LIMIT 1
"""
    )
    if row and "|" in row:
        lid_s, due_s = row.split("|", 1)
        lid = int(lid_s)
        psql(
            f"WITH d AS (DELETE FROM mfi_accounting.loan_account_billing_details WHERE loan_installment_details_id={lid} RETURNING 1) SELECT COUNT(*)::text FROM d"
        )
        return lid, date.fromisoformat(due_s)
    row2 = psql(
        f"""
SELECT lid.id::text || '|' || lid.installment_date::date::text
FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id={account_id}
  AND COALESCE(lid.is_deleted,false)=false
  AND NOT EXISTS (SELECT 1 FROM mfi_accounting.loan_account_billing_details labd WHERE labd.loan_installment_details_id=lid.id)
ORDER BY lid.installment_date ASC LIMIT 1
"""
    )
    if not row2 or "|" not in row2:
        raise RuntimeError("no billing gap installment")
    a, b = row2.split("|", 1)
    return int(a), date.fromisoformat(b)


def _orphan(lan: str) -> int:
    return int(
        psql(
            f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{lan}' AND ldd.is_deleted=false
  AND (ldd.paid_amount < 0 OR ldd.due_amount < 0
       OR ldd.paid_amount > ldd.due_amount + COALESCE(ldd.waived_amount,0) + 1);
"""
        )
        or "0"
    )


def _repay(amt: Decimal, tag: str) -> str:
    # Keep CRN short/alphanumeric — 132161 on long/underscore tags
    crn = f"W4B{tag[0]}{int(time.time()) % 10**10}"
    vd = str(int(time.time() * 1000))
    resp = _post(
        "loanRepayment",
        {
            "headers": _hdr(f"w4b_{crn}"),
            "request": {
                "loan_repayment_details": {
                    "account_number": CHILD,
                    "repayment_amount": str(amt),
                    "repayment_time": vd,
                    "value_date": vd,
                    "repayment_mode": "CASH",
                    "receipt_number": crn,
                    "client_reference_number": crn,
                }
            },
        },
    )
    st = resp.get("response_status", {})
    print(f"  repay[{tag}] crn={crn}: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:100]}")
    if st.get("status") != "SUCCESS" and st.get("code") not in ("000", "30265", "30273"):
        raise RuntimeError(f"repay {tag} failed: {json.dumps(resp)[:400]}")
    ref = psql(
        f"SELECT tm.reference_number FROM mfi_accounting.transaction_master tm WHERE tm.client_reference_number='{crn}' ORDER BY tm.id DESC LIMIT 1;"
    ).strip()
    assert_gl_balanced_txn(ref, f"{CHILD}/{tag}")
    return ref


def _arm(order: str, parent_id: int, ids: list, child_id: int, amt: Decimal) -> dict[str, Any]:
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    dcf.prepare_fixture_pint_free(PARENT)
    force_regular_asset_slab([str(child_id)])
    inv = snapshot_invariants([PARENT, CHILD])
    lid, due = _open_billing_gap(child_id)
    bill_day = due + timedelta(days=1)
    print(f"  ARM {order}: lid={lid} due={due} bill_day={bill_day} amt={amt}")

    if order == "AFTER_EOD":
        result = roll(
            bill_day,
            bill_day,
            chain=CHAIN_ACCRUAL_BILLING,
            quarantine_parent_id=int(parent_id),
            quarantine_child_ids=[int(x) for x in ids if int(x) != int(parent_id)],
            timeout_s=int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "90")),
            layers_seeded=["labd_gap"],
        )
        declare_layers(result)
        finish_scenario([PARENT, CHILD], baseline=inv, label=f"w4b.{order}.eod")
        inv = snapshot_invariants([PARENT, CHILD])
        before = snapshot_dues(CHILD, f"{order}-before-repay")
        ref = _repay(amt, order)
        after = snapshot_dues(CHILD, f"{order}-after-repay")
    else:  # BEFORE_EOD
        before = snapshot_dues(CHILD, f"{order}-before-repay")
        ref = _repay(amt, order)
        finish_scenario([PARENT, CHILD], baseline=inv, label=f"w4b.{order}.repay")
        inv = snapshot_invariants([PARENT, CHILD])
        result = roll(
            bill_day,
            bill_day,
            chain=CHAIN_ACCRUAL_BILLING,
            quarantine_parent_id=int(parent_id),
            quarantine_child_ids=[int(x) for x in ids if int(x) != int(parent_id)],
            timeout_s=int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "90")),
            layers_seeded=["labd_gap"],
        )
        declare_layers(result)
        after = snapshot_dues(CHILD, f"{order}-after-eod")

    orphans = _orphan(CHILD)
    labd = int(
        psql(
            f"SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details WHERE loan_installment_details_id={lid};"
        )
        or "0"
    )
    finish_scenario([PARENT, CHILD], baseline=inv, label=f"w4b.{order}.final")
    print(
        f"  ARM {order} truth: ref={ref} orphans={orphans} labd={labd} "
        f"prin_paid {before['prin_paid']}→{after['prin_paid']}"
    )
    if orphans > 0:
        raise RuntimeError(f"CONTRACT FAIL {order} orphans={orphans}")
    if labd < 1:
        raise RuntimeError(f"CONTRACT FAIL {order} no labd after billing path")
    return {"order": order, "ref": ref, "orphans": orphans, "labd": labd, "before": before, "after": after}


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.w4_repay_before_vs_after_eod (W4-b) ===")
    print(f"  parent={PARENT} child={CHILD}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    parent_id, ids, _ = resolve_fixture(PARENT)
    # resolve after restore in arm; get child_id from live
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    parent_id, ids, _ = resolve_fixture(PARENT)
    child_id = int(
        psql(f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}';").strip()
    )
    assert_loan_status(CHILD, "ACTIVE")
    overdue = Decimal(
        psql(
            f"""
SELECT COALESCE(SUM(due_amount-paid_amount-COALESCE(waived_amount,0)),0)::text
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{CHILD}' AND ldd.is_deleted=false
  AND (due_amount-paid_amount-COALESCE(waived_amount,0))>0;
"""
        )
        or "0"
    )
    amt = min(overdue, Decimal("400")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if amt <= 0:
        raise RuntimeError("no dues")

    a1 = _arm("BEFORE_EOD", parent_id, ids, child_id, amt)
    a2 = _arm("AFTER_EOD", parent_id, ids, child_id, amt)
    print(
        f"  compare: BEFORE paid_delta={a1['after']['prin_paid']-a1['before']['prin_paid']} "
        f"AFTER paid_delta={a2['after']['prin_paid']-a2['before']['prin_paid']} "
        f"(need not equal — both coherent)"
    )
    print("  PASS contract: both orders coherent (no orphans, labd present, GL OK)")
    print("=== PASS: flowtest.w4_repay_before_vs_after_eod ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"=== FAIL: flowtest.w4_repay_before_vs_after_eod — {e} ===")
        raise
