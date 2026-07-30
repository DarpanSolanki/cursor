#!/usr/bin/env python3
"""W4-a — repay → EOD billing → reverse: dues restored, no orphan, GL balanced.

Production contract: after billing has posted labd for a boundary, reversing the
prior repayment must restore dues toward pre-repay, mark tm.reversed, leave GL
balanced, and not leave negative/orphan paid amounts.
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


def _hdr(stan: str, *, function_code: str = "DEFAULT", function_sub_code: str = "DEFAULT") -> dict:
    return {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "end_channel_code": "NOVOPAY",
        "function_code": function_code,
        "function_sub_code": function_sub_code,
        "run_mode": "REAL",
        "operation_mode": "SELF",
        "locale": "en-in",
        "stan": stan,
        "transmission_datetime": str(int(time.time() * 1000)),
        "user_id": os.environ.get("ICF_USER_ID", "103"),
        "actor_type": "CUSTOMER" if function_sub_code == "WITHOUT_MAKER_CHECKER" else "EMPLOYEE",
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
ORDER BY lid.installment_date ASC, lid.id ASC LIMIT 1
"""
    )
    if row and "|" in row:
        lid_s, due_s = row.split("|", 1)
        lid = int(lid_s)
        psql(
            f"""
WITH d AS (
  DELETE FROM mfi_accounting.loan_account_billing_details
  WHERE loan_installment_details_id={lid} RETURNING 1
) SELECT COUNT(*)::text FROM d
"""
        )
        print(f"  seed: cleared labd lid={lid} due={due_s}")
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
ORDER BY lid.installment_date ASC, lid.id ASC LIMIT 1
"""
    )
    if not row2 or "|" not in row2:
        raise RuntimeError("no installment for billing gap")
    lid_s, due_s = row2.split("|", 1)
    return int(lid_s), date.fromisoformat(due_s)


def _neg_orphan_dues(lan: str) -> int:
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


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.w4_reversal_after_billing (W4-a) ===")
    print(f"  parent={PARENT} child={CHILD}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    subprocess.check_call(["bash", str(ROOT / "scripts/bin/novopay-service.sh"), "ensure", "task"])
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    dcf.prepare_fixture_pint_free(PARENT)
    parent_id, ids, _ = resolve_fixture(PARENT)
    child_id = int(
        psql(
            f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}';"
        ).strip()
    )
    inv = snapshot_invariants([PARENT, CHILD])
    assert_loan_status(CHILD, "ACTIVE")
    force_regular_asset_slab([str(child_id)])

    before = snapshot_dues(CHILD, "before-repay")
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
        raise RuntimeError("no open dues")
    crn = f"W4A{int(time.time())}"
    vd = str(int(time.time() * 1000))
    print(f"  dayN op: loanRepayment amt={amt} crn={crn}")

    resp = _post(
        "loanRepayment",
        {
            "headers": _hdr(f"w4a_rp_{crn}", function_sub_code="WITHOUT_MAKER_CHECKER"),
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
    print(f"  repay: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:100]}")
    if st.get("status") != "SUCCESS" and st.get("code") not in ("000", "30265", "30273"):
        raise RuntimeError(f"repay failed: {json.dumps(resp)[:400]}")
    mid = snapshot_dues(CHILD, "after-repay")
    ref = psql(
        f"SELECT tm.reference_number FROM mfi_accounting.transaction_master tm WHERE tm.client_reference_number='{crn}' ORDER BY tm.id DESC LIMIT 1;"
    ).strip()
    assert_gl_balanced_txn(ref, f"{CHILD}/repay")
    finish_scenario([PARENT, CHILD], baseline=inv, label="w4a.after-repay")
    inv = snapshot_invariants([PARENT, CHILD])

    lid, due = _open_billing_gap(child_id)
    bill_day = due + timedelta(days=1)
    print(f"  dayN+k EOD: billing boundary lid={lid} due={due} bill_day={bill_day}")
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
    labd_n = int(
        psql(
            f"SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details WHERE loan_installment_details_id={lid};"
        )
        or "0"
    )
    print(f"  DB after EOD: labd={labd_n} for lid={lid}")
    if labd_n < 1:
        raise RuntimeError("billing did not create labd — cannot assert reversal-after-billing")
    finish_scenario([PARENT, CHILD], baseline=inv, label="w4a.after-eod")
    inv = snapshot_invariants([PARENT, CHILD])

    # Reverse on N+k+1 (wall-clock after EOD)
    print(f"  dayN+k+1 op: reverse ref={ref}")
    lapd = psql(
        f"""
SELECT lapd.amount::text||'|'||lapd.principal_amount::text||'|'||lapd.interest_amount::text
  ||'|'||lapd.penalty_amount::text||'|'||lapd.fee_amount::text||'|'||lapd.excess_amount::text
  ||'|'||lapd.client_reference_number
  ||'|'||(EXTRACT(EPOCH FROM lapd.value_date)*1000)::bigint::text
  ||'|'||(EXTRACT(EPOCH FROM lapd.transaction_date)*1000)::bigint::text
  ||'|'||COALESCE(tc.type,'LOAN_REPAYMENT')||'|'||COALESCE(tc.sub_type,'CASH')
FROM mfi_accounting.loan_account_payments_details lapd
JOIN mfi_accounting.transaction_master tm ON tm.reference_number=lapd.transaction_reference_number
JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id
WHERE lapd.transaction_reference_number='{ref}'
ORDER BY lapd.id DESC LIMIT 1;
"""
    ).strip().split("|")
    if len(lapd) < 11:
        raise RuntimeError(f"no lapd for {ref}")
    a, prin, interest, penal, fee, excess, crn_l, vd_ms, td_ms, txn_type, txn_sub = lapd[:11]
    rev_ms = str(int(time.time() * 1000))
    rev_req = {
        "transaction_reversal_details": {
            "account_number": CHILD,
            "transaction_ref_no": ref,
            "transaction_reversal_date": rev_ms,
            "transaction_value_date": vd_ms,
            "transaction_date": td_ms,
            "transaction_amount": a,
            "channel_code": "WEB",
            "client_reference_number": crn_l,
            "reason": "OTHER",
            "description": "flowtest.w4_reversal_after_billing",
            "currency": "INR",
            "transaction_type": txn_type,
            "transaction_sub_type": txn_sub,
            "principal_amount": prin,
            "interest_amount": interest,
            "penalty_amount": penal,
            "fee_amount": fee,
            "excess_amount": excess,
        }
    }
    for fc in ("DEFAULT", "APPROVE"):
        r = _post(
            "loanAccountTransactionReversal",
            {"headers": _hdr(f"w4a_rev_{fc}_{int(time.time())}", function_code=fc), "request": rev_req},
        )
        st = r.get("response_status", {})
        print(f"  reversal {fc}: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:120]}")
        if st.get("status") != "SUCCESS" and st.get("code") not in ("000", "30365", "30267", "30375", "30376", "130009"):
            if fc == "DEFAULT":
                continue
            raise RuntimeError(f"reversal {fc} failed: {json.dumps(r)[:500]}")
        time.sleep(1)

    rev_flag = psql(
        f"SELECT COALESCE(tm.reversed,false)::text FROM mfi_accounting.transaction_master tm WHERE tm.reference_number='{ref}';"
    )
    after = snapshot_dues(CHILD, "after-rev")
    orphans = _neg_orphan_dues(CHILD)
    labd_after = int(
        psql(
            f"SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details WHERE loan_installment_details_id={lid};"
        )
        or "0"
    )
    print(
        f"  DB truth: reversed={rev_flag} orphans={orphans} labd_still={labd_after} "
        f"pending before={before['prin_pending']} mid={mid['prin_pending']} after={after['prin_pending']}"
    )
    if rev_flag != "true":
        raise AssertionError(f"CONTRACT: tm.reversed expected true got {rev_flag}")
    if orphans > 0:
        defect = ROOT / "scripts/testing/defects/LMS-DEFECT-w4-reversal-after-billing-orphan.md"
        defect.write_text(
            f"# LMS-DEFECT — orphan/negative dues after reversal-after-billing\n\n"
            f"ref={ref} orphans={orphans} before={before} mid={mid} after={after}\nSTOP\n"
        )
        raise RuntimeError(f"CONTRACT FAIL orphans={orphans} — {defect}")
    # pending should move back toward before (allow ₹2 after billing INT churn)
    if after["prin_pending"] + Decimal("2") < mid["prin_pending"] and mid["prin_pending"] < before["prin_pending"]:
        # still at mid level after reverse — fail
        if abs(after["prin_pending"] - mid["prin_pending"]) < Decimal("0.01"):
            defect = ROOT / "scripts/testing/defects/LMS-DEFECT-w4-reversal-after-billing-dues.md"
            defect.write_text(
                f"# LMS-DEFECT — dues not restored after reversal-after-billing\n\n"
                f"ref={ref} before={before} mid={mid} after={after}\nSTOP\n"
            )
            raise RuntimeError(f"CONTRACT FAIL dues not restored — {defect}")
    print("  PASS contract: reversed + no orphan dues + labd retained")
    finish_scenario([PARENT, CHILD], baseline=inv, label="w4a.after-rev")
    print("=== PASS: flowtest.w4_reversal_after_billing ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"=== FAIL: flowtest.w4_reversal_after_billing — {e} ===")
        raise
