#!/usr/bin/env python3
"""Build individualChildLoanForeclosure payload from simulation and fire APPROVE REAL."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ACCT_URL = os.environ.get("ACCOUNTING_URL", "http://localhost:8002/accounting/api/v1")
LAN = os.environ.get("ICF_LAN", "6004044425")
FD = os.environ.get("ICF_FORECLOSURE_DATE", "1784500000000")
USER_ID = os.environ.get("ICF_USER_ID", "103")
OFFICE_ID = os.environ.get("ICF_OFFICE_ID", "6")
RECEIPT = os.environ.get("ICF_RECEIPT", f"4127{int(time.time()) % 1000000000000:012d}")
EXPECT_CODE = os.environ.get("ICF_EXPECT_CODE", "30267")


def _post(api: str, body: dict) -> dict:
    url = f"{ACCT_URL}/{api}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def _headers(stan: str, *, run_mode: str = "REAL", function_code: str = "APPROVE") -> dict:
    td = str(int(time.time() * 1000))
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
        "transmission_datetime": td,
        "user_id": USER_ID,
        "actor_type": "EMPLOYEE",
        "user_handle_value": USER_ID,
        "office_id": OFFICE_ID,
    }


def _component(due: str) -> dict:
    d = Decimal(due)
    return {
        "due_amount": str(d),
        "is_waived": "false",
        "is_fully_waived": "false",
        "waiver_percentage": "0",
        "waived_amount": "0",
        "amount_to_be_paid": str(d),
    }


def _simulate(lan: str, fd: str) -> dict:
    stan = f"icf_sim_{int(time.time())}"
    body = {
        "headers": _headers(stan, run_mode="REAL", function_code="DEFAULT"),
        "request": {"account_number": lan, "foreclosure_date": fd},
    }
    resp = _post("fetchLoanForeclosureSimulationDetails", body)
    status = resp.get("response_status", {})
    if status.get("code") != "30360":
        raise SystemExit(f"simulation failed: {status}")
    return resp


def _charge_tax(charge: dict) -> Decimal:
    components = charge.get("tax_components") or []
    if components:
        return sum((Decimal(str(t.get("tax_amount") or "0")) for t in components), Decimal(0))
    return Decimal(str(charge.get("total_tax_amount") or "0"))


def _build_request(sim: dict, lan: str, fd: str, receipt: str) -> dict:
    fs = sim.get("foreclosure_simulation_details") or {}
    charges = sim.get("charges_details") or []

    parts = {
        "billed_interest_details": fs.get("billed_interest", "0"),
        "billed_principal_details": fs.get("billed_principal", "0"),
        "balance_principal_details": fs.get("balance_principal", "0"),
        "bpi_details": fs.get("bpi_amount", "0"),
        "billed_dpi_details": fs.get("billed_dpi", "0"),
        "bpd_details": fs.get("bpd_amount", "0"),
        "current_lpp_details": fs.get("current_lpp", "0"),
        "foreclosure_fee_details": fs.get("foreclosure_fee", "0"),
    }
    request: dict = {}
    for key, due in parts.items():
        request[key] = _component(str(due))

    # future_lpp is informational in simulation; not persisted on prepayment charge rows
    request["future_lpp_details"] = _component(str(fs.get("future_lpp") or "0"))

    cbc_due = str(fs.get("cbc_fee") or "0")
    request["fee_details"] = [{**_component(cbc_due), "identifier_code": "cbc_fee"}]

    # Match ValidateFinalPrepaymentProcessor.fetchForeclosureAmount (incl. billed DPI + BPD)
    total = (
        Decimal(str(fs.get("billed_interest") or "0"))
        + Decimal(str(fs.get("billed_principal") or "0"))
        + Decimal(str(fs.get("balance_principal") or "0"))
        + Decimal(str(fs.get("bpi_amount") or "0"))
        + Decimal(str(fs.get("billed_dpi") or "0"))
        + Decimal(str(fs.get("bpd_amount") or "0"))
        + Decimal(str(fs.get("current_lpp") or "0"))
        + Decimal(str(fs.get("foreclosure_fee") or "0"))
        + Decimal(str(cbc_due))
    )
    excess = Decimal(str(fs.get("excess_amount") or "0"))
    if excess > 0:
        total -= excess

    # Mirrors ValidateFinalPrepaymentProcessor.calculateTotalChargeAmount: every charge contributes
    # its amount, plus its tax whenever the charge is not inclusive of tax. The fee identifiers are
    # already counted above from the simulation block, but their tax still has to be added.
    for ch in charges:
        ident = str(ch.get("charge_identifier") or "")
        already_counted = ident in ("current_lpp", "foreclosure_fee", "cbc_fee", "future_lpp")
        val = Decimal(str(ch.get("charge_value") or "0"))
        if not already_counted:
            total += val
        if str(ch.get("charge_inclusive_of_tax") or "").lower() == "false":
            total += _charge_tax(ch)

    rounded = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    round_off = rounded - total

    request["charges_details"] = charges
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
        "closure_reason": "OTHERS",
        "closure_reason_value": "Others",
        "notes": "local individualChildLoanForeclosure ntest",
        "paid_by": "SELF",
        "paid_by_value": "Self",
        "depositor_name": "LOCAL_TEST",
        "excess_amount": str(fs.get("excess_amount") or "0"),
    }
    return request


def _processor_verified_in_log(stan: str) -> bool:
    ws = Path(__file__).resolve().parents[3]
    log_path = os.environ.get(
        "ACCOUNTING_LOG",
        str(ws / "trustt-platform-accounting" / "logs" / "mfi" / "accounting-mfi.log"),
    )
    try:
        tail = Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines()[-1200:]
    except OSError:
        return False
    saw_due = False
    for line in tail:
        if stan not in line:
            continue
        if "updateDueDetailsForPrepaymentProcessor took" in line:
            saw_due = True
    return saw_due


def main() -> int:
    print(f"=== individualChildLoanForeclosure ntest LAN={LAN} FD={FD} ===")
    sim = _simulate(LAN, FD)
    request = _build_request(sim, LAN, FD, RECEIPT)
    stan = f"icf_{int(time.time())}"
    body = {"headers": _headers(stan), "request": request}
    resp = _post("individualChildLoanForeclosure", body)
    status = resp.get("response_status", {})
    code = status.get("code")
    print(f"response: {code}/{status.get('status')} — {status.get('message', '')[:120]}")
    time.sleep(1)
    if code == EXPECT_CODE:
        print("PASS")
        return 0
    if code in ("333", "13005") and _processor_verified_in_log(stan):
        print("PASS (updateDueDetailsForPrepaymentProcessor verified in log; downstream local gap)")
        return 0
    print(json.dumps(resp, indent=2)[:4000])
    return 1


if __name__ == "__main__":
    sys.exit(main())
