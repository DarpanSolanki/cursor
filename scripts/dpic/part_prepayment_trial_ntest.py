#!/usr/bin/env python3
"""loanAccountPartPrepayment TRIAL — posts part-prep txn without persisting loan state."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal

ACCT_URL = os.environ.get("ACCOUNTING_URL", "http://localhost:8002/accounting/api/v1")
LAN = os.environ.get("ACCOUNT_NUMBER", "6004044425")
RESCHED_MS = os.environ["RESCHED_MS"]
OVERDUE = Decimal(os.environ.get("PART_PREP_OVERDUE", "0"))
NET = Decimal(os.environ.get("PART_PREP_NET", "5000"))
BPI = Decimal(os.environ.get("PART_PREP_BPI", "0"))
CHARGES = Decimal(os.environ.get("PART_PREP_CHARGES", "0"))
DUE = Decimal(os.environ.get("PART_PREP_DUE", "0"))
BPD = Decimal(os.environ.get("PART_PREP_BPD", "0"))
GROSS = Decimal(os.environ.get("PART_PREP_GROSS", str(OVERDUE + NET + BPI + CHARGES + DUE + BPD)))
RECEIPT = os.environ.get("PART_PREP_RECEIPT", f"pp{int(time.time()) % 1000000000000:012d}")
USER_ID = os.environ.get("PART_PREP_USER_ID", "103")
OFFICE_ID = os.environ.get("PART_PREP_OFFICE_ID", "6")
EXPECT_CODE = os.environ.get("PART_PREP_EXPECT_CODE", "30485")
STAN = os.environ.get("PART_PREP_STAN", f"pp_trial_{int(time.time())}")


def _post(api: str, body: dict) -> dict:
    url = f"{ACCT_URL}/{api}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def _headers() -> dict:
    td = str(int(time.time() * 1000))
    return {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "end_channel_code": "NOVOPAY",
        "function_code": "DEFAULT",
        "function_sub_code": "DEFAULT",
        "run_mode": "TRIAL",
        "operation_mode": "SELF",
        "locale": "en-in",
        "stan": STAN,
        "transmission_datetime": td,
        "user_id": USER_ID,
        "actor_type": "EMPLOYEE",
        "user_handle_value": USER_ID,
        "office_id": OFFICE_ID,
    }


def _find_dpi_amount(payload: object) -> Decimal:
    found = Decimal("0")

    def walk(node: object) -> None:
        nonlocal found
        if isinstance(node, dict):
            ref = str(node.get("reference_code") or node.get("referenceCode") or "")
            amt = node.get("amount") or node.get("net_amount")
            if ref in ("BILLED_DPI_INT_AMT", "ADV_BILLED_DPI_INT_AMT") and amt is not None:
                val = Decimal(str(amt))
                if val > found:
                    found = val
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def main() -> int:
    print(f"=== loanAccountPartPrepayment TRIAL LAN={LAN} gross={GROSS} overdue={OVERDUE} stan={STAN} ===")
    request = {
        "loan_account_number": LAN,
        "rescheduling_effective_date": RESCHED_MS,
        "part_prepayment_impact": "REDUCE_TENOR",
        "broken_period_interest_handling": "NO",
        "bpi_amount": str(BPI),
        "bpd_amount": str(BPD),
        "overdue_amount": str(OVERDUE),
        "overdue_fee_charges": "0",
        "charges": str(CHARGES),
        "net_amount": str(NET),
        "gross_amount": str(GROSS),
        "due_amount": str(DUE),
        "instrument_type": "CASH",
        "receipt_number": RECEIPT,
        "excess_amount": "0",
    }
    body = {"headers": _headers(), "request": request}
    resp = _post("loanAccountPartPrepayment", body)
    status = resp.get("response_status", {})
    code = status.get("code")
    print(f"response: {code}/{status.get('status')} — {status.get('message', '')[:160]}")

    if code != EXPECT_CODE:
        print(json.dumps(resp, indent=2)[:5000])
        return 1

    dpi_amt = _find_dpi_amount(resp)
    if dpi_amt <= 0:
        print("FAIL: overall_transaction_details missing BILLED_DPI_INT_AMT / ADV_BILLED_DPI_INT_AMT > 0")
        print(json.dumps(resp, indent=2)[:5000])
        return 1

    print(f"OK: response DPI leg amount={dpi_amt}")
    print(f"STAN={STAN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
