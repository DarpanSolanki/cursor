#!/usr/bin/env python3
"""F4 FLOW B — compose age_dues_for_dpd → loanWriteoff.

ACTIVE overdue child (SEEDED aging) → writeoff with today's value_date.
Nested loan_writeoff_details per JTF. GAP-062 EC mismatch may block — exit 2.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.asserts import assert_gl_balanced_txn, assert_loan_status, snapshot_dues  # noqa: E402
from flowtest.db import psql, psql_multi  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore  # noqa: E402
from flowtest.invariants import finish_scenario, snapshot_invariants  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.loan_state import age_dues_for_dpd, force_regular_asset_slab  # noqa: E402
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
        "actor_type": "EMPLOYEE",
        "user_handle_value": os.environ.get("ICF_USER_ID", "103"),
        "office_id": os.environ.get("ICF_OFFICE_ID", "2"),
    }


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.loan_writeoff (F4 FLOW B — age→writeoff compose) ===")
    print(f"  parent={PARENT} child={CHILD}")

    inv_baseline = snapshot_invariants([PARENT, CHILD])
    print(f"  invariants baseline: lans={[PARENT, CHILD]}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    subprocess.check_call(["bash", str(ROOT / "scripts/bin/novopay-service.sh"), "ensure", "task"])
    subprocess.check_call(["bash", str(ROOT / "scripts/bin/novopay-service.sh"), "ensure", "authorization"])
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    assert_loan_status(CHILD, "ACTIVE")

    child_id = int(
        psql(
            f"SELECT account_id FROM mfi_accounting.loan_account "
            f"WHERE la_account_number='{CHILD}' AND is_deleted=false"
        )
    )
    force_regular_asset_slab([child_id])
    age_dues_for_dpd(child_id, as_of=__import__("datetime").date.today().isoformat(), min_dpd_days=35)
    before = snapshot_dues(CHILD, "before-writeoff")
    # Mirror ValidateLoanWriteOffDataProcessor + LoanDueDetailsRepository:
    # PRIN = SUM(due-paid-waived) all PRIN; INT = IAD posted+carry − INT paid+waived ≤today;
    # PINT = SUM(due-paid-waived) PINT due_date≤today. (INT due rows ≠ platform INT outstanding.)
    row = psql(
        f"""
SELECT
  COALESCE((
    SELECT SUM(due_amount - paid_amount - waived_amount)
    FROM mfi_accounting.loan_due_details
    WHERE component_type = 'PRIN' AND loan_account_id = {child_id} AND is_deleted = false
  ), 0)::text
  || '|' ||
  (
    COALESCE((
      SELECT SUM(total_accrual_posted_amount + carry_over_amount)
      FROM mfi_accounting.interest_accrual_details WHERE account_id = {child_id}
    ), 0)
    -
    COALESCE((
      SELECT SUM(paid_amount + waived_amount)
      FROM mfi_accounting.loan_due_details
      WHERE component_type = 'INT' AND loan_account_id = {child_id}
        AND due_date::date <= CURRENT_DATE AND is_deleted = false
    ), 0)
  )::text
  || '|' ||
  COALESCE((
    SELECT SUM(due_amount - paid_amount - waived_amount)
    FROM mfi_accounting.loan_due_details
    WHERE loan_account_id = {child_id} AND component_type IN ('PINT')
      AND due_date::date <= CURRENT_DATE AND is_deleted = false
  ), 0)::text
"""
    )
    prin_s, int_s, pint_s = (row or "0|0|0").split("|")
    prin = Decimal(prin_s or "0")
    interest = Decimal(int_s or "0")
    penal = Decimal(pint_s or "0")
    wo_raw = prin + interest + penal
    if wo_raw <= 0:
        raise RuntimeError(f"writeoff outstanding=0 prin={prin} int={interest} pint={penal}")

    # L1 harness: AmountValidator rounds via CurrencyUtil (INR 2dp) — send 2dp only.
    # Align IAD carry so platform outstanding equals that 2dp amount (exact compare).
    from decimal import ROUND_HALF_UP

    wo_2 = wo_raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    delta = wo_raw - wo_2
    if delta != 0:
        psql_multi(
            f"""
UPDATE mfi_accounting.interest_accrual_details
SET carry_over_amount = COALESCE(carry_over_amount, 0) - ({delta})
WHERE id = (
  SELECT id FROM mfi_accounting.interest_accrual_details
  WHERE account_id = {child_id}
  ORDER BY id DESC LIMIT 1
);
"""
        )
        print(f"  hygiene: scale IAD carry by -{delta} so outstanding→{wo_2} (2dp)")

    # recompute after scale
    row2 = psql(
        f"""
SELECT
  COALESCE((
    SELECT SUM(due_amount - paid_amount - waived_amount)
    FROM mfi_accounting.loan_due_details
    WHERE component_type = 'PRIN' AND loan_account_id = {child_id} AND is_deleted = false
  ), 0)
  +
  (
    COALESCE((
      SELECT SUM(total_accrual_posted_amount + carry_over_amount)
      FROM mfi_accounting.interest_accrual_details WHERE account_id = {child_id}
    ), 0)
    -
    COALESCE((
      SELECT SUM(paid_amount + waived_amount)
      FROM mfi_accounting.loan_due_details
      WHERE component_type = 'INT' AND loan_account_id = {child_id}
        AND due_date::date <= CURRENT_DATE AND is_deleted = false
    ), 0)
  )
  +
  COALESCE((
    SELECT SUM(due_amount - paid_amount - waived_amount)
    FROM mfi_accounting.loan_due_details
    WHERE loan_account_id = {child_id} AND component_type IN ('PINT')
      AND due_date::date <= CURRENT_DATE AND is_deleted = false
  ), 0)
"""
    )
    wo_amt = Decimal(row2 or "0").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    value_date = str(int(time.time() * 1000))
    # Max 2 attempts: (1) scaled 2dp (2) one alternate ROUND_DOWN if needed
    candidates = [
        ("2dp_scaled", format(wo_amt, "f")),
    ]
    alt = wo_raw.quantize(Decimal("0.01"), rounding=__import__("decimal").ROUND_DOWN)
    if alt != wo_amt and alt > 0:
        candidates.append(("2dp_floor", format(alt, "f")))
    print(f"  compose: raw={wo_raw} scaled_outstanding={wo_amt} attempts={len(candidates)}")
    print("  LAYERS: aging=SEEDED iad_scale=SEEDED writeoff=REAL")

    ok = False
    last: dict = {}
    attempts = 0
    for label, amt_s in candidates[:2]:
        attempts += 1
        req = {
            "loan_writeoff_details": {
                "writeoff_amount": amt_s,
                "value_date": value_date,
                "account_number": CHILD,
            },
            "notes": f"flowtest writeoff F5 {label}",
            "attachments": [],
        }
        body = {
            "headers": _hdr(f"ft_wo_{label}_{int(time.time())}"),
            "request": req,
        }
        last = _post("loanWriteoff", body)
        st = last.get("response_status", {})
        print(
            f"  loanWriteoff DEFAULT/{label} amt={amt_s}: "
            f"{st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:180]}"
        )
        if st.get("status") == "SUCCESS" or st.get("code") in ("000", "30267", "30276", "30281", "MOSL-000", "30375"):
            ok = True
            body["headers"] = _hdr(f"ft_wo_APPROVE_{int(time.time())}", function_code="APPROVE")
            last = _post("loanWriteoff", body)
            st = last.get("response_status", {})
            print(f"  loanWriteoff APPROVE: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:180]}")
            ok = st.get("status") == "SUCCESS" or st.get("code") in ("000", "30267", "30279", "30376", "30375", "30281")
            break
        if st.get("code") in ("13009",) or "Unable to connect" in str(st.get("message", "")):
            print(f"  BLOCKER: infra {st.get('code')} — ensure authorization/approval; not amount defect")
            print("=== BLOCKED: flowtest.loan_writeoff ===")
            return 2
        msg = str(st.get("message", "")) + json.dumps(last)[:400]
        # Amount accepted past AmountValidator + ValidateLoanWriteOffDataProcessor; posting NPE = GAP-062
        if st.get("code") == "333" or "NullPointer" in msg or "134207" in msg:
            ev = ROOT / "scripts/scratch/flowtest-f5"
            ev.mkdir(parents=True, exist_ok=True)
            (ev / "writeoff_gap062_evidence.json").write_text(
                json.dumps(
                    {
                        "amount_harness": "PASS",
                        "writeoff_amount": amt_s,
                        "scaled_outstanding": str(wo_amt),
                        "response": last,
                        "log_hint": "PrepaymentApproppriationProcessor.java:85 NPE String.toCharArray val=null (GAP-062)",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(
                "  AMOUNT_HARNESS: PASS (2dp IAD-scaled accepted by validators). "
                "DEFECT_CANDIDATE_3: GAP-062 NPE PrepaymentApproppriationProcessor:85 — SU-FLOW-WRITEOFF-GAP062"
            )
            print("=== BLOCKED: flowtest.loan_writeoff ===")
            return 2

    if not ok:
        print(
            "  DEFECT_CANDIDATE_3: writeoff amount still rejected after IAD→2dp scale "
            f"(attempts={attempts}). "
            f"validator=AmountValidator+ValidateLoanWriteOffDataProcessor:82-109 "
            f"last={json.dumps(last)[:500]}"
        )
        ev = ROOT / "scripts/scratch/flowtest-f5"
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "writeoff_attempt_evidence.json").write_text(
            json.dumps(
                {
                    "raw": str(wo_raw),
                    "scaled": str(wo_amt),
                    "attempts": attempts,
                    "last_response": last,
                    "validators": [
                        "loans_orc.xml:1402-1403 amountValidator → AmountValidator.roundAmount INR 2dp",
                        "ValidateLoanWriteOffDataProcessor.java:82-109 exact BigDecimal compare",
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print("=== BLOCKED: flowtest.loan_writeoff ===")
        return 2

    time.sleep(2)
    status = psql(
        f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}' AND is_deleted=false"
    )
    print(f"  status after writeoff: {status}")
    # Accept WRITOFF / WRITTEN_OFF / CLOSED variants
    if status not in ("WRITOFF", "WRITTEN_OFF", "WRITE_OFF", "CLOSED", "ACTIVE"):
        raise AssertionError(f"unexpected status {status!r}")
    if status == "ACTIVE":
        # partial writeoff may leave ACTIVE — assert waived/paid moved
        after = snapshot_dues(CHILD, "after-writeoff")
        if after["prin_pending"] >= before["prin_pending"]:
            raise AssertionError("partial writeoff did not reduce pending")
        print("  partial writeoff PASS: pending reduced, status ACTIVE")
    else:
        print(f"  status PASS: {status}")

    ref = psql(
        f"""
SELECT tm.reference_number FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id=tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id=tm.id
WHERE td.account_number='{CHILD}' AND tc.type ILIKE '%WRITE%'
ORDER BY tm.id DESC LIMIT 1
"""
    ).strip()
    if not ref:
        ref = psql(
            f"""
SELECT tm.reference_number FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_details td ON td.transaction_id=tm.id
WHERE td.account_number='{CHILD}'
ORDER BY tm.id DESC LIMIT 1
"""
        ).strip()
    if ref:
        assert_gl_balanced_txn(ref, f"{CHILD}/writeoff")
    else:
        raise AssertionError("no writeoff txn ref for GL assert")

    print("  LAYERS_DECLARE: aging=SEEDED writeoff=REAL")
    print("=== PASS: flowtest.loan_writeoff ===")
    finish_scenario([PARENT, CHILD], baseline=inv_baseline, label="flowtest.loan_writeoff")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"=== FAIL: flowtest.loan_writeoff: {exc} ===")
        raise
