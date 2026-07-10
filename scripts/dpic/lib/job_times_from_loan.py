#!/usr/bin/env python3
"""Derive DPI certification job_time epochs from a loan's installment schedule.

Prints shell exports:
  PRE_EMI_JOB_MS, SINGLE_OVERDUE_JOB_MS, MULTI_OVERDUE_JOB_MS, FORECLOSURE_JOB_MS
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
GRACE_DAYS = int(os.environ.get("GRACE_DAYS", "3"))


def _eod_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 18, 0, 0, tzinfo=IST).timestamp() * 1000)


def _pg_rows(loan_account_id: str) -> list[tuple[date, int]]:
    host = os.environ.get("YB_HOST", "127.0.0.1")
    port = os.environ.get("YB_PORT", "5433")
    user = os.environ.get("YB_USER", "yugabyte")
    db = os.environ.get("YB_DB", "yugabyte")
    pw = os.environ.get("PGPASSWORD", "yugabyte")
    sql = f"""
SELECT lid.installment_date::date, la.expected_disbursement_date::date
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_account la ON la.account_id = lid.loan_account_id
WHERE lid.loan_account_id = {int(loan_account_id)}
  AND lid.is_deleted = false
ORDER BY lid.serial_number
LIMIT 3;
"""
    out = subprocess.check_output(
        ["psql", "-h", host, "-p", port, "-U", user, "-d", db, "-t", "-A", "-F", "|", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env={**os.environ, "PGPASSWORD": pw},
        text=True,
    )
    rows: list[tuple[date, date | None]] = []
    disb: date | None = None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        inst_s, disb_s = line.split("|", 1)
        y, m, d = (int(x) for x in inst_s.split("-"))
        inst = date(y, m, d)
        if disb is None:
            y2, m2, d2 = (int(x) for x in disb_s.split("-"))
            disb = date(y2, m2, d2)
        rows.append((inst, disb))
    if len(rows) < 2 or disb is None:
        raise SystemExit(f"need >=2 installments + disburse date for loan {loan_account_id}")
    return [(r[0], disb) for r in rows]


def _after_grace(emi_due: date) -> int:
    return _eod_ms(emi_due + timedelta(days=GRACE_DAYS + 1))


def main() -> None:
    loan_id = os.environ.get("LOAN_ACCOUNT_ID")
    if not loan_id:
        raise SystemExit("LOAN_ACCOUNT_ID required")
    schedule = _pg_rows(loan_id)
    first_emi = schedule[0][0]
    second_emi = schedule[1][0]
    disb = schedule[0][1]
    pre = disb + timedelta(days=7)
    if pre >= first_emi:
        pre = first_emi - timedelta(days=2)
    fc = second_emi + timedelta(days=GRACE_DAYS + 5)
    exports = {
        "PRE_EMI_JOB_MS": str(_eod_ms(pre)),
        "SINGLE_OVERDUE_JOB_MS": str(_after_grace(first_emi)),
        "MULTI_OVERDUE_JOB_MS": str(_after_grace(second_emi)),
        "FORECLOSURE_JOB_MS": str(_eod_ms(fc)),
        "FIRST_EMI_DATE": first_emi.isoformat(),
        "SECOND_EMI_DATE": second_emi.isoformat(),
    }
    for k, v in exports.items():
        print(f"export {k}={v}")


if __name__ == "__main__":
    main()
