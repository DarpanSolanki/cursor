#!/usr/bin/env python3
"""Drive parent waiveLoanAccountCharges on a group parent, then the WAIVER queue fan-out
(childLoanEventProcessingBatchJob -> childWaiveLoanAccountCharges) and evaluate the
value-level assert SQL."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from clb_queue_harness import max_batch_execution_id, wait_batch_after  # noqa: E402
from flowtest.doc_stub import document_details  # noqa: E402

ACCT_URL = os.environ.get("ACCOUNTING_URL", "http://localhost:8002/accounting/api/v1")
PG_ENV = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
PG = ["psql", "-h", "localhost", "-p", "5433", "-U", "yugabyte", "-d", "yugabyte",
      "-v", "ON_ERROR_STOP=1", "-t", "-A"]
SQL_FILE = ROOT / "scripts/testing/waiver/assert_child_waiver_applied.sql"


def psql(sql: str) -> str:
    out = subprocess.check_output([*PG, "-c", sql], env=PG_ENV, text=True)
    return out.strip().split("\n")[0] if out.strip() else ""


def psql_rows(sql: str) -> list[list[str]]:
    out = subprocess.check_output([*PG, "-c", sql], env=PG_ENV, text=True).strip()
    return [line.split("|") for line in out.split("\n") if line]


def post(api: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{ACCT_URL}/{api}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read())


def hdr(stan: str, function_code: str) -> dict:
    return {
        "tenant_code": "mfi", "client_code": "NOVOPAY", "channel_code": "WEB",
        "end_channel_code": "NOVOPAY", "function_code": function_code,
        "function_sub_code": "DEFAULT", "run_mode": "REAL", "operation_mode": "SELF",
        "locale": "en-in", "stan": stan,
        "transmission_datetime": str(int(time.time() * 1000)),
        "user_id": "103", "actor_type": "EMPLOYEE", "user_handle_value": "103",
        "office_id": "2",
    }


def assert_sql(parent_lan: str) -> str:
    out = subprocess.check_output(
        [*PG, "-v", f"PARENT_LAN={parent_lan}", "-f", str(SQL_FILE)], env=PG_ENV, text=True)
    return out.strip().split("\n")[0]


def pick_due(parent_lan: str) -> tuple[str, Decimal, Decimal, int]:
    parent_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account "
        f"WHERE la_account_number='{parent_lan}' AND is_deleted=false;")
    rows = psql_rows(f"""
SELECT ldd.id, ldd.due_date::date,
       (ldd.due_amount - ldd.paid_amount - ldd.waived_amount)
FROM mfi_accounting.loan_due_details ldd
WHERE ldd.loan_account_id = {parent_id} AND ldd.is_deleted = false
  AND ldd.component_type = 'INT'
  AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
ORDER BY ldd.due_date LIMIT 1;
""")
    if not rows:
        raise SystemExit("BLOCKED: no open parent INT due")
    due_id, due_date, pending = rows[0][0], rows[0][1], Decimal(rows[0][2])
    kids = psql_rows(f"""
SELECT c.account_id, COALESCE(MIN(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0)
FROM mfi_accounting.loan_account c
LEFT JOIN mfi_accounting.loan_due_details ldd
  ON ldd.loan_account_id = c.account_id AND ldd.is_deleted = false
 AND ldd.component_type = 'INT' AND ldd.due_date::date = DATE '{due_date}'
WHERE c.parent_loan_account_id = {parent_id} AND c.is_deleted = false
GROUP BY c.account_id ORDER BY c.account_id;
""")
    n = len(kids)
    min_child = min(Decimal(k[1]) for k in kids)
    # Waiver is split EQUALLY across children (GetChildLoanWaiverDetailsProcessor:48-50),
    # not pro rata, so the parent amount must stay within n * smallest child pending.
    cap = min(pending, Decimal(n) * min_child)
    amount = (cap * Decimal("0.5")).quantize(Decimal("1"))
    if amount <= 0:
        raise SystemExit(f"BLOCKED: no headroom (parent_pending={pending} min_child={min_child})")
    print(f"  parent_due_id={due_id} due_date={due_date} parent_pending={pending} "
          f"children={n} min_child_pending={min_child} waive={amount}")
    return due_id, amount, pending, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-lan", required=True)
    args = ap.parse_args()
    parent = args.parent_lan

    print(f"=== childWaiveLoanAccountCharges driver parent={parent} ===")
    print(f"  pre-assert: {assert_sql(parent)}")

    due_id, amount, pending, n_children = pick_due(parent)
    req = {
        "notes": "child waiver fanout coverage",
        "document_details": document_details(document_code="OTHER"),
        "waiver_details_list": [{
            "loan_account_number": parent,
            "loan_due_details_id": due_id,
            "is_fully_waived": "0",
            "waived_amount": format(amount, "f"),
            "amount_to_be_paid": format(pending - amount, "f"),
            "waiver_percentage": format((amount / pending * 100).quantize(Decimal("0.01")), "f"),
        }],
    }
    for fc in ("DEFAULT", "APPROVE"):
        resp = post("waiveLoanAccountCharges",
                    {"headers": hdr(f"cwf_{fc}_{int(time.time())}", fc), "request": req})
        st = resp.get("response_status", {})
        print(f"  waiveLoanAccountCharges {fc}: {st.get('code')}/{st.get('status')} "
              f"{str(st.get('message', ''))[:160]}")
        if st.get("status") != "SUCCESS" and st.get("code") not in ("30321", "30322"):
            print(f"  BLOCKED: {json.dumps(resp)[:600]}")
            return 2
        time.sleep(1)

    queued = psql(f"""
SELECT COUNT(*) FROM mfi_accounting.loan_account_events_queue q
WHERE q.event_type = 'WAIVER' AND q.is_deleted = false
  AND q.parent_account_id = (SELECT account_id FROM mfi_accounting.loan_account
                             WHERE la_account_number='{parent}' AND is_deleted=false);
""")
    print(f"  WAIVER queue rows for parent: {queued}")
    if queued == "0":
        print("  BLOCKED: parent APPROVE did not enqueue a WAIVER child event")
        return 2

    for attempt in range(1, 6):
        before = max_batch_execution_id("childLoanEventProcessingBatchJob")
        subprocess.check_call(
            ["python3", str(ROOT / "scripts/testing/api-fire.py"),
             "childLoanEventProcessingBatchJob", "--batch",
             "--job-time", str(int(time.time() * 1000))], cwd=str(ROOT))
        wait_batch_after("childLoanEventProcessingBatchJob", before, timeout_s=180)
        pending_q = psql(f"""
SELECT COUNT(*) FROM mfi_accounting.loan_account_events_queue q
WHERE q.event_type='WAIVER' AND q.is_deleted=false AND q.event_status='P'
  AND q.parent_account_id = (SELECT account_id FROM mfi_accounting.loan_account
                             WHERE la_account_number='{parent}' AND is_deleted=false);
""")
        print(f"  batch pass {attempt}: pending WAIVER queue rows = {pending_q}")
        if pending_q == "0":
            break
        time.sleep(2)

    verdict = assert_sql(parent)
    print(f"  ASSERT: {verdict}")
    return 0 if verdict == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
