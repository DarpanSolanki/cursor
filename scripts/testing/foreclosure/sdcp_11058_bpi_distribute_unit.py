#!/usr/bin/env python3
"""SDCP-11058 — mirror GroupLoanUtility.getDistributedAmountEqually for any N.

Asserts sum(children) == parent for N in {1,2,3,5,7,10,20} (not hardcoded to 2×0.5).
Matches Java: equal split by child count with carry residue on last child.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def distribute_equally(amount: Decimal, n: int) -> list[Decimal]:
    if n < 1:
        raise ValueError("n must be >= 1")
    carry = 0.0
    out: list[Decimal] = []
    for i in range(n):
        is_last = i == n - 1
        output = float(amount) / n
        whole = int(output)
        frac = output - whole
        carry += frac
        dec = Decimal(whole)
        if carry >= 1:
            whole += 1
            carry -= 1
            dec += Decimal(1)
        if is_last:
            whole += int(round(carry))
            dec += Decimal(str(carry)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        out.append(dec)
    return out


def main() -> None:
    cases = [
        (Decimal("79"), (1, 2, 3, 5, 7, 10, 20)),
        (Decimal("78"), (2, 3)),
        (Decimal("1213.36"), (2, 3, 4)),
        (Decimal("100"), (3,)),
        (Decimal("1"), (3,)),
    ]
    for amount, ns in cases:
        for n in ns:
            parts = distribute_equally(amount, n)
            total = sum(parts, Decimal(0))
            if total != amount:
                raise SystemExit(f"FAIL: parent={amount} N={n} parts={parts} sum={total}")
            print(f"OK: parent={amount} N={n} parts={parts} sum={total}")
    # Explicit N=3 regression (user constraint — not only 2×0.5)
    parts3 = distribute_equally(Decimal("79"), 3)
    assert len(parts3) == 3 and sum(parts3) == Decimal("79")
    print("OK: N=3 parent BPI 79 →", parts3)
    print("PASS: sdcp_11058_bpi_distribute_unit")


if __name__ == "__main__":
    main()
