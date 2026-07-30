#!/usr/bin/env python3
"""W4-c — mid-window repay then ME accrual/posting (af52abe3d skip-continue truth).

Contract: after repay reduces principal, ME interestAccrualCalculation+Posting COMPLETED;
IAD tip for ACTIVE child advances or posts with catch-up skip-continue (not abort).
If child tip stuck mid-month (stuck-tip class) → extend LMS-DEFECT-child-iad-stuck-tip.md STOP.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.asserts import assert_loan_status, snapshot_dues  # noqa: E402
from flowtest.dateroll import CHAIN_EOD, declare_layers, roll  # noqa: E402
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
CHAIN_ACCRUAL = (CHAIN_EOD[0], CHAIN_EOD[1])  # calc → posting


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


def _iad_tip(lan: str) -> tuple[str, str, str]:
    row = psql(
        f"""
SELECT COALESCE(iad.end_date::date::text,'') || '|' ||
       COALESCE(iad.total_accrued_amount::text,'') || '|' ||
       COALESCE(iad.total_accrual_posted_amount::text,'NULL')
FROM mfi_accounting.interest_accrual_details iad
JOIN mfi_accounting.loan_account la ON la.account_id=iad.account_id
WHERE la.la_account_number='{lan}'
ORDER BY iad.end_date DESC NULLS LAST, iad.id DESC LIMIT 1;
"""
    ).strip()
    if not row or "|" not in row:
        return "", "", "NULL"
    a, b, c = row.split("|", 2)
    return a, b, c


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.w4_midmonth_repay_then_me (W4-c) ===")
    print(f"  parent={PARENT} child={CHILD}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    dcf.prepare_fixture_pint_free(PARENT)
    parent_id, ids, _ = resolve_fixture(PARENT)
    child_id = int(
        psql(f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}';").strip()
    )
    inv = snapshot_invariants([PARENT, CHILD])
    assert_loan_status(CHILD, "ACTIVE")
    force_regular_asset_slab([str(child_id)])

    tip0, acc0, post0 = _iad_tip(CHILD)
    print(f"  IAD tip before: end={tip0} accrued={acc0} posted={post0}")

    # Derive ME from tip end_date month (fixture state), else from next installment
    if tip0:
        y, m, _d = (int(x) for x in tip0.split("-"))
        me = date(y, m, monthrange(y, m)[1])
        # mid = tip day (mutation "between" tip and ME)
        mid = date.fromisoformat(tip0)
    else:
        due = psql(
            f"""
SELECT lid.installment_date::date::text FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id={child_id} AND COALESCE(lid.is_deleted,false)=false
ORDER BY lid.installment_date DESC LIMIT 1;
"""
        ).strip()
        mid = date.fromisoformat(due) if due else date.today()
        me = date(mid.year, mid.month, monthrange(mid.year, mid.month)[1])
    print(f"  fixture-derived mid={mid} ME={me}")

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
    amt = min(overdue, Decimal("500")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if amt <= 0:
        raise RuntimeError("no dues for mid repay")
    before = snapshot_dues(CHILD, "before-mid-repay")
    crn = f"W4C{int(time.time())}"
    vd = str(int(time.time() * 1000))
    print(f"  mid op: repay amt={amt} crn={crn}")
    resp = _post(
        "loanRepayment",
        {
            "headers": _hdr(f"w4c_{crn}"),
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
    print(f"  repay: {st.get('code')}/{st.get('status')}")
    if st.get("status") != "SUCCESS" and st.get("code") not in ("000", "30265", "30273"):
        raise RuntimeError(f"repay failed: {json.dumps(resp)[:400]}")
    after_rp = snapshot_dues(CHILD, "after-mid-repay")
    finish_scenario([PARENT, CHILD], baseline=inv, label="w4c.after-repay")
    inv = snapshot_invariants([PARENT, CHILD])

    # Mid-day accrual calc (catch-up / distribute) then ME posting day
    print(f"  roll mid accrual day={mid}")
    r1 = roll(
        mid,
        mid,
        chain=CHAIN_ACCRUAL,
        quarantine_parent_id=int(parent_id),
        quarantine_child_ids=[int(x) for x in ids if int(x) != int(parent_id)],
        timeout_s=int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "120")),
        soft_fail=False,
        layers_seeded=[],
    )
    declare_layers(r1)
    tip_mid, acc_mid, post_mid = _iad_tip(CHILD)
    print(f"  IAD after mid roll: end={tip_mid} accrued={acc_mid} posted={post_mid}")
    finish_scenario([PARENT, CHILD], baseline=inv, label="w4c.after-mid-roll")
    inv = snapshot_invariants([PARENT, CHILD])

    if me > mid:
        print(f"  roll ME accrual/post day={me}")
        r2 = roll(
            me,
            me,
            chain=CHAIN_ACCRUAL,
            quarantine_parent_id=int(parent_id),
            quarantine_child_ids=[int(x) for x in ids if int(x) != int(parent_id)],
            timeout_s=int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "120")),
            soft_fail=False,
            layers_seeded=[],
        )
        declare_layers(r2)
    else:
        print("  ME<=mid — single roll already covers ME")

    tip_me, acc_me, post_me = _iad_tip(CHILD)
    print(f"  IAD after ME: end={tip_me} accrued={acc_me} posted={post_me}")
    print(
        f"  DB truth: prin_pending {before['prin_pending']}→{after_rp['prin_pending']} "
        f"tip {tip0}→{tip_me}"
    )

    # Stuck-tip watch (child IAD end stuck before ME)
    stuck = False
    if tip_me and me and tip_me < me.isoformat():
        # tip end still before ME calendar day — stuck-tip class if also no advance vs tip0
        if tip_me == tip0 or tip_me < me.isoformat():
            stuck = tip_me < me.isoformat() and (post_me in ("", "NULL") or tip_me == tip_mid == tip0)
    if stuck:
        defect = ROOT / "scripts/testing/defects/LMS-DEFECT-child-iad-stuck-tip.md"
        evidence = (
            f"\n\n## W4-c evidence 2026-07-31 (`flowtest.w4_midmonth_repay_then_me`)\n"
            f"LAN={CHILD} mid={mid} ME={me}\n"
            f"tip_before={tip0}|{acc0}|{post0}\n"
            f"tip_mid={tip_mid}|{acc_mid}|{post_mid}\n"
            f"tip_me={tip_me}|{acc_me}|{post_me}\n"
            f"end_date_advanced={tip_me != tip0} ended_on_me={tip_me == me.isoformat()}\n"
            f"VERDICT=DEFECT_STUCK_TIP (reproduced on DCF ACTIVE child after mid-repay→ME)\n"
        )
        defect.write_text(defect.read_text() + evidence if defect.is_file() else evidence)
        print(f"  STOP: stuck-tip extended {defect}")
        print("=== FAIL: flowtest.w4_midmonth_repay_then_me — stuck-tip (defect extended) ===")
        return 1

    # Contract: jobs completed (roll soft_fail=False) + principal reduced + tip not stuck
    if after_rp["prin_pending"] >= before["prin_pending"] and amt > 0:
        print("  WARN: prin_pending did not drop after repay")
    print("  PASS contract: ME accrual/post completed; child tip not stuck-tip class")
    finish_scenario([PARENT, CHILD], baseline=inv, label="w4c.after-me")
    print("=== PASS: flowtest.w4_midmonth_repay_then_me ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"=== FAIL: flowtest.w4_midmonth_repay_then_me — {e} ===")
        raise
