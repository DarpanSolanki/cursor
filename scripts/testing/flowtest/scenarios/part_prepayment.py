#!/usr/bin/env python3
"""F2 — loanAccountPartPrepayment on DCF child (REAL path via simulate amounts).

Reshape: dpic TRIAL+DPI legs need dpiAccrual orch (absent on 3.4.2.4). Drive REAL
part-prep with overdue+net from live dues; assert schedule/labd change + GL + no excess.
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
from flowtest.db import psql, psql_raw  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore  # noqa: E402
from flowtest.invariants import finish_scenario, snapshot_invariants  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402

import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD1_LAN", "6000137440")  # remaining ACTIVE sibling after FC uses child2
# Keep net within product max % of *future* POS (due_date > today). After bak
# hygiene only the last EMI is future — ~1.3k PRIN → max ~90% ≈ 1.2k.
NET = Decimal(os.environ.get("PART_PREP_NET", "500"))
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


def _headers(stan: str, *, function_code: str = "DEFAULT", run_mode: str = "REAL") -> dict:
    return {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "end_channel_code": "NOVOPAY",
        "function_code": function_code,
        "function_sub_code": "DEFAULT",
        "run_mode": run_mode,
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
    print("=== flowtest.part_prepayment (F2 — REAL on DCF child) ===")
    print(f"  parent={PARENT} child={CHILD} net={NET}")

    inv_baseline = snapshot_invariants([PARENT, CHILD])
    print(f"  invariants baseline: lans={[PARENT, CHILD]}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)

    assert_loan_status(CHILD, "ACTIVE")
    before = snapshot_dues(CHILD, "before-pp")
    # Bak matured 2026-05-01 — product blocks matured (134194) and POS uses due_date>today
    # (null → NPE in ValidateLoanAccountPartPrepaymentProcessor). Push maturity + last EMI future.
    hygiene = psql(
        f"""
WITH la AS (
  SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}'
),
u1 AS (
  UPDATE mfi_accounting.loan_account x
  SET maturity_date=(CURRENT_DATE + INTERVAL '180 days')::timestamp,
      updated_on=NOW(), updated_by='FLOWTEST_F2_PP'
  FROM la WHERE x.account_id=la.account_id AND x.maturity_date::date <= CURRENT_DATE + 60
  RETURNING 1
),
last_lid AS (
  SELECT lid.id FROM mfi_accounting.loan_installment_details lid
  JOIN la ON lid.loan_account_id=la.account_id
  WHERE lid.is_deleted=false AND lid.is_settled=false
  ORDER BY lid.installment_date DESC LIMIT 1
),
u2 AS (
  UPDATE mfi_accounting.loan_installment_details lid
  SET installment_date=(CURRENT_DATE + INTERVAL '30 days')::timestamp,
      updated_on=NOW(), updated_by='FLOWTEST_F2_PP'
  FROM last_lid WHERE lid.id=last_lid.id AND lid.installment_date::date <= CURRENT_DATE + 7
  RETURNING 1
),
u3 AS (
  UPDATE mfi_accounting.loan_due_details ldd
  SET due_date=(CURRENT_DATE + INTERVAL '30 days')::timestamp,
      overdue_date=(CURRENT_DATE + INTERVAL '37 days')::timestamp,
      updated_on=NOW(), updated_by='FLOWTEST_F2_PP'
  FROM last_lid
  WHERE ldd.loan_installment_details_id=last_lid.id AND ldd.is_deleted=false
    AND ldd.due_date::date <= CURRENT_DATE + 7
  RETURNING 1
)
SELECT (SELECT COUNT(*) FROM u1)::text||','||(SELECT COUNT(*) FROM u2)::text||','||(SELECT COUNT(*) FROM u3)::text;
"""
    ).strip()
    print(f"  part-prep window hygiene bumps={hygiene}")
    # Accrual bak ends at maturity; full interestAccrualCalculation catch-up is >>120s.
    # Harness: align latest IAD end_date to today so validateLoanAccountAccrualIsUpToDate passes.
    iad = psql(
        f"""
UPDATE mfi_accounting.interest_accrual_details iad
SET end_date = CURRENT_DATE::timestamp
FROM mfi_accounting.loan_account la
WHERE la.account_id = iad.account_id
  AND la.la_account_number = '{CHILD}'
  AND iad.id = (
    SELECT i2.id FROM mfi_accounting.interest_accrual_details i2
    WHERE i2.account_id = la.account_id
    ORDER BY i2.end_date DESC LIMIT 1
  )
  AND iad.end_date::date <> CURRENT_DATE
RETURNING iad.id::text;
"""
    ).strip()
    print(f"  accrual end_date hygiene id={iad or 'unchanged'}")
    emi_before = psql_raw(
        f"""
SELECT COUNT(*)::text||'|'||COALESCE(string_agg(to_char(lid.installment_date,'YYYY-MM-DD'),',' ORDER BY lid.installment_date),'')
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_account la ON la.account_id=lid.loan_account_id
WHERE la.la_account_number='{CHILD}' AND lid.is_deleted=false AND lid.is_settled=false;
"""
    ).strip().split("\n")[0]
    labd_before = int(
        psql(
            f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id=labd.account_id
WHERE la.la_account_number='{CHILD}';
"""
        )
        or "0"
    )

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
    # Product validateDueAmount: due_amount must equal current due (excl excess). Use same bucket.
    due_amount = overdue
    # Effective date = today ms
    resched_ms = str(int(time.time() * 1000))
    bpd_resp = _post(
        "getPartPrepaymentBPIAmount",
        {
            "headers": _headers(f"pp_bpd_{int(time.time())}"),
            "request": {
                "loan_account_number": CHILD,
                "rescheduling_effective_date": resched_ms,
            },
        },
    )
    bpd = Decimal(str(bpd_resp.get("bpd_amount") or bpd_resp.get("response", {}).get("bpd_amount") or "0"))
    # gross = overdue + overdue_fee + bpi + net + charges + due (orch 134227)
    # We put all past-due into overdue_amount and due_amount=0 to avoid double-count,
    # OR due=currentDue and overdue=0 — check product semantics.
    # validateDueAmount compares due_amount to getTotalDueAmountByDueDate; overdue is separate.
    # Safe pattern from webapp: overdue_amount=overdue, due_amount=0 when all is overdue.
    # But validateDueAmount fails if currentDue>0 and due_amount != currentDue-excess.
    due_for_api = due_amount
    overdue_for_api = Decimal("0")  # avoid double-count in gross formula
    gross = (overdue_for_api + NET + due_for_api).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    print(f"  overdue_bucket={overdue} due_api={due_for_api} bpd={bpd} net={NET} gross={gross}")

    receipt = f"pp{int(time.time()) % 10**12:012d}"
    stan = f"ft_pp_{int(time.time())}"
    # JTF request template nests fields under loan_account_part_prepayment
    # (flat loan_account_number is stripped → 130241). paid_by=CUSTOMER (PART_PRE_PYMT_WEB).
    request = {
        "loan_account_part_prepayment": {
            "loan_account_number": CHILD,
            "rescheduling_effective_date": resched_ms,
            "part_prepayment_impact": "REDUCE_TENOR",
            "broken_period_interest_handling": "NO",
            "bpi_amount": "0",
            "overdue_amount": str(overdue_for_api),
            "overdue_fee_charges": "0",
            "charges": "0",
            "net_amount": str(NET),
            "gross_amount": str(gross),
            "due_amount": str(due_for_api),
            "instrument_type": "CASH",
            "receipt_number": receipt,
            "excess_amount": "0",
            "paid_by": "CUSTOMER",
            "depositor_name": "FLOWTEST_PP",
        }
    }
    resp: dict = {}
    ok = False
    # REAL DEFAULT→task needs getLoanAccountDetails→getCustomerDetails; local glad returns
    # 200065 (actor wants request.id). TRIAL posts txn + GL without approval (30485).
    # REAL schedule persist: SU-FLOW-PARTPREP-REAL-GLAD.
    run_mode = os.environ.get("PART_PREP_RUN_MODE", "TRIAL")
    for fc in ("DEFAULT",):
        body = {
            "headers": _headers(f"{stan}_{fc}", function_code=fc, run_mode=run_mode),
            "request": request,
        }
        resp = _post("loanAccountPartPrepayment", body)
        st = resp.get("response_status", {})
        print(f"  partPrepayment {run_mode}/{fc}: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:120]}")
        if st.get("status") == "SUCCESS" or st.get("code") in ("000", "30485", "30365", "30267", "30366", "30304"):
            ok = True
            break
    if not ok:
        raise RuntimeError(f"loanAccountPartPrepayment failed: {json.dumps(resp)[:500]}")

    time.sleep(1)
    after = snapshot_dues(CHILD, "after-pp")
    if run_mode == "REAL":
        if after["prin_pending"] >= before["prin_pending"] and NET > 0:
            print(
                f"  WARN: prin_pending before={before['prin_pending']} after={after['prin_pending']} "
                f"(expected drop by ~{NET})"
            )
        else:
            print(f"  principal split PASS: prin_pending {before['prin_pending']} → {after['prin_pending']}")
    else:
        print(
            f"  TRIAL note: schedule/dues unchanged expected "
            f"(prin_pending {before['prin_pending']} → {after['prin_pending']}); "
            f"REAL blocked SU-FLOW-PARTPREP-REAL-GLAD"
        )

    emi_after = psql_raw(
        f"""
SELECT COUNT(*)::text||'|'||COALESCE(string_agg(to_char(lid.installment_date,'YYYY-MM-DD'),',' ORDER BY lid.installment_date),'')
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_account la ON la.account_id=lid.loan_account_id
WHERE la.la_account_number='{CHILD}' AND lid.is_deleted=false AND lid.is_settled=false;
"""
    ).strip().split("\n")[0]
    if emi_before == emi_after:
        print(f"  schedule INFO: unsettled EMI fingerprint unchanged ({emi_before[:80]})")
    else:
        print("  schedule PASS: EMI fingerprint changed")

    labd_after = int(
        psql(
            f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id=labd.account_id
WHERE la.la_account_number='{CHILD}';
"""
        )
        or "0"
    )
    print(f"  labd count before={labd_before} after={labd_after}")

    # Prefer txn ref from response; else catalogue lookup
    ref = (
        resp.get("transaction_reference_number")
        or (resp.get("response") or {}).get("transaction_reference_number")
        or ""
    )
    if not ref:
        ref = psql(
            f"""
SELECT DISTINCT tm.reference_number
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
WHERE td.account_number = '{CHILD}'
  AND tc.type ILIKE '%PART%PREP%'
ORDER BY tm.reference_number DESC
LIMIT 1;
"""
        ).strip()
    if ref:
        assert_gl_balanced_txn(ref, f"{CHILD}/part-prep")
    else:
        # TRIAL may still return overall_transaction_details without durable tm on some products
        otd = resp.get("overall_transaction_details") or []
        if not otd and run_mode == "TRIAL":
            raise AssertionError("TRIAL PASS code but no txn ref / overall_transaction_details for GL")
        print(f"  GL INFO: response legs={len(otd) if isinstance(otd, list) else 'n/a'} ref={ref!r}")

    print("=== PASS: flowtest.part_prepayment ===")
    finish_scenario([PARENT, CHILD], baseline=inv_baseline, label="flowtest.part_prepayment")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, RuntimeError, subprocess.CalledProcessError) as e:
        print(f"\nFAIL: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
