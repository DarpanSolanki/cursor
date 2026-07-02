#!/usr/bin/env python3
"""Fail before disburse if disburse→first EMI gap exceeds product max (60 days for demo product)."""
import sys
from datetime import datetime, timezone

MAX_GAP_DAYS = 60


def main() -> None:
    disb_ms, emi_ms = (int(x) for x in sys.argv[1:3])
    disb = datetime.fromtimestamp(disb_ms / 1000, tz=timezone.utc).date()
    emi = datetime.fromtimestamp(emi_ms / 1000, tz=timezone.utc).date()
    gap = (emi - disb).days
    if gap > MAX_GAP_DAYS:
        print(
            f"FAIL: disburse→first EMI gap is {gap} days (max {MAX_GAP_DAYS}). "
            f"Would trigger 134233 in async disburseLoan. Adjust demo_config / compute_dates.py.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"OK: disburse→first EMI gap={gap} days (max {MAX_GAP_DAYS})")


if __name__ == "__main__":
    main()
