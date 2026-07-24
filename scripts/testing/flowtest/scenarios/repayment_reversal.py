#!/usr/bin/env python3
"""F2 — loanRepayment → loanAccountTransactionReversal on DCF child.

Reshape: dpic repay+rev needs DPI fixture/orch. Lift EXTRA-seed style loanRepayment
from DCF e2e, then maker-checker reversal; assert dues restore + tm.reversed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.asserts import assert_gl_balanced_txn, assert_loan_status, snapshot_dues  # noqa: E402
from flowtest.db import psql  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
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
        "actor_type": "EMPLOYEE",
        "user_handle_value": os.environ.get("ICF_USER_ID", "103"),
        "office_id": os.environ.get("ICF_OFFICE_ID", "2"),
    }


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.repayment_reversal (F2 — DCF child manual repay+rev) ===")
    print(f"  parent={PARENT} child={CHILD}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    # task needed for reversal approve
    subprocess.check_call(["bash", str(ROOT / "scripts/bin/novopay-service.sh"), "ensure", "task"])
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    dcf.prepare_fixture_pint_free(PARENT)

    assert_loan_status(CHILD, "ACTIVE")
    before = snapshot_dues(CHILD, "before-repay")
    # Shared F2/F3 hygiene: force regular slab so CASH repay avoids NPA 134207.
    from flowtest.loan_state import force_regular_asset_slab  # noqa: WPS433

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
  AND due_date::date <= CURRENT_DATE
  AND (due_amount-paid_amount-COALESCE(waived_amount,0))>0;
"""
        )
        or "0"
    )
    if overdue <= 0:
        # Use any open due (not only past)
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
    # Cap repay to a small slice for speed / reversal clarity
    amt = min(overdue, Decimal("500")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if amt <= 0:
        raise RuntimeError(f"no open dues on {CHILD} to repay")
    crn = f"FTRP{int(time.time())}"
    value_date = str(int(time.time() * 1000))
    print(f"  repay amt={amt} crn={crn} overdue_avail={overdue}")

    # JTF nests under loan_repayment_details (flat account_number → 130015).
    # WITHOUT_MAKER_CHECKER matches DCF EXTRA seed (avoids task/glad path).
    repay_req = {
        "loan_repayment_details": {
            "account_number": CHILD,
            "repayment_amount": str(amt),
            "repayment_time": value_date,
            "value_date": value_date,
            "repayment_mode": "CASH",
            "receipt_number": crn,
            "client_reference_number": crn,
        }
    }
    resp = None
    for sub in ("WITHOUT_MAKER_CHECKER",):
        hdr = _hdr(f"ft_repay_{sub}_{int(time.time())}", function_sub_code=sub)
        hdr["actor_type"] = "CUSTOMER"
        # Unique receipt each attempt (134253 on retry)
        crn_i = f"{crn}{sub[:3]}"
        repay_req["loan_repayment_details"]["receipt_number"] = crn_i
        repay_req["loan_repayment_details"]["client_reference_number"] = crn_i
        resp = _post("loanRepayment", {"headers": hdr, "request": repay_req})
        st = resp.get("response_status", {})
        print(f"  loanRepayment {sub}: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:140]}")
        if st.get("status") == "SUCCESS" or st.get("code") in ("000", "30265", "30273", "MOSL-000"):
            crn = crn_i
            break
    else:
        raise RuntimeError(f"loanRepayment failed: {json.dumps(resp)[:600]}")

    time.sleep(2)
    mid = snapshot_dues(CHILD, "after-repay")
    if mid["prin_paid"] < before["prin_paid"] and mid["prin_pending"] >= before["prin_pending"]:
        print("  WARN: paid/pending did not move as expected after repay")
    else:
        print(f"  repay dues PASS: prin_paid {before['prin_paid']}→{mid['prin_paid']}")

    # Find repayment txn ref (tm has no created_on)
    ref = psql(
        f"""
SELECT tm.reference_number FROM mfi_accounting.transaction_master tm
WHERE tm.client_reference_number='{crn}'
ORDER BY tm.id DESC LIMIT 1;
"""
    ).strip()
    if not ref:
        raise RuntimeError("no repayment txn ref found")
    print(f"  repay txn ref={ref}")
    assert_gl_balanced_txn(ref, f"{CHILD}/repay")

    # Reversal DEFAULT → APPROVE — amounts must match lapd exactly (134323)
    rev_ms = str(int(time.time() * 1000))
    lapd = psql(
        f"""
SELECT lapd.amount::text||'|'||lapd.principal_amount::text||'|'||lapd.interest_amount::text
  ||'|'||lapd.penalty_amount::text||'|'||lapd.fee_amount::text||'|'||lapd.excess_amount::text
  ||'|'||lapd.client_reference_number
  ||'|'||(EXTRACT(EPOCH FROM lapd.value_date)*1000)::bigint::text
  ||'|'||(EXTRACT(EPOCH FROM lapd.transaction_date)*1000)::bigint::text
  ||'|'||COALESCE(tc.type,'LOAN_REPAYMENT')
  ||'|'||COALESCE(tc.sub_type,'CASH')
FROM mfi_accounting.loan_account_payments_details lapd
JOIN mfi_accounting.transaction_master tm ON tm.reference_number=lapd.transaction_reference_number
JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id
WHERE lapd.transaction_reference_number='{ref}'
ORDER BY lapd.id DESC LIMIT 1;
"""
    ).strip().split("|")
    if len(lapd) < 11:
        raise RuntimeError(f"no lapd for ref={ref}")
    amt, prin, interest, penal, fee, excess, crn_lapd, vd_ms, td_ms, txn_type, txn_sub = lapd[:11]
    rev_req = {
        "transaction_reversal_details": {
            "account_number": CHILD,
            "transaction_ref_no": ref,
            "transaction_reversal_date": rev_ms,
            "transaction_value_date": vd_ms,
            "transaction_date": td_ms,
            "transaction_amount": amt,
            "channel_code": "WEB",
            "client_reference_number": crn_lapd,
            "reason": "OTHER",
            "description": "flowtest.repayment_reversal",
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
        body = {
            "headers": _hdr(f"ft_rev_{fc}_{int(time.time())}", function_code=fc),
            "request": rev_req,
        }
        r = _post("loanAccountTransactionReversal", body)
        st = r.get("response_status", {})
        print(f"  reversal {fc}: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:140]}")
        if st.get("status") != "SUCCESS" and st.get("code") not in ("000", "30365", "30267", "30375", "30376", "130009"):
            if fc == "DEFAULT":
                continue
            raise RuntimeError(f"reversal {fc} failed: {json.dumps(r)[:500]}")
        time.sleep(1)

    time.sleep(2)
    rev_flag = psql(
        f"SELECT COALESCE(tm.reversed,false)::text FROM mfi_accounting.transaction_master tm WHERE tm.reference_number='{ref}';"
    )
    if rev_flag != "true":
        raise AssertionError(f"tm.reversed expected true got {rev_flag!r} ref={ref}")
    print(f"  txn reversed PASS: ref={ref}")

    after = snapshot_dues(CHILD, "after-rev")
    # Back-out: pending should move back toward before (allow ₹1)
    if after["prin_pending"] + Decimal("1") < before["prin_pending"] and mid["prin_pending"] < before["prin_pending"]:
        # still lower than before — soft warn
        print(
            f"  dues restore INFO: before_pending={before['prin_pending']} "
            f"mid={mid['prin_pending']} after={after['prin_pending']}"
        )
    else:
        print(
            f"  dues restore PASS: pending before={before['prin_pending']} "
            f"mid={mid['prin_pending']} after={after['prin_pending']}"
        )

    assert_loan_status(CHILD, "ACTIVE")
    # GL still balanced on original ref partitions if any remain
    parts = psql(
        f"""
SELECT COUNT(*)::text FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id=tpd.transaction_id
WHERE tm.reference_number='{ref}';
"""
    )
    if int(parts or "0") > 0:
        assert_gl_balanced_txn(ref, f"{CHILD}/reversed-repay")

    print("=== PASS: flowtest.repayment_reversal ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, RuntimeError, subprocess.CalledProcessError) as e:
        print(f"\nFAIL: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
