#!/usr/bin/env python3
"""Assert SDCP-10199 parent last-child DFC DB invariants (local / QA)."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from decimal import Decimal


def psql_scalar(sql: str) -> str:
    env = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
    cmd = [
        "psql",
        "-h", os.environ.get("YB_HOST", "localhost"),
        "-p", os.environ.get("YB_PORT", "5433"),
        "-U", os.environ.get("YB_USER", "yugabyte"),
        "-d", os.environ.get("YB_DB", "yugabyte"),
        "-t", "-A",
        "-c", sql,
    ]
    out = subprocess.check_output(cmd, env=env, text=True).strip()
    return out.split("\n")[0] if out else ""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--parent-lan", required=True)
    args = p.parse_args()
    lan = args.parent_lan.replace("'", "")

    status = psql_scalar(
        f"SELECT loan_status FROM mfi_accounting.loan_account "
        f"WHERE account_number='{lan}' AND is_deleted=false LIMIT 1;"
    )
    prin_pending = Decimal(psql_scalar(
        f"SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0) "
        f"FROM mfi_accounting.loan_due_details ldd "
        f"JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id "
        f"WHERE la.account_number='{lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;"
    ) or "0")
    prin_waived = Decimal(psql_scalar(
        f"SELECT COALESCE(SUM(waived_amount),0) FROM mfi_accounting.loan_due_details ldd "
        f"JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id "
        f"WHERE la.account_number='{lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;"
    ) or "0")
    future_prin_waived = Decimal(psql_scalar(
        f"SELECT COALESCE(SUM(waived_amount),0) FROM mfi_accounting.loan_due_details ldd "
        f"JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id "
        f"WHERE la.account_number='{lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false "
        f"AND ldd.due_date > CURRENT_DATE;"
    ) or "0")

    ok = True
    if status != "CLOSED":
        print(f"FAIL: parent loan_status={status!r} (expected CLOSED)")
        ok = False
    if prin_pending != 0:
        print(f"FAIL: parent PRIN pending={prin_pending} (expected 0)")
        ok = False
    if future_prin_waived != 0:
        print(f"FAIL: future PRIN waived={future_prin_waived} (expected 0 — insurance pays PRIN)")
        ok = False
    if prin_waived != 0:
        print(f"WARN: parent total PRIN waived={prin_waived} (product rule: PRIN paid, not waived)")

    if ok:
        print(f"PASS: parent {lan} last-child DFC invariants")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
