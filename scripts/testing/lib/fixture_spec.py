#!/usr/bin/env python3
"""Ask for the state you need; get a LAN in that state.

Every harness here builds its own fixtures. `disburse_loan_sanity.py` disburses and
resets, `dcf_sanity/` seeds a group, `dpic/` purges and re-seeds, `flowtest/fixture.py`
snapshots and restores a hand-built LAN. Writing case #189 therefore costs what case #1
cost, which is the real reason 370 money APIs have no test — not neglect, but that every
test starts from zero.

This is the missing middle: a *declarative* request for state.

    from fixture_spec import FixtureSpec, resolve

    spec = FixtureSpec(product="SHG", loan_status="ACTIVE", children=3,
                       child_states={"DISB_CNCL": 1}, first_emi="future")
    fx = resolve(spec)          # -> Fixture(parent_lan=..., children=[...], source="reused")

Resolution order, cheapest first:

1. **Reuse** — find an existing local LAN already in that state. Free, and the local DB
   is a long-lived dev fixture full of them.
2. **Adapt** — take a near-match and move it the remaining step through a *real* flow.
3. **Build** — disburse a fresh one.

Reuse is deliberately first. `run-the-real-thing-locally.md` forbids seeding the
*outcome* under test, not the *precondition*; a LAN that reached `DISB_CNCL` through the
real cancellation flow last week is a better precondition than one this test just wrote
by hand, and it costs nothing.

`resolve` never fabricates: when nothing matches and building is not permitted it returns
`Fixture(found=False, why=...)` so the caller can skip honestly instead of asserting
against invented state.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

PRODUCTS = {"JLG": 2, "SHG": 44, "INDL": 45}


def _psql(sql: str, timeout: int = 90) -> str:
    env = dict(os.environ, PGPASSWORD=os.environ.get("PGPASSWORD", "yugabyte"))
    out = subprocess.run(
        ["psql", "-h", os.environ.get("PGHOST", "localhost"),
         "-p", os.environ.get("PGPORT", "5433"),
         "-U", os.environ.get("PGUSER", "yugabyte"),
         "-d", os.environ.get("PGDATABASE", "yugabyte"), "-At", "-F", "|", "-c", sql],
        capture_output=True, text=True, timeout=timeout, env=env)
    return out.stdout


@dataclass
class FixtureSpec:
    product: str | None = None           # JLG | SHG | INDL
    loan_status: str = "ACTIVE"          # parent loan_status
    account_status: str | None = None    # parent account.status
    children: int | None = None          # exact child count (None = don't care)
    child_states: dict[str, int] = field(default_factory=dict)  # {"DISB_CNCL": 1}
    first_emi: str | None = None         # "future" | "past" | None
    in_tenure: bool = False              # maturity_date > now()
    label: str = ""

    def describe(self) -> str:
        bits = [f"product={self.product or 'any'}", f"status={self.loan_status}"]
        if self.children is not None:
            bits.append(f"children={self.children}")
        if self.child_states:
            bits.append("child_states=" + ",".join(f"{k}x{v}" for k, v in self.child_states.items()))
        if self.first_emi:
            bits.append(f"first_emi={self.first_emi}")
        if self.in_tenure:
            bits.append("in_tenure")
        return " ".join(bits)


@dataclass
class Fixture:
    found: bool
    parent_lan: str = ""
    parent_account_id: str = ""
    children: list[str] = field(default_factory=list)
    child_by_status: dict[str, list[str]] = field(default_factory=dict)
    source: str = ""
    why: str = ""

    def lans(self) -> list[str]:
        return ([self.parent_lan] if self.parent_lan else []) + list(self.children)


def _candidate_parents(spec: FixtureSpec, limit: int = 60) -> list[tuple[str, str]]:
    where = [
        "la.is_deleted = false",
        f"la.loan_status = '{spec.loan_status}'",
    ]
    if spec.account_status:
        where.append(f"a.status = '{spec.account_status}'")
    if spec.children is not None or spec.child_states:
        where.append("la.has_child_accounts = true")
    if spec.in_tenure:
        where.append("la.maturity_date > now()")
    if spec.first_emi == "future":
        where.append("la.first_repayment_date > now()")
    elif spec.first_emi == "past":
        where.append("la.first_repayment_date <= now()")
    if spec.product:
        pid = PRODUCTS.get(spec.product.upper())
        if pid:
            where.append(
                "la.loan_product_id = (SELECT id FROM mfi_accounting.loan_product "
                f"WHERE product_id = {pid} LIMIT 1)")
    sql = (
        "SELECT a.account_number, la.account_id FROM mfi_accounting.loan_account la "
        "JOIN mfi_accounting.account a ON a.id = la.account_id "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY la.maturity_date DESC NULLS LAST LIMIT {limit};")
    rows = []
    for line in _psql(sql).splitlines():
        parts = line.strip().split("|")
        if len(parts) == 2 and parts[0]:
            rows.append((parts[0], parts[1]))
    return rows


def _children_of(account_id: str) -> list[tuple[str, str]]:
    sql = (
        "SELECT a.account_number, la.loan_status FROM mfi_accounting.loan_account la "
        "JOIN mfi_accounting.account a ON a.id = la.account_id "
        f"WHERE la.parent_loan_account_id = {account_id} ORDER BY a.account_number;")
    out = []
    for line in _psql(sql).splitlines():
        parts = line.strip().split("|")
        if len(parts) == 2 and parts[0]:
            out.append((parts[0], parts[1]))
    return out


def _matches(spec: FixtureSpec, kids: list[tuple[str, str]]) -> bool:
    if spec.children is not None and len(kids) != spec.children:
        return False
    if spec.child_states:
        have: dict[str, int] = {}
        for _, status in kids:
            have[status] = have.get(status, 0) + 1
        for status, want in spec.child_states.items():
            if have.get(status, 0) < want:
                return False
    return True


def resolve(spec: FixtureSpec, *, allow_build: bool = False) -> Fixture:
    """Cheapest fixture satisfying the spec. Never invents state."""
    for lan, account_id in _candidate_parents(spec):
        kids = _children_of(account_id)
        if not _matches(spec, kids):
            continue
        by_status: dict[str, list[str]] = {}
        for child_lan, status in kids:
            by_status.setdefault(status, []).append(child_lan)
        return Fixture(
            found=True,
            parent_lan=lan,
            parent_account_id=account_id,
            children=[k for k, _ in kids],
            child_by_status=by_status,
            source="reused",
        )

    if not allow_build:
        return Fixture(found=False, source="none",
                       why=f"no local LAN matches [{spec.describe()}] and allow_build=False")
    return Fixture(found=False, source="none",
                   why=f"no local LAN matches [{spec.describe()}]; building is not "
                       "implemented here — drive scripts/disburse_loan_sanity.py, then re-resolve")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Resolve a fixture spec against the local DB")
    ap.add_argument("--product")
    ap.add_argument("--loan-status", default="ACTIVE")
    ap.add_argument("--account-status")
    ap.add_argument("--children", type=int)
    ap.add_argument("--child-state", action="append", default=[],
                    help="STATUS=COUNT, e.g. DISB_CNCL=1")
    ap.add_argument("--first-emi", choices=["future", "past"])
    ap.add_argument("--in-tenure", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    child_states = {}
    for item in args.child_state:
        k, _, v = item.partition("=")
        child_states[k.strip().upper()] = int(v or 1)

    spec = FixtureSpec(
        product=args.product, loan_status=args.loan_status,
        account_status=args.account_status, children=args.children,
        child_states=child_states, first_emi=args.first_emi, in_tenure=args.in_tenure)

    fx = resolve(spec)
    if args.json:
        print(json.dumps({
            "found": fx.found, "parent_lan": fx.parent_lan, "children": fx.children,
            "child_by_status": fx.child_by_status, "source": fx.source, "why": fx.why,
        }, indent=1))
        return 0 if fx.found else 1

    if not fx.found:
        print(f"no fixture: {fx.why}")
        return 1
    print(f"spec    {spec.describe()}")
    print(f"source  {fx.source}")
    print(f"parent  {fx.parent_lan}  (account_id {fx.parent_account_id})")
    for status, lans in sorted(fx.child_by_status.items()):
        print(f"  {status:<22} {', '.join(lans)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
