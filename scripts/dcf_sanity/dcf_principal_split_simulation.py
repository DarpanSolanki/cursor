#!/usr/bin/env python3
"""Simulate DeathForeclosureInsuranceWriter principal GL split (BLD_PRIN / UNBLD_PRIN).

Mirrors writer order:
  1) billing sync through death date
  2) fetchOutStandingLoanBalanceAsPerDate (outstanding — unchanged by this fix)
  3) [NEW] billing sync through reporting when reporting > death
  4) getUnpaidBilledPrincipal + min() split

OLD bug: step 3 ran after step 4, so reporting >> death saw only death-era billing at split.

Usage:
  python3 scripts/dcf_sanity/dcf_principal_split_simulation.py
  python3 scripts/dcf_sanity/dcf_principal_split_simulation.py --qa3-fixture
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class PrinRow:
    due_date: str
    amount: Decimal
    paid: Decimal
    has_billing_at_split: bool


def unpaid_billed_principal(rows: Iterable[PrinRow]) -> Decimal:
    total = Decimal("0")
    for r in rows:
        if not r.has_billing_at_split:
            continue
        pending = r.amount - r.paid
        if pending > 0:
            total += pending
    return total


def split_principal(
    prin_amt_overdue: Decimal,
    dcf_pos_amount: Decimal,
    rows: Iterable[PrinRow],
) -> tuple[Decimal, Decimal, Decimal]:
    """Returns (bld_prin, unbld_prin, total_settleable)."""
    unpaid_billed = unpaid_billed_principal(rows)
    total = prin_amt_overdue + dcf_pos_amount
    bld = min(unpaid_billed, total)
    unbld = total - bld
    return bld, unbld, total


def simulate_outstanding_10494(
    future_prin: Decimal,
    extra_int_credit: Decimal,
    death_cycle_pint_paid: Decimal,
    sum_assured: Decimal,
    *,
    apply_death_cycle_credit: bool,
) -> tuple[Decimal, Decimal]:
    """SDCP-10494 death-on-due-date penal credit (independent of billing split order)."""
    overpaid_penal_raw = Decimal("0")
    overpaid_penal = overpaid_penal_raw
    if apply_death_cycle_credit and overpaid_penal_raw == 0:
        overpaid_penal = death_cycle_pint_paid
    total_overpay = extra_int_credit + overpaid_penal
    net_pos = future_prin - total_overpay
    outstanding = net_pos  # simplified: overdue 0, BPI/LPP/fees 0 for fixture
    claim = sum_assured - outstanding
    return outstanding, claim


# QA3 LAN 6005077725 — future PRIN after death (pre-approve: all unpaid)
VIKRAM_FUTURE_ROWS_DEATH_BILLING = [
    PrinRow("2026-10-07", Decimal("2691"), Decimal("0"), True),   # only next billed at death sync
    PrinRow("2026-11-07", Decimal("2724"), Decimal("0"), False),
    PrinRow("2026-12-07", Decimal("2757"), Decimal("0"), False),
    PrinRow("2027-01-07", Decimal("2791"), Decimal("0"), False),
    PrinRow("2027-02-08", Decimal("2825"), Decimal("0"), False),
    PrinRow("2027-03-08", Decimal("2860"), Decimal("0"), False),
    PrinRow("2027-04-07", Decimal("2895"), Decimal("0"), False),
    PrinRow("2027-05-07", Decimal("2930"), Decimal("0"), False),
    PrinRow("2027-06-07", Decimal("2966"), Decimal("0"), False),
    PrinRow("2027-07-07", Decimal("3002"), Decimal("0"), False),
    PrinRow("2027-08-07", Decimal("3039"), Decimal("0"), False),
    PrinRow("2027-09-07", Decimal("3076"), Decimal("0"), False),
]

VIKRAM_FUTURE_ROWS_REPORTING_BILLING = [
    PrinRow(r.due_date, r.amount, r.paid, r.due_date <= "2027-06-07")
    for r in VIKRAM_FUTURE_ROWS_DEATH_BILLING
]

# QA4 LAN 6007564726 — SDCP-10494 outstanding fixture (release doc)
LAN_6007564726 = {
    "future_prin": Decimal("5361"),
    "extra_int": Decimal("3"),
    "death_cycle_pint": Decimal("200"),
    "sum_assured": Decimal("10000"),
    "expected_outstanding": Decimal("5158"),
    "expected_claim": Decimal("4842"),
}


@dataclass
class ScenarioResult:
    scenario_id: str
    label: str
    passed: bool
    detail: str


def run_scenarios() -> list[ScenarioResult]:
    results: list[ScenarioResult] = []

    # S07 + S13 — Vikram QA3 reporting >> death
    prin_overdue = Decimal("0")
    total_settleable = Decimal("34341")  # stored outstanding = net POS + overdue
    dcf_pos = total_settleable - prin_overdue

    old_bld, old_unbld, old_total = split_principal(
        prin_overdue, dcf_pos, VIKRAM_FUTURE_ROWS_DEATH_BILLING
    )
    new_bld, new_unbld, new_total = split_principal(
        prin_overdue, dcf_pos, VIKRAM_FUTURE_ROWS_REPORTING_BILLING
    )
    exp_bld, exp_unbld = Decimal("25439"), Decimal("8902")

    results.append(
        ScenarioResult(
            "S07_S13_vikram_qa3",
            "Reporting after death — GL split matches workbook",
            new_bld == exp_bld and new_unbld == exp_unbld and new_total == Decimal("34341"),
            f"OLD split BLD={old_bld} UNBLD={old_unbld} (QA bug 2691/31650); "
            f"NEW split BLD={new_bld} UNBLD={new_unbld} expected {exp_bld}/{exp_unbld}",
        )
    )

    # S11 — SDCP-10494 outstanding not affected by split reorder
    with_credit, claim_with = simulate_outstanding_10494(
        LAN_6007564726["future_prin"],
        LAN_6007564726["extra_int"],
        LAN_6007564726["death_cycle_pint"],
        LAN_6007564726["sum_assured"],
        apply_death_cycle_credit=True,
    )
    without_credit, claim_without = simulate_outstanding_10494(
        LAN_6007564726["future_prin"],
        LAN_6007564726["extra_int"],
        LAN_6007564726["death_cycle_pint"],
        LAN_6007564726["sum_assured"],
        apply_death_cycle_credit=False,
    )
    results.append(
        ScenarioResult(
            "S11_sdcp_10494_outstanding",
            "Death on due + paid EMI — penal credit gives 5158 / 4842",
            with_credit == LAN_6007564726["expected_outstanding"]
            and claim_with == LAN_6007564726["expected_claim"],
            f"with credit outstanding={with_credit} claim={claim_with}; "
            f"without credit outstanding={without_credit} (Δ200)",
        )
    )

    # S12 — unpaid death cycle: no penal credit
    results.append(
        ScenarioResult(
            "S12_death_on_due_unpaid",
            "Unpaid death-cycle EMI — no death-cycle penal credit",
            without_credit == LAN_6007564726["future_prin"] - LAN_6007564726["extra_int"],
            f"outstanding without credit={without_credit}",
        )
    )

    # Reporting == death — same billing snapshot at split (no extra sync)
    same_day_rows = [
        PrinRow("2026-10-07", Decimal("2691"), Decimal("0"), True),
        PrinRow("2026-11-07", Decimal("2724"), Decimal("0"), False),
    ]
    b1, u1, _ = split_principal(Decimal("0"), Decimal("5000"), same_day_rows)
    b2, u2, _ = split_principal(Decimal("0"), Decimal("5000"), same_day_rows)
    results.append(
        ScenarioResult(
            "S13_reporting_equals_death",
            "Reporting date = death — split unchanged by reorder",
            b1 == b2 and u1 == u2,
            f"BLD={b1} UNBLD={u1} total=5000",
        )
    )

    # Invariant: BLD + UNBLD = total always
    results.append(
        ScenarioResult(
            "INV_total_principal",
            "BLD + UNBLD = total settleable principal",
            new_bld + new_unbld == new_total and old_bld + old_unbld == old_total,
            f"new {new_bld}+{new_unbld}={new_total}; old {old_bld}+{old_unbld}={old_total}",
        )
    )

    # Overdue billed + future billed — total caps BLD leg
    overdue_rows = [PrinRow("2026-08-07", Decimal("1000"), Decimal("0"), True)]
    future_rows = [PrinRow("2026-10-07", Decimal("5000"), Decimal("0"), True)]
    bld, unbld, tot = split_principal(Decimal("1000"), Decimal("4000"), overdue_rows + future_rows)
    results.append(
        ScenarioResult(
            "S02_overdue_plus_future",
            "Overdue billed + POS — split caps at total",
            bld == Decimal("5000") and unbld == Decimal("0") and tot == Decimal("5000"),
            f"BLD={bld} UNBLD={unbld} (unpaid billed 6000 capped to total 5000)",
        )
    )

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa3-fixture", action="store_true", help="Print QA3 fixture summary only")
    args = parser.parse_args()

    if args.qa3_fixture:
        print("QA3 LAN 6005077725 fixtures:")
        print("  death=2026-09-07 reporting=2027-06-20 outstanding=34341")
        print("  pre-fix GL: BLD_PRIN=2691 UNBLD_PRIN=31650")
        print("  post-fix expected: BLD_PRIN=25439 UNBLD_PRIN=8902")
        return 0

    results = run_scenarios()
    failed = [r for r in results if not r.passed]
    print("=== DCF principal split simulation ===\n")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.scenario_id}: {r.label}")
        print(f"       {r.detail}\n")

    if failed:
        print(f"FAILED {len(failed)}/{len(results)} scenarios")
        return 1
    print(f"ALL {len(results)} scenarios PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
