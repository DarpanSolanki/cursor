#!/usr/bin/env python3
"""F5 FLOW A — ICF close → loanAccountReopening with document_details stub."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
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
from flowtest.doc_stub import document_details  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402

import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD2_LAN", "6000137441")
DEATH_DATE = os.environ.get("DEATH_DATE", "2025-08-02")
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


def _hdr(stan: str, *, function_code: str = "DEFAULT") -> dict:
    return {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "end_channel_code": "NOVOPAY",
        "function_code": function_code,
        "function_sub_code": "DEFAULT",
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


def _icf_close() -> None:
    fc_date = dcf._vikram_fc_date(DEATH_DATE)
    psql(
        f"""
WITH la AS (
  SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number = '{CHILD}'
),
last_lid AS (
  SELECT lid.id FROM mfi_accounting.loan_installment_details lid
  JOIN la ON lid.loan_account_id = la.account_id
  WHERE lid.is_deleted = false ORDER BY lid.installment_date DESC LIMIT 1
),
u1 AS (
  UPDATE mfi_accounting.loan_account x
  SET maturity_date = (CURRENT_DATE + INTERVAL '180 days')::timestamp,
      updated_on = NOW(), updated_by = 'FLOWTEST_F5_REOPEN'
  FROM la WHERE x.account_id = la.account_id
    AND x.maturity_date::date <= CURRENT_DATE + INTERVAL '60 days'
  RETURNING 1
),
u2 AS (
  UPDATE mfi_accounting.loan_installment_details lid
  SET installment_date = (CURRENT_DATE + INTERVAL '30 days')::timestamp,
      updated_on = NOW(), updated_by = 'FLOWTEST_F5_REOPEN'
  FROM last_lid WHERE lid.id = last_lid.id RETURNING 1
),
u3 AS (
  UPDATE mfi_accounting.loan_due_details d
  SET due_date = (CURRENT_DATE + INTERVAL '30 days')::timestamp,
      updated_on = NOW(), updated_by = 'FLOWTEST_F5_REOPEN'
  FROM last_lid WHERE d.loan_installment_details_id = last_lid.id
    AND COALESCE(d.is_deleted,false)=false RETURNING 1
)
SELECT 1;
"""
    )
    os.environ["ICF_USE_LOAN_PREPAYMENT"] = "0"
    dcf.VIKRAM_USE_LOAN_PREPAYMENT = False
    dcf._run_child_fc_via_individual_child(CHILD, DEATH_DATE)
    assert_loan_status(CHILD, "CLOSED", label="compose-ICF")
    print(f"  compose: ICF CLOSED {CHILD} (seed for reopen)")


def _ok(st: dict) -> bool:
    return st.get("status") == "SUCCESS" or st.get("code") in (
        "000", "30267", "30375", "30376", "130009", "MOSL-000", "30276", "30281", "30279"
    )


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    os.environ["FLOWTEST_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.loan_reopening (F5 — ICF→reopen + doc stub) ===")
    print(f"  parent={PARENT} child={CHILD}")
    print("  DOC_STUB: request payload (ValidateDocument + CreateDocument local DB) — no HTTP DMS")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    subprocess.check_call(["bash", str(ROOT / "scripts/bin/foreclosure-local-setup.sh")])
    subprocess.check_call(["bash", str(ROOT / "scripts/bin/novopay-service.sh"), "ensure", "task"])
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.prepare_fixture_pint_free(PARENT)
    dcf.ensure_fixture_accounts_active(PARENT)

    _icf_close()
    closed = snapshot_dues(CHILD, "before-reopen")
    print("  LAYERS: ICF=REAL reopen=REAL docs=STUB_PAYLOAD fixture=dcf_bak compose=chain")

    req = {
        "account_number": CHILD,
        "reason": "OTHER",  # LOAN_REOPEN_REASON / LOAN_REOPEN
        "notes": "flowtest.loan_reopening F5",
        "document_details": document_details(document_code="OTHER"),
    }
    last = {}
    for fc in ("DEFAULT", "APPROVE"):
        body = {"headers": _hdr(f"ft_reopen_{fc}_{int(time.time())}", function_code=fc), "request": req}
        last = _post("loanAccountReopening", body)
        st = last.get("response_status", {})
        print(f"  loanAccountReopening {fc}: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:160]}")
        if not _ok(st):
            print(f"  BLOCKER: reopen {fc} — {json.dumps(last)[:500]}")
            print("=== BLOCKED: flowtest.loan_reopening ===")
            return 2
        time.sleep(2)

    assert_loan_status(CHILD, "ACTIVE", label="after-reopen")
    after = snapshot_dues(CHILD, "after-reopen")
    print(f"  dues INFO: prin_pending {closed['prin_pending']}→{after['prin_pending']}")

    ref = psql(
        f"""
SELECT lacd.transaction_reference_number
FROM mfi_accounting.loan_account_closure_details lacd
JOIN mfi_accounting.loan_account la ON la.account_id=lacd.loan_account_id
WHERE la.la_account_number='{CHILD}'
ORDER BY lacd.id DESC LIMIT 1
"""
    ).strip()
    if ref:
        assert_gl_balanced_txn(ref, f"{CHILD}/closure-ref-after-reopen", allow_empty=True)
    assert_webapp_summary_accrued_le_original(CHILD, role="reopened-child")
    print("  LAYERS_DECLARE: ICF=REAL reopen=REAL docs=STUB_PAYLOAD")
    print("=== PASS: flowtest.loan_reopening ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"=== FAIL: flowtest.loan_reopening: {exc} ===")
        raise
