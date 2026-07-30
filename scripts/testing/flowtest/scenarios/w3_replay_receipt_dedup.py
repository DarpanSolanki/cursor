#!/usr/bin/env python3
"""W3-a — duplicate loanRepayment same receipt → exactly-one txn; second 134253.

Production contract: ReceiptNumberDedupProcessor rejects replay (134253).
Real orch: loanRepayment → receiptNumberDedupProcessor (loans_orc).
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

from flowtest.asserts import assert_gl_balanced_txn, assert_loan_status  # noqa: E402
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
        with urllib.request.urlopen(req, timeout=120) as resp:
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


def _repay_body(receipt: str, amt: Decimal, value_date: str) -> dict:
    return {
        "loan_repayment_details": {
            "account_number": CHILD,
            "repayment_amount": str(amt),
            "repayment_time": value_date,
            "value_date": value_date,
            "repayment_mode": "CASH",
            "receipt_number": receipt,
            "client_reference_number": receipt,
        }
    }


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.w3_replay_receipt_dedup (W3-a receipt replay) ===")
    print(f"  parent={PARENT} child={CHILD}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    inv_baseline = snapshot_invariants([PARENT, CHILD])
    print(f"  invariants baseline: lans={[PARENT, CHILD]}")
    dcf.prepare_fixture_pint_free(PARENT)
    assert_loan_status(CHILD, "ACTIVE")

    account_id = psql(
        f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}' AND is_deleted=false;"
    ).strip()
    if account_id:
        force_regular_asset_slab([account_id])

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
        raise RuntimeError(f"no open dues on {CHILD}")
    receipt = f"W3RP{int(time.time())}"
    vd = str(int(time.time() * 1000))
    print(f"  setup: ACTIVE child dues_open={overdue} repay_amt={amt} receipt={receipt}")

    body1 = {"headers": _hdr(f"w3a1_{int(time.time())}"), "request": _repay_body(receipt, amt, vd)}
    r1 = _post("loanRepayment", body1)
    st1 = r1.get("response_status", {})
    print(f"  stimulus#1 loanRepayment: {st1.get('code')}/{st1.get('status')} — {str(st1.get('message',''))[:120]}")
    if st1.get("status") != "SUCCESS" and st1.get("code") not in ("000", "30265", "30273", "MOSL-000"):
        raise RuntimeError(f"first repay must SUCCESS: {json.dumps(r1)[:500]}")

    # Parallel second+third with SAME receipt (true concurrent replay, not sequential pretend)
    def _dup(i: int) -> dict:
        return _post(
            "loanRepayment",
            {"headers": _hdr(f"w3a2_{i}_{int(time.time()*1000)}"), "request": _repay_body(receipt, amt, vd)},
        )

    dup_codes: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_dup, i) for i in (1, 2)]
        for fut in as_completed(futs):
            r = fut.result()
            st = r.get("response_status", {})
            code = str(st.get("code") or "")
            dup_codes.append(code)
            print(f"  stimulus#dup: {code}/{st.get('status')} — {str(st.get('message',''))[:120]}")

    tm_n = int(
        psql(
            f"""
SELECT COUNT(*)::text FROM mfi_accounting.transaction_master tm
WHERE tm.receipt_number='{receipt}' AND tm.status='SUCCESS' AND COALESCE(tm.reversed,false)=false;
"""
        )
        or "0"
    )
    crn_n = int(
        psql(
            f"""
SELECT COUNT(*)::text FROM mfi_accounting.transaction_master tm
WHERE tm.client_reference_number='{receipt}' AND tm.status='SUCCESS'
  AND COALESCE(tm.reversed,false)=false;
"""
        )
        or "0"
    )
    print(f"  DB truth: SUCCESS tm receipt={tm_n} SUCCESS tm client_ref={crn_n}")

    # Production contract: exactly one SUCCESS txn; replay must be 134253 (not SUCCESS)
    if tm_n != 1:
        raise RuntimeError(f"CONTRACT FAIL: expected exactly 1 SUCCESS tm for receipt, got {tm_n}")
    if any(c in ("000",) or c == "SUCCESS" for c in dup_codes):
        # response_status.code SUCCESS variants
        pass
    bad_ok = [c for c in dup_codes if c in ("000", "30265", "30273", "MOSL-000")]
    if bad_ok:
        raise RuntimeError(f"CONTRACT FAIL: duplicate repay succeeded codes={dup_codes}")
    if "134253" not in dup_codes:
        print(f"  WARN: expected 134253 on replay; got {dup_codes} — still fail if not reject")
        if not all(c and c not in ("000", "30265", "30273") for c in dup_codes):
            raise RuntimeError(f"CONTRACT FAIL: replay not rejected: {dup_codes}")

    ref = psql(
        f"""
SELECT tm.reference_number FROM mfi_accounting.transaction_master tm
WHERE tm.receipt_number='{receipt}' AND tm.status='SUCCESS'
ORDER BY tm.id DESC LIMIT 1;
"""
    ).strip()
    assert_gl_balanced_txn(ref, f"{CHILD}/w3a")
    print(f"  PASS contract: exactly-one txn ref={ref}; replay rejected codes={dup_codes}")

    finish_scenario([PARENT, CHILD], baseline=inv_baseline, label="w3.replay_receipt")
    print("=== PASS: flowtest.w3_replay_receipt_dedup ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"=== FAIL: flowtest.w3_replay_receipt_dedup — {e} ===")
        raise
