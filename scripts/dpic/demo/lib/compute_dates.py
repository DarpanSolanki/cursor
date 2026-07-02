#!/usr/bin/env python3
"""Compute DPIC demo milestone dates from presentation anchor (default 15-Jun-2026).

EMI day = 14th of month. Timeline for demo on anchor day:
  disburse → 1st EMI (prior month 14th) → accrual from 15th → month-end GL → 2nd EMI billing (14th) → APIs on anchor.

Usage:
  python3 compute_dates.py                    # print shell exports
  python3 compute_dates.py --anchor 2026-06-15
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
EMI_DAY = 14


def _midnight_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=IST).timestamp() * 1000)


def _eod_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 18, 0, 0, tzinfo=IST).timestamp() * 1000)


def plan(anchor: date) -> dict[str, str]:
    # 2nd EMI = 14th of anchor month (billing); if anchor is before 14th, use anchor month 14th anyway
    second_emi = date(anchor.year, anchor.month, EMI_DAY)
    if second_emi > anchor:
        # anchor is 15th — 14th is yesterday; OK
        pass

    # 1st EMI = 14th of previous month
    if anchor.month == 1:
        first_emi = date(anchor.year - 1, 12, EMI_DAY)
    else:
        first_emi = date(anchor.year, anchor.month - 1, EMI_DAY)

    first_emi_plus1 = first_emi + timedelta(days=1)
    last_dom = calendar.monthrange(first_emi.year, first_emi.month)[1]
    month_end = date(first_emi.year, first_emi.month, last_dom)
    # Disburse ~61 days before 1st EMI (matches monthly MFI spacing in local payload)
    disburse = first_emi - timedelta(days=61)

    return {
        "DEMO_ANCHOR_DATE": anchor.isoformat(),
        "DEMO_ANCHOR_MS": str(_eod_ms(anchor)),
        "DEMO_DISBURSE_DATE": disburse.isoformat(),
        "DEMO_DISBURSE_MS": str(_midnight_ms(disburse)),
        "DEMO_FIRST_EMI_DATE": first_emi.isoformat(),
        "DEMO_FIRST_EMI_MS": str(_midnight_ms(first_emi)),
        "DEMO_FIRST_EMI_PLUS1_DATE": first_emi_plus1.isoformat(),
        "DEMO_FIRST_EMI_PLUS1_MS": str(_eod_ms(first_emi_plus1)),
        "DEMO_MONTH_END_DATE": month_end.isoformat(),
        "DEMO_MONTH_END_MS": str(_eod_ms(month_end)),
        "DEMO_SECOND_EMI_DATE": second_emi.isoformat(),
        "DEMO_SECOND_EMI_MS": str(_eod_ms(second_emi)),
        "DEMO_FORECLOSURE_MS": str(_eod_ms(anchor)),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--anchor", default="2026-06-15", help="Presentation date YYYY-MM-DD")
    args = p.parse_args()
    y, m, d = (int(x) for x in args.anchor.split("-"))
    for k, v in plan(date(y, m, d)).items():
        print(f"export {k}={v}")


if __name__ == "__main__":
    main()
