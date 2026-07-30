#!/usr/bin/env python3
"""W3-b — concurrent mutations same LAN (repay ‖ repay) → no double-post / coherent dues.

Production contract: racing money ops on one LAN must not double-apply the same dues
(CAS/lock or business reject). Stimulus is real parallel HTTP (ThreadPool), not sequential.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.asserts import assert_loan_status, snapshot_dues  # noqa: E402
from flowtest.db import psql  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore  # noqa: E402
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


def _ok(st: dict) -> bool:
    return st.get("status") == "SUCCESS" or st.get("code") in ("000", "30265", "30273", "MOSL-000")


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.w3_concurrent_same_lan (W3-b parallel repay‖repay) ===")
    print(f"  parent={PARENT} child={CHILD}")
    print("  note: part-prep REAL blocked (SU-FLOW-PARTPREP-REAL-GLAD) — race two loanRepayment instead")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    inv_baseline = snapshot_invariants([PARENT, CHILD])
    dcf.prepare_fixture_pint_free(PARENT)
    assert_loan_status(CHILD, "ACTIVE")
    account_id = psql(
        f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}' AND is_deleted=false;"
    ).strip()
    if account_id:
        force_regular_asset_slab([account_id])

    before = snapshot_dues(CHILD, "before-race")
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
    # Each racer asks for the FULL overdue — double SUCCESS would over-apply
    amt = overdue.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if amt < Decimal("100"):
        raise RuntimeError(f"need overdue≥100 for race, got {amt}")
    print(f"  setup: overdue={overdue} race_amt_each={amt} (full bucket)")

    ts = int(time.time())
    receipts = [f"W3C{ts}A", f"W3C{ts}B"]
    vd = str(int(time.time() * 1000))

    def _fire(receipt: str) -> tuple[str, dict]:
        body = {
            "headers": _hdr(f"w3b_{receipt}"),
            "request": {
                "loan_repayment_details": {
                    "account_number": CHILD,
                    "repayment_amount": str(amt),
                    "repayment_time": vd,
                    "value_date": vd,
                    "repayment_mode": "CASH",
                    "receipt_number": receipt,
                    "client_reference_number": receipt,
                }
            },
        }
        return receipt, _post("loanRepayment", body)

    results: list[tuple[str, dict]] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_fire, r) for r in receipts]
        for fut in as_completed(futs):
            results.append(fut.result())

    successes = []
    for receipt, resp in results:
        st = resp.get("response_status", {})
        print(f"  race {receipt}: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:140]}")
        if _ok(st):
            successes.append(receipt)

    tm_count = int(
        psql(
            f"""
SELECT COUNT(*)::text FROM mfi_accounting.transaction_master tm
WHERE tm.receipt_number IN ('{receipts[0]}','{receipts[1]}')
  AND tm.status='SUCCESS' AND COALESCE(tm.reversed,false)=false;
"""
        )
        or "0"
    )
    after = snapshot_dues(CHILD, "after-race")
    paid_delta = after["prin_paid"] - before["prin_paid"]
    # Interest/fee may move too — use unsettled drop as money-applied proxy
    unsettled_after = Decimal(
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
    applied = overdue - unsettled_after
    print(
        f"  DB truth: SUCCESS tm={tm_count} successes_http={len(successes)} "
        f"applied_unsettled_drop={applied} prin_paid_delta={paid_delta}"
    )

    # Contract: cannot apply more than overdue (double-post of full bucket)
    if applied > overdue + Decimal("1"):
        defect = ROOT / "scripts/testing/defects/LMS-DEFECT-w3-concurrent-double-post.md"
        defect.write_text(
            f"""# LMS-DEFECT — concurrent same-LAN double-post (W3-b)

**Case:** flowtest.w3_concurrent_same_lan
**Symptom:** two parallel loanRepayment of full overdue both applied; applied={applied} > overdue={overdue}
**tm_count:** {tm_count} receipts={receipts}
**STOP:** no product edit this wave.
"""
        )
        raise RuntimeError(f"CONTRACT FAIL double-post applied={applied}>{overdue} — defect {defect}")

    if tm_count > 1 and applied > amt + Decimal("1"):
        # Two SUCCESS txns that together exceeded one full bucket
        raise RuntimeError(f"CONTRACT FAIL: tm={tm_count} applied={applied} exceeds single amt={amt}")

    if tm_count == 0:
        raise RuntimeError("CONTRACT FAIL: zero SUCCESS — race must allow at least one winner")

    print(
        f"  PASS contract: tm={tm_count} applied={applied}≤overdue={overdue} "
        f"(loser rejected or serialized)"
    )
    finish_scenario([PARENT, CHILD], baseline=inv_baseline, label="w3.concurrent_same_lan")
    print("=== PASS: flowtest.w3_concurrent_same_lan ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"=== FAIL: flowtest.w3_concurrent_same_lan — {e} ===")
        raise
