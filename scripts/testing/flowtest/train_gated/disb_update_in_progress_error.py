#!/usr/bin/env python3
"""updateLoanAccountPreDisbursementDetails NEFT in-flight (TDPQA-241, sha fe703fe04).

The 134498 in-flight-vs-134130 already-disbursed distinction this case asserts was added
by TDPQA-241 and lands on mfi_integration_v3.5.1.1, forward-merging upward from there. On
any lower train (3.4.2.5 and earlier in the chain) UpdateLoanDisbursementModeDetailsProcessor
throws a single generic 134130 for every blocked status, so the assert would fail there for
reasons unrelated to a real defect. Checked live: NOT an ancestor on 3.4.2.5.

Runs the real check only when fe703fe04 is an ancestor of the checked-out accounting HEAD;
otherwise prints SKIPPED and exits 0, so a lower-train checkout does not read as a regression.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[4])
ACCOUNTING_REPO = f"{ROOT}/trustt-platform-accounting"
GATE_SHA = "fe703fe04"
ACCT_URL = os.environ.get("ACCT_URL", "http://localhost:8002/accounting/api/v1")
LAN = os.environ.get("TDPQA241_INFLIGHT_LAN", "")
REF = os.environ.get("TDPQA241_INFLIGHT_REF", "")


def on_qualifying_train() -> bool:
    try:
        subprocess.run(
            ["git", "-C", ACCOUNTING_REPO, "cat-file", "-e", GATE_SHA],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError:
        return False
    r = subprocess.run(
        ["git", "-C", ACCOUNTING_REPO, "merge-base", "--is-ancestor", GATE_SHA, "HEAD"],
        capture_output=True,
    )
    return r.returncode == 0


def fire() -> int:
    body = {
        "external_ref_number": REF,
        "account_number": LAN,
        "disbursement_mode": "OTHBACCT",
        "disbursement_account_number": "50100999888777",
        "disbursement_bank_name": "HDFC BANK",
        "disbursement_account_holder_name": "QA TDPQA241",
    }
    req = urllib.request.Request(
        f"{ACCT_URL}/updateLoanAccountPreDisbursementDetails",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        payload = json.loads(e.read())

    status = payload.get("response_status", {})
    code = status.get("code")
    message = status.get("message")
    expected_code = "134498"
    expected_message = (
        "The loan disbursement payment is currently being processed. "
        "Updating the CASA account is not permitted."
    )
    if code == expected_code and message == expected_message:
        print(f"PASS: code={code} message matches")
        return 0
    print(f"FAIL: code={code} (expected {expected_code}) message={message!r}", file=sys.stderr)
    return 1


def main() -> int:
    if not on_qualifying_train():
        print(
            f"SKIPPED: {GATE_SHA} (TDPQA-241) is not an ancestor of the checked-out "
            "accounting HEAD — this train predates the 134498 in-flight distinction. "
            "Not a failure; re-enable check on 3.5.1.1+."
        )
        return 0
    if not LAN or not REF:
        print("FAIL: TDPQA241_INFLIGHT_LAN / TDPQA241_INFLIGHT_REF not set", file=sys.stderr)
        return 1
    return fire()


if __name__ == "__main__":
    raise SystemExit(main())
