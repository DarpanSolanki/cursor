#!/usr/bin/env python3
"""Derive DPI fast-EOD milestone epochs from a loan's real installment schedule.

Usage (prints shell exports):
  LOAN_ACCOUNT_ID=8058960 python3 eod_milestones_from_loan.py
"""
from __future__ import annotations

import calendar
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def _eod_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 18, 0, 0, tzinfo=IST).timestamp() * 1000)


def _pg_dates(loan_account_id: str) -> tuple[date, date]:
    host = os.environ.get("YB_HOST", "127.0.0.1")
    port = os.environ.get("YB_PORT", "5433")
    user = os.environ.get("YB_USER", "yugabyte")
    db = os.environ.get("YB_DB", "yugabyte")
    pw = os.environ.get("PGPASSWORD", "yugabyte")
    sql = f"""
SELECT installment_date::date
FROM mfi_accounting.loan_installment_details
WHERE loan_account_id = {int(loan_account_id)} AND is_deleted = false
ORDER BY serial_number
LIMIT 2;
"""
    out = subprocess.check_output(
        ["psql", "-h", host, "-p", port, "-U", user, "-d", db, "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env={**os.environ, "PGPASSWORD": pw},
        text=True,
    )
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise SystemExit(f"need >=2 installments for loan {loan_account_id}, got {lines!r}")
    y1, m1, d1 = (int(x) for x in lines[0].split("-"))
    y2, m2, d2 = (int(x) for x in lines[1].split("-"))
    return date(y1, m1, d1), date(y2, m2, d2)


def plan(first_emi: date, second_emi: date, calendar_anchor: date) -> dict[str, str]:
    first_plus1 = first_emi + timedelta(days=1)
    last_dom = calendar.monthrange(first_emi.year, first_emi.month)[1]
    month_end = date(first_emi.year, first_emi.month, last_dom)
    # Business anchor for demo APIs: latest milestone (2nd EMI EOD), even if after calendar today.
    anchor = max(calendar_anchor, second_emi)
    return {
        "DEMO_FIRST_EMI_DATE": first_emi.isoformat(),
        "DEMO_FIRST_EMI_MS": str(_eod_ms(first_emi)),
        "DEMO_FIRST_EMI_PLUS1_DATE": first_plus1.isoformat(),
        "DEMO_FIRST_EMI_PLUS1_MS": str(_eod_ms(first_plus1)),
        "DEMO_MONTH_END_DATE": month_end.isoformat(),
        "DEMO_MONTH_END_MS": str(_eod_ms(month_end)),
        "DEMO_SECOND_EMI_DATE": second_emi.isoformat(),
        "DEMO_SECOND_EMI_MS": str(_eod_ms(second_emi)),
        "DEMO_ANCHOR_DATE": anchor.isoformat(),
        "DEMO_ANCHOR_MS": str(_eod_ms(anchor)),
        "DEMO_FORECLOSURE_MS": str(_eod_ms(anchor)),
        "JOB_TIME": str(_eod_ms(anchor)),
    }


def main() -> None:
    loan_id = os.environ.get("LOAN_ACCOUNT_ID")
    if not loan_id:
        raise SystemExit("LOAN_ACCOUNT_ID required")
    first_emi, second_emi = _pg_dates(loan_id)
    anchor = date.today()
    for k, v in plan(first_emi, second_emi, anchor).items():
        print(f"export {k}={v}")


if __name__ == "__main__":
    main()
