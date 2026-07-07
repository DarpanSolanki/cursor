#!/usr/bin/env python3
"""SDCP-10199 parent last-child DFC — logic simulation (child vs parent settlement rules).

Mirrors DeathForeclosureInsuranceWriter intent:
  - Child + parent last-child: PRIN settled as paid_amount (insurance), not waived.
  - INT: future rows waived only (waiveFutureInterestPastReporting).

Usage:
  python3 scripts/dcf_sanity/parent_last_child_dfc_simulation.py
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class DueRow:
    due_date: str
    component: str
    due: Decimal
    paid: Decimal = Decimal("0")
    waived: Decimal = Decimal("0")

    @property
    def pending(self) -> Decimal:
        return self.due - self.paid - self.waived


def waive_future_int_only(rows: list[DueRow], reporting: str) -> None:
    for r in rows:
        if r.component != "INT" or r.due_date <= reporting:
            continue
        r.waived += r.pending


def appropriate_prin_paid(rows: list[DueRow], principal_budget: Decimal) -> None:
    budget = principal_budget
    for r in sorted(rows, key=lambda x: (x.due_date, x.component)):
        if r.component != "PRIN" or budget <= 0:
            continue
        take = min(r.pending, budget)
        r.paid += take
        budget -= take


def waive_all_future_pending(rows: list[DueRow], reporting: str) -> None:
    """Legacy 3.4.2.x bug — waives PRIN + INT."""
    for r in rows:
        if r.due_date <= reporting:
            continue
        r.waived += r.pending


def prin_pending(rows: list[DueRow]) -> Decimal:
    return sum(r.pending for r in rows if r.component == "PRIN")


def prin_waived(rows: list[DueRow]) -> Decimal:
    return sum(r.waived for r in rows if r.component == "PRIN")


def main() -> int:
    reporting = "2026-07-06"
    # Same shape as QA3 child 6002330226 future tail
    child_rows = [
        DueRow("2026-05-05", "PRIN", Decimal("833"), paid=Decimal("833")),
        DueRow("2026-06-05", "PRIN", Decimal("840"), paid=Decimal("840")),
        DueRow("2026-07-06", "PRIN", Decimal("848")),
        DueRow("2026-11-05", "PRIN", Decimal("872")),
        DueRow("2026-07-06", "INT", Decimal("36")),
        DueRow("2026-11-05", "INT", Decimal("7")),
    ]
    waive_future_int_only(child_rows, reporting)
    appropriate_prin_paid(child_rows, Decimal("848") + Decimal("872"))
    assert prin_pending(child_rows) == 0, "child PRIN pending"
    assert prin_waived(child_rows) == 0, "child PRIN must not be waived"

    parent_rows = [
        DueRow("2026-06-05", "PRIN", Decimal("2479"), paid=Decimal("2308")),
        DueRow("2026-07-06", "PRIN", Decimal("1989")),
        DueRow("2026-11-05", "PRIN", Decimal("2058")),
        DueRow("2026-07-06", "INT", Decimal("87")),
        DueRow("2026-11-05", "INT", Decimal("17")),
    ]
    parent_os = sum(r.pending for r in parent_rows if r.component == "PRIN")

    # Old parent last-child path (waive all future) — wrong for PRIN
    broken = [DueRow(r.due_date, r.component, r.due, r.paid, r.waived) for r in parent_rows]
    waive_all_future_pending(broken, reporting)
    assert prin_waived(broken) > 0, "broken path should waive PRIN"

    # Fixed parent last-child path
    fixed = [DueRow(r.due_date, r.component, r.due, r.paid, r.waived) for r in parent_rows]
    waive_future_int_only(fixed, reporting)
    appropriate_prin_paid(fixed, parent_os)
    assert prin_pending(fixed) == 0, "parent PRIN pending after fix"
    assert prin_waived(fixed) == 0, "parent PRIN waived after fix"

    print("PASS: parent_last_child_dfc_simulation — PRIN paid, INT-only waive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
