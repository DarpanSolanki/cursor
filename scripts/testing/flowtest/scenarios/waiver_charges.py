#!/usr/bin/env python3
"""F5 FLOW C — age dues → waiveLoanAccountCharges with document_details stub."""
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

from flowtest.asserts import assert_loan_status, snapshot_dues  # noqa: E402
from flowtest.db import psql  # noqa: E402
from flowtest.doc_stub import document_details  # noqa: E402
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


def _ok(st: dict) -> bool:
    return st.get("status") == "SUCCESS" or st.get("code") in (
        "000", "30267", "30375", "30376", "MOSL-000", "30276", "30281", "30279"
    )


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.waiver_charges (F5 — age→waive + doc stub) ===")
    print(f"  parent={PARENT} child={CHILD}")
    print("  DOC_STUB: request payload (ValidateDocument + CreateDocument local DB) — no HTTP DMS")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    subprocess.check_call(["bash", str(ROOT / "scripts/bin/novopay-service.sh"), "ensure", "task"])
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    assert_loan_status(CHILD, "ACTIVE")
    inv_baseline = snapshot_invariants([PARENT, CHILD])

    child_id = int(
        psql(
            f"SELECT account_id FROM mfi_accounting.loan_account "
            f"WHERE la_account_number='{CHILD}' AND is_deleted=false"
        )
    )
    force_regular_asset_slab([child_id])
    age_dues_for_dpd(child_id, as_of=__import__("datetime").date.today().isoformat(), min_dpd_days=35)
    before = snapshot_dues(CHILD, "before-waiver")

    due_row = psql(
        f"""
SELECT ldd.id::text || '|' ||
  (ldd.due_amount - COALESCE(ldd.paid_amount,0) - COALESCE(ldd.waived_amount,0))::text
FROM mfi_accounting.loan_due_details ldd
WHERE ldd.loan_account_id = {child_id} AND ldd.is_deleted = false
  AND ldd.component_type = 'INT'
  AND (ldd.due_amount - COALESCE(ldd.paid_amount,0) - COALESCE(ldd.waived_amount,0)) > 0
ORDER BY ldd.due_date ASC
LIMIT 1
"""
    )
    if not due_row or "|" not in due_row:
        print("  BLOCKER: no open INT due for waiver — SU-FLOW-WAIVER-NODUE")
        print("=== BLOCKED: flowtest.waiver_charges ===")
        return 2
    due_id, pending_s = due_row.split("|", 1)
    pending = Decimal(pending_s)
    print(f"  compose: waive INT due_id={due_id} pending={pending} (SEEDED age)")
    print("  LAYERS: aging=SEEDED waive=REAL docs=STUB_PAYLOAD")

    req = {
        "notes": "flowtest waiver charges F5",
        "document_details": document_details(document_code="OTHER"),
        "waiver_details_list": [
            {
                "loan_account_number": CHILD,
                "loan_due_details_id": due_id,
                "is_fully_waived": "1",
                "waived_amount": format(pending, "f"),
                "amount_to_be_paid": "0",
                "waiver_percentage": "100",
            }
        ],
    }
    last = {}
    for fc in ("DEFAULT", "APPROVE"):
        body = {"headers": _hdr(f"ft_waive_{fc}_{int(time.time())}", function_code=fc), "request": req}
        last = _post("waiveLoanAccountCharges", body)
        st = last.get("response_status", {})
        print(f"  waiveLoanAccountCharges {fc}: {st.get('code')}/{st.get('status')} — {str(st.get('message',''))[:180]}")
        if not _ok(st):
            print(f"  BLOCKER: waive {fc} — {json.dumps(last)[:500]}")
            print("=== BLOCKED: flowtest.waiver_charges ===")
            return 2
        time.sleep(1)

    after = snapshot_dues(CHILD, "after-waiver")
    if after["int_waived"] <= before["int_waived"]:
        # soft: check due row waived
        left = Decimal(
            psql(
                f"""
SELECT (due_amount - COALESCE(paid_amount,0) - COALESCE(waived_amount,0))::text
FROM mfi_accounting.loan_due_details WHERE id = {due_id}
"""
            )
            or "0"
        )
        if left > 0:
            raise AssertionError(f"due {due_id} still pending={left} after waive")
    print(f"  waived PASS: int_waived {before['int_waived']}→{after['int_waived']}")
    print("  LAYERS_DECLARE: aging=SEEDED waive=REAL docs=STUB_PAYLOAD")
    finish_scenario([PARENT, CHILD], baseline=inv_baseline, label="flowtest.waiver_charges")
    print("=== PASS: flowtest.waiver_charges ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"=== FAIL: flowtest.waiver_charges: {exc} ===")
        raise
