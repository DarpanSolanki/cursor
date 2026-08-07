#!/usr/bin/env python3
"""Drive parent group loanPrepayment (foreclosure) APPROVE so the FCL queue fan-out runs
childLoanForeclosure -> individualChildLoanForeclosure per child, then evaluate the
value-level assert SQL on the child prepayment_details component split."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from clb_queue_harness import max_batch_execution_id, wait_batch_after  # noqa: E402

ACCT_URL = os.environ.get("ACCOUNTING_URL", "http://localhost:8002/accounting/api/v1")
PG_ENV = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
PG = ["psql", "-h", "localhost", "-p", "5433", "-U", "yugabyte", "-d", "yugabyte",
      "-v", "ON_ERROR_STOP=1", "-t", "-A"]
SQL_FILE = ROOT / "scripts/testing/foreclosure/assert_child_fc_split.sql"
USER_ID = os.environ.get("ICF_USER_ID", "103")
OFFICE_ID = os.environ.get("ICF_OFFICE_ID", "2")


def psql(sql: str) -> str:
    out = subprocess.check_output([*PG, "-c", sql], env=PG_ENV, text=True)
    return out.strip().split("\n")[0] if out.strip() else ""


def post(api: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{ACCT_URL}/{api}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
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
        "user_id": USER_ID, "actor_type": "EMPLOYEE", "user_handle_value": USER_ID,
        "office_id": OFFICE_ID,
    }


def component(due: str, waived: Decimal = Decimal("0")) -> dict:
    d = Decimal(str(due or "0"))
    w = waived if waived <= d else d
    return {
        "due_amount": str(d),
        "is_waived": "1" if w > 0 else "0",
        "is_fully_waived": "1" if w > 0 and w == d else "0",
        "waiver_percentage": "",
        "waived_amount": str(w),
        "amount_to_be_paid": str(d - w),
    }


def assert_sql(parent_lan: str) -> str:
    out = subprocess.check_output(
        [*PG, "-v", f"PARENT_LAN={parent_lan}", "-f", str(SQL_FILE)], env=PG_ENV, text=True)
    return out.strip().split("\n")[0]


def simulate(lan: str, fd: str) -> dict:
    body = {"headers": hdr(f"cfc_sim_{int(time.time())}", "DEFAULT"),
            "request": {"account_number": lan, "foreclosure_date": fd}}
    resp = post("fetchLoanForeclosureSimulationDetails", body)
    st = resp.get("response_status", {})
    if st.get("code") != "30360":
        raise SystemExit(f"BLOCKED: simulation {st.get('code')}/{st.get('message')}")
    return resp


def build_request(sim: dict, lan: str, fd: str, receipt: str, waive_bi: Decimal) -> dict:
    fs = sim.get("foreclosure_simulation_details") or {}
    req: dict = {
        "billed_interest_details": component(str(fs.get("billed_interest") or "0"), waive_bi),
        "billed_principal_details": component(str(fs.get("billed_principal") or "0")),
        "balance_principal_details": component(str(fs.get("balance_principal") or "0")),
        "bpi_details": component(str(fs.get("bpi_amount") or "0")),
        "current_lpp_details": component(str(fs.get("current_lpp") or "0")),
        "future_lpp_details": component(str(fs.get("future_lpp") or "0")),
        "foreclosure_fee_details": component(str(fs.get("foreclosure_fee") or "0")),
        "fee_details": [{**component(str(fs.get("cbc_fee") or "0")), "identifier_code": "cbc_fee"}],
        "charges_details": sim.get("charges_details") or [],
    }
    if fs.get("billed_dpi") is not None:
        req["billed_dpi_details"] = component(str(fs.get("billed_dpi") or "0"))
    if fs.get("bpd_amount") is not None:
        req["bpd_details"] = component(str(fs.get("bpd_amount") or "0"))

    total = Decimal("0")
    for key in ("billed_interest_details", "billed_principal_details", "balance_principal_details",
                "bpi_details", "billed_dpi_details", "bpd_details", "current_lpp_details",
                "foreclosure_fee_details"):
        if key in req:
            total += Decimal(req[key]["amount_to_be_paid"])
    total += Decimal(req["fee_details"][0]["amount_to_be_paid"])
    excess = Decimal(str(fs.get("excess_amount") or "0"))
    if excess > 0:
        total -= excess
    rounded = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    req["loan_foreclosure_details"] = {
        "account_number": lan, "foreclosure_date": fd,
        "total_foreclosure_amount": str(rounded), "round_off_amount": str(rounded - total),
        "receipt_number": receipt, "currency_code": "INR", "currency_code_value": "INR",
        "payment_mode": "CASH", "payment_mode_value": "Cash",
        "closure_reason": "RELOC", "closure_reason_value": "Relocation",
        "notes": "child foreclosure component split coverage",
        "paid_by": "CUSTOMER", "paid_by_value": "Customer", "depositor_name": "LOCAL_TEST",
        "excess_amount": str(fs.get("excess_amount") or "0"),
    }
    return req


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-lan", required=True)
    ap.add_argument("--waive-billed-interest", default="0")
    args = ap.parse_args()
    parent = args.parent_lan

    print(f"=== childLoanForeclosure driver parent={parent} ===")
    print(f"  pre-assert: {assert_sql(parent)}")

    fd = str(int(time.time()) * 1000)
    sim = simulate(parent, fd)
    fs = sim.get("foreclosure_simulation_details") or {}
    waive_bi = Decimal(args.waive_billed_interest)
    print(f"  parent sim billed_interest={fs.get('billed_interest')} "
          f"billed_principal={fs.get('billed_principal')} "
          f"balance_principal={fs.get('balance_principal')} bpi={fs.get('bpi_amount')} "
          f"waive_billed_interest={waive_bi}")

    receipt = f"6191{int(time.time()) % 10**12:012d}"
    req = build_request(sim, parent, fd, receipt, waive_bi)
    for fc in ("DEFAULT", "APPROVE_TASK", "APPROVE"):
        resp = post("loanPrepayment", {"headers": hdr(f"cfc_{fc.lower()}_{int(time.time())}", fc),
                                       "request": req})
        st = resp.get("response_status", {})
        print(f"  loanPrepayment {fc}: {st.get('code')}/{st.get('status')} "
              f"{str(st.get('message', ''))[:160]}")
        if st.get("status") != "SUCCESS" and st.get("code") not in (
                "000", "30364", "30365", "30366", "30267"):
            if fc == "APPROVE_TASK":
                print("  WARN: APPROVE_TASK non-success, continuing")
                continue
            print(f"  BLOCKED: {json.dumps(resp)[:1500]}")
            return 2
        time.sleep(1)

    parent_id = psql(f"SELECT account_id FROM mfi_accounting.loan_account "
                     f"WHERE la_account_number='{parent}' AND is_deleted=false;")
    for attempt in range(1, 8):
        pending_q = psql(f"""
SELECT COUNT(*) FROM mfi_accounting.loan_account_events_queue q
WHERE q.event_type='FCL' AND q.is_deleted=false AND q.event_status='P'
  AND q.parent_account_id={parent_id};""")
        done = psql(f"""
SELECT COUNT(DISTINCT pd.loan_account_id) FROM mfi_accounting.prepayment_details pd
JOIN mfi_accounting.loan_account c ON c.account_id=pd.loan_account_id
WHERE c.parent_loan_account_id={parent_id} AND pd.is_deleted=false
  AND pd.prepayment_status='APPROVED';""")
        kids = psql(f"SELECT COUNT(*) FROM mfi_accounting.loan_account c "
                    f"WHERE c.parent_loan_account_id={parent_id};")
        print(f"  poll {attempt}: pending FCL queue={pending_q} approved child prepay={done}/{kids}")
        if pending_q == "0" and done == kids:
            break
        before = max_batch_execution_id("childLoanEventProcessingBatchJob")
        subprocess.check_call(
            ["python3", str(ROOT / "scripts/testing/api-fire.py"),
             "childLoanEventProcessingBatchJob", "--batch",
             "--job-time", str(int(time.time() * 1000))], cwd=str(ROOT))
        wait_batch_after("childLoanEventProcessingBatchJob", before, timeout_s=240)
        time.sleep(2)

    verdict = assert_sql(parent)
    print(f"  ASSERT: {verdict}")
    return 0 if verdict == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
