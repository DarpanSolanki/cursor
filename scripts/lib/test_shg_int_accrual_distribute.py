#!/usr/bin/env python3
"""Multi-window SHG INT distribute math — mirrors GroupLoanUtility carry-over + renormalize.

Run: python3 scripts/lib/test_shg_int_accrual_distribute.py
"""
from __future__ import annotations

import sys
from decimal import Decimal, ROUND_HALF_UP


def renormalize(fractions: list[float]) -> list[float]:
    s = sum(fractions)
    if s <= 0:
        return [1.0 / len(fractions)] * len(fractions)
    return [f / s for f in fractions]


def carry_over_distribute(amount: Decimal, fractions: list[float]) -> list[Decimal]:
    """Port of GroupLoanUtility.getFinalAmountListUsingCarryOver (whole-rupee + last absorb)."""
    fracs = renormalize(fractions)
    carry = 0.0
    values: list[Decimal] = []
    for i, frac in enumerate(fracs):
        last = i == len(fracs) - 1
        output = float(amount) * frac
        whole = int(output)
        decimal_frac = output - whole
        carry += decimal_frac
        decimal_value = Decimal(whole)
        if carry >= 1:
            whole += 1
            carry -= 1
            decimal_value += Decimal(1)
        if last:
            whole += int(round(carry))
            decimal_value += Decimal(str(carry)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        values.append(decimal_value)
    total = sum(values)
    if total != amount:
        # Match Java: throw if sum != amount — surface as assert in tests
        raise AssertionError(f"sum(children)={total} != parent={amount}")
    return values


def main() -> int:
    fails = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        mark = "PASS" if ok else "FAIL"
        print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            fails += 1

    # Window total ₹502 / 10 kids — every child ≥ 1 (not daily-delta zeros)
    shares = carry_over_distribute(Decimal("502"), [0.1] * 10)
    check("window_502_sum", sum(shares) == Decimal("502"), str(sum(shares)))
    check("window_502_all_positive", all(s >= 1 for s in shares), str(shares))

    # Mid-cycle style 2133/2134 parity grain
    shares = carry_over_distribute(Decimal("2134"), [0.5, 0.5])
    check("two_child_2134", shares == [Decimal("1067"), Decimal("1067")], str(shares))

    # Renormalize after one closed (remaining 0.5 → 1.0)
    fr = renormalize([0.5])
    check("renorm_single", abs(fr[0] - 1.0) < 1e-9, str(fr))

    # Unequal 3 children
    shares = carry_over_distribute(Decimal("1000"), [0.4, 0.35, 0.25])
    check("three_child_1000_sum", sum(shares) == Decimal("1000"), str(shares))
    check("three_child_all_pos", all(s > 0 for s in shares), str(shares))

    # Multi-window simulation: day1=50, day15=500, day_due=1200 — SET each day
    windows = [Decimal("50"), Decimal("500"), Decimal("1200")]
    for w in windows:
        s = carry_over_distribute(w, [0.1] * 10)
        check(f"window_{w}_sum", sum(s) == w, str(sum(s)))
        check(f"window_{w}_all_ge1", all(x >= 1 for x in s) or w < 10, str(s[:3]))

    # Daily delta anti-pattern: ₹2 among 10 — sum OK but many zeros (document why we avoid)
    tiny = carry_over_distribute(Decimal("2"), [0.1] * 10)
    zeros = sum(1 for x in tiny if x == 0)
    check("tiny_delta_has_zeros_expected", zeros >= 5, f"zeros={zeros} shares={tiny}")
    check("tiny_delta_sum_still_2", sum(tiny) == Decimal("2"), str(sum(tiny)))

    print(f"=== {'PASS' if fails == 0 else 'FAIL'} ({fails} fail) ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
