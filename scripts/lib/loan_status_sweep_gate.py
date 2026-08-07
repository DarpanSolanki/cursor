#!/usr/bin/env python3
"""Multi-account loan_status sweeps must not stamp over another workflow's state.

TDPQA-72: `UpdateLoanStatusForSHGProcessor` selected every child of a parent and wrote
`loan_status` unconditionally. INITIATE used `findAllByParentAccountId` (no filter);
FINAL used `findAllByParentAccountNonClosed` (`!= 'CLOSED'` only) and wrote a hardcoded
`ACTIVE`. `DISB_CNCL` is not `CLOSED`, so a disbursement-cancelled child came back to
life whenever a parent foreclosure ran on that group.

That is a *class*, not one bug. Six services in accounting select many loan accounts and
stamp `loan_status`, and they disagree about what they are allowed to overwrite:

- **terminal guard** — skips CLOSED / DISB_CNCL. Safe.
- **account-status only** — filters `account.status == ACTIVE`. Protects loans that are
  terminal at the *account* level, but NOT one frozen by a different workflow
  (`DISB_CNCL_FREEZE`, `PART_PREPAYMENT_FREEZE`, `LOAN_RESTR_FREEZE`), whose account is
  still ACTIVE. A foreclosure expiry can still clear a cancellation freeze.
- **unguarded** — writes to whatever the finder returned.

This gate does not decide which is correct: for some sweeps, overwriting a freeze is the
intent. It makes the choice **visible and deliberate**, and ratchets so the unguarded set
can only shrink.

  loan_status_sweep_gate.py            report; exit 1 if the unguarded set grew
  loan_status_sweep_gate.py --json
  loan_status_sweep_gate.py --accept   record the current set as the baseline
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "trustt-platform-accounting/src/main/java"
BASELINE = ROOT / "cursor-bundle/flow-test/loan_status_sweep_baseline.json"

_SWEEP_FINDER = re.compile(
    r"findAllByParentAccount\w*|findAllChildAccountsByParentAccountId"
    r"|findAllLoanAccountDetailsByIds")
_SETS_STATUS = re.compile(r"\.setLoanStatus\s*\(")
_TERMINAL_GUARD = re.compile(
    r"LoanStatus\.DISB_CNCL\b|LoanStatus\.CLOSED\b|TERMINAL_STATUSES|isInactive\s*\(")
_ACCOUNT_STATUS_FILTER = re.compile(
    r"getStatus\(\)\s*\.compareTo\s*\(\s*AccountEntity\.AccountStatus\.ACTIVE"
    r"|getStatus\(\)\s*==\s*AccountEntity\.AccountStatus\.ACTIVE")


def classify() -> list[dict]:
    out: list[dict] = []
    if not SRC.is_dir():
        return out
    for path in SRC.rglob("*.java"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not (_SETS_STATUS.search(text) and _SWEEP_FINDER.search(text)):
            continue
        if _TERMINAL_GUARD.search(text):
            level = "terminal_guard"
        elif _ACCOUNT_STATUS_FILTER.search(text):
            level = "account_status_only"
        else:
            level = "unguarded"
        out.append({
            "file": str(path.relative_to(ROOT)),
            "class": path.stem,
            "guard": level,
        })
    return sorted(out, key=lambda r: r["class"])


def load_baseline() -> dict:
    if BASELINE.is_file():
        try:
            return json.loads(BASELINE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--accept", action="store_true")
    args = ap.parse_args()

    rows = classify()
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0

    if not rows:
        print("loan_status sweep gate: no multi-account sweeps found "
              "(accounting checkout missing?)")
        return 0

    unguarded = sorted(r["class"] for r in rows if r["guard"] == "unguarded")
    weak = sorted(r["class"] for r in rows if r["guard"] == "account_status_only")
    safe = sorted(r["class"] for r in rows if r["guard"] == "terminal_guard")

    if args.accept:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps({"unguarded": unguarded, "account_status_only": weak}, indent=1) + "\n",
            encoding="utf-8")
        print(f"baseline recorded: {len(unguarded)} unguarded, {len(weak)} account-status-only")
        return 0

    print(f"loan_status sweep gate: {len(rows)} multi-account sweep(s)")
    if safe:
        print(f"  terminal guard      ({len(safe)}): {', '.join(safe)}")
    if weak:
        print(f"  account-status only ({len(weak)}): {', '.join(weak)}")
        print("      protects CANCELLED/CLOSED accounts, NOT a loan frozen by another")
        print("      workflow (DISB_CNCL_FREEZE, PART_PREPAYMENT_FREEZE, LOAN_RESTR_FREEZE)")
    if unguarded:
        print(f"  UNGUARDED           ({len(unguarded)}): {', '.join(unguarded)}")

    base = load_baseline()
    if not base:
        print("\n  no baseline yet — run with --accept to record the current set")
        return 0

    grew_unguarded = sorted(set(unguarded) - set(base.get("unguarded") or []))
    grew_weak = sorted(set(weak) - set(base.get("account_status_only") or []))
    if grew_unguarded or grew_weak:
        print("\n  FAIL — new unguarded sweep(s) since baseline:")
        for c in grew_unguarded + grew_weak:
            print(f"    {c}")
        print("  Add a terminal-status guard, or accept deliberately with --accept.")
        return 1

    shrank = sorted((set(base.get("unguarded") or []) | set(base.get("account_status_only") or []))
                    - set(unguarded) - set(weak))
    if shrank:
        print(f"\n  improved: {', '.join(shrank)} now guarded — re-run --accept to lower the bar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
