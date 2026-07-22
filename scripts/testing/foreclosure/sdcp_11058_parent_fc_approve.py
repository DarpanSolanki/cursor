#!/usr/bin/env python3
"""SDCP-11058 — build parent loanPrepayment APPROVE from simulation JSON and fire REAL."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP

ACCT_URL = os.environ.get("ACCOUNTING_URL", "http://localhost:8002/accounting/api/v1")
USER_ID = os.environ.get("ICF_USER_ID", "103")
OFFICE_ID = os.environ.get("ICF_OFFICE_ID", "2")


def _post(api: str, body: dict) -> dict:
    url = f"{ACCT_URL}/{api}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def _headers(stan: str, *, function_code: str = "APPROVE") -> dict:
    td = str(int(time.time() * 1000))
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
        "transmission_datetime": td,
        "user_id": USER_ID,
        "actor_type": "EMPLOYEE",
        "user_handle_value": USER_ID,
        "office_id": OFFICE_ID,
    }


def _component(due: str) -> dict:
    d = Decimal(str(due or "0"))
    return {
        "due_amount": str(d),
        "is_waived": "0",
        "is_fully_waived": "0",
        "waiver_percentage": "",
        "waived_amount": "0",
        "amount_to_be_paid": str(d),
    }


def _build_request(sim: dict, lan: str, fd: str, receipt: str) -> dict:
    fs = sim.get("foreclosure_simulation_details") or {}
    charges = sim.get("charges_details") or []
    request: dict = {
        "billed_interest_details": _component(str(fs.get("billed_interest") or "0")),
        "billed_principal_details": _component(str(fs.get("billed_principal") or "0")),
        "balance_principal_details": _component(str(fs.get("balance_principal") or "0")),
        "bpi_details": _component(str(fs.get("bpi_amount") or "0")),
        "current_lpp_details": _component(str(fs.get("current_lpp") or "0")),
        "future_lpp_details": _component(str(fs.get("future_lpp") or "0")),
        "foreclosure_fee_details": _component(str(fs.get("foreclosure_fee") or "0")),
        "fee_details": [{**_component(str(fs.get("cbc_fee") or "0")), "identifier_code": "cbc_fee"}],
        "charges_details": charges,
    }
    # Optional DPI/BPD keys when present on train
    if fs.get("billed_dpi") is not None:
        request["billed_dpi_details"] = _component(str(fs.get("billed_dpi") or "0"))
    if fs.get("bpd_amount") is not None:
        request["bpd_details"] = _component(str(fs.get("bpd_amount") or "0"))

    total = (
        Decimal(str(fs.get("billed_interest") or "0"))
        + Decimal(str(fs.get("billed_principal") or "0"))
        + Decimal(str(fs.get("balance_principal") or "0"))
        + Decimal(str(fs.get("bpi_amount") or "0"))
        + Decimal(str(fs.get("billed_dpi") or "0"))
        + Decimal(str(fs.get("bpd_amount") or "0"))
        + Decimal(str(fs.get("current_lpp") or "0"))
        + Decimal(str(fs.get("foreclosure_fee") or "0"))
        + Decimal(str(fs.get("cbc_fee") or "0"))
    )
    excess = Decimal(str(fs.get("excess_amount") or "0"))
    if excess > 0:
        total -= excess
    rounded = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    round_off = rounded - total
    request["loan_foreclosure_details"] = {
        "account_number": lan,
        "foreclosure_date": fd,
        "total_foreclosure_amount": str(rounded),
        "round_off_amount": str(round_off),
        "receipt_number": receipt,
        "currency_code": "INR",
        "currency_code_value": "INR",
        "payment_mode": "CASH",
        "payment_mode_value": "Cash",
        "closure_reason": "RELOC",
        "closure_reason_value": "Relocation",
        "notes": "SDCP-11058 local SHG parent FC BPI parity",
        "paid_by": "CUSTOMER",
        "paid_by_value": "Customer",
        "depositor_name": "LOCAL_TEST",
        "excess_amount": str(fs.get("excess_amount") or "0"),
    }
    return request


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lan", required=True)
    ap.add_argument("--foreclosure-date", required=True)
    ap.add_argument("--sim-json", required=True)
    args = ap.parse_args()
    with open(args.sim_json) as f:
        sim = json.load(f)
    receipt = f"6191{int(time.time()) % 10**12:012d}"
    request = _build_request(sim, args.lan, args.foreclosure_date, receipt)
    parent_bpi = (sim.get("foreclosure_simulation_details") or {}).get("bpi_amount")
    print(f"parent_lan={args.lan} parent_bpi_quote={parent_bpi} receipt={receipt}")

    # SHG parent: DEFAULT REAL creates task/prepayment; then APPROVE_TASK; then APPROVE posts + child fan-out
    for fc in ("DEFAULT", "APPROVE_TASK", "APPROVE"):
        stan = f"sdcp11058_{fc.lower()}_{int(time.time())}"
        body = {"headers": _headers(stan, function_code=fc), "request": request}
        resp = _post("loanPrepayment", body)
        status = resp.get("response_status", {})
        code = status.get("code")
        print(f"loanPrepayment {fc}: {code}/{status.get('status')} — {str(status.get('message', ''))[:160]}")
        if code not in ("000", "30365", "30364", "30267", "30366") and status.get("status") != "SUCCESS":
            # APPROVE_TASK may be no-op if no task workflow locally — continue to APPROVE if PENDING exists
            if fc == "APPROVE_TASK" and code in ("333", "13005", "334"):
                print(f"WARN: APPROVE_TASK {code} — continuing to APPROVE if PENDING prepayment exists")
                time.sleep(1)
                continue
            print(json.dumps(resp, indent=2)[:4000])
            return 1
        time.sleep(1)
    print("OK: parent loanPrepayment DEFAULT+APPROVE_TASK+APPROVE accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
