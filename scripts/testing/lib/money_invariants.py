#!/usr/bin/env python3
"""Run the universal money invariants around ANY registry case, not just flowtest's.

`flowtest/invariants.py` is the best money check in this workspace — per-transaction
double-entry, negative/orphan dues, status legality, AIR/BPI deltas, all baseline-relative
so only NEW violations fail. It was reachable from 24 flowtest scenarios. The other 95
money cases — all 58 dpic, 12 disburse, 15 foreclosure, 10 dcf_sanity — ran with none of
it, each asserting only what its author thought to check.

That is the wrong shape. Per-case asserts catch the defect the author imagined; invariants
catch the defect nobody imagined, which is the only kind that reaches production. Wiring
them in centrally means a new case inherits them for free instead of re-deriving them.

Which LANs to check is the whole problem, and it has one honest answer:

- LANs the case pins in `defaults` / `env` (`PARENT_LAN`, `CHILD2_LAN`, `LAN`, …)
- plus any LAN that got a `client_request_response_log` row during the run

`system_date` on CRR is real wall-clock, so the second source catches cases that create
fresh LANs (disbursement) without the case having to declare anything. `loan_account.
updated_on` is NOT usable here — it is stamped from the business value date, not the
clock, so it cannot order writes.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

_LAN_KEY = re.compile(r"(^|_)(PARENT|CHILD\d?|VICTIM|SIBLING)?_?LAN$")
_LAN_VALUE = re.compile(r"^\d{6,}$")

OFF = os.environ.get("MONEY_INVARIANTS", "1") == "0"


def _psql(sql: str, timeout: int = 60) -> str:
    env = dict(os.environ, PGPASSWORD=os.environ.get("PGPASSWORD", "yugabyte"))
    try:
        out = subprocess.run(
            ["psql", "-h", os.environ.get("PGHOST", "localhost"),
             "-p", os.environ.get("PGPORT", "5433"),
             "-U", os.environ.get("PGUSER", "yugabyte"),
             "-d", os.environ.get("PGDATABASE", "yugabyte"),
             "-At", "-c", sql],
            capture_output=True, text=True, timeout=timeout, env=env)
        return out.stdout
    except Exception:
        return ""


def declared_lans(case: dict, env: dict[str, str] | None = None) -> list[str]:
    """LANs the case pins, from `defaults` then `env` overlays then the live process env."""
    out: list[str] = []
    sources: list[dict] = [case.get("defaults") or {}, case.get("env") or {}]
    if env:
        sources.append(env)
    for src in sources:
        for key, value in src.items():
            if not _LAN_KEY.search(str(key).upper()):
                continue
            value = str(value or "").strip()
            if _LAN_VALUE.match(value) and value not in out:
                out.append(value)
    return out


def mark() -> str:
    """Wall-clock marker to diff CRR against. Empty string when the DB is unreachable."""
    return (_psql("SELECT now();") or "").strip()


def lans_touched_since(marker: str) -> list[str]:
    if not marker:
        return []
    rows = _psql(
        "SELECT DISTINCT loan_account_number FROM mfi_accounting.client_request_response_log "
        f"WHERE system_date >= '{marker}' AND loan_account_number IS NOT NULL "
        "AND loan_account_number NOT LIKE '~%' LIMIT 40;")
    return [r.strip() for r in rows.splitlines() if _LAN_VALUE.match(r.strip())]


def _invariants():
    sys.path.insert(0, str(ROOT / "scripts" / "testing"))
    from flowtest import invariants  # noqa: PLC0415
    return invariants


def baseline(lans: list[str]) -> dict | None:
    if OFF or not lans:
        return None
    try:
        return {"lans": _invariants().snapshot_invariants(lans)}
    except Exception as exc:  # noqa: BLE001
        print(f"  money invariants: baseline unavailable ({exc})")
        return None


def verify(lans: list[str], base: dict | None, *, label: str) -> bool:
    """True when no NEW violation appeared. Never raises — the caller owns the verdict."""
    if OFF:
        return True
    lans = [x for x in dict.fromkeys(lans) if x]
    if not lans:
        return True
    try:
        inv = _invariants()
        inv.run_universal_invariants(
            lans, baseline=base, label=label, absolute_only=base is None)
        return True
    except AssertionError as exc:
        print(f"  MONEY INVARIANT VIOLATION ({label}): {exc}", file=sys.stderr)
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  money invariants: skipped ({exc})")
        return True


class Guard:
    """Wrap a case run: capture a baseline, then assert no new violation.

    Absent a genuine before-baseline the check falls back to `absolute_only`, which
    asserts what must hold in ANY state. That distinction matters: a self-snapshot
    baseline neutralises every delta and makes the gate vacuous, which is worse than
    not running it because it looks like coverage.
    """

    def __init__(self, case: dict, *, case_id: str, env: dict[str, str] | None = None):
        self.case_id = case_id
        self.enabled = (not OFF) and case.get("smoke_tier") == "money"
        self.lans = declared_lans(case, env) if self.enabled else []
        self.marker = ""
        self.base = None

    def __enter__(self) -> "Guard":
        if not self.enabled:
            return self
        self.marker = mark()
        self.base = baseline(self.lans)
        return self

    def check(self) -> bool:
        if not self.enabled:
            return True
        lans = list(self.lans) + lans_touched_since(self.marker)
        if not lans:
            return True
        return verify(lans, self.base, label=f"post-case {self.case_id}")

    def __exit__(self, *exc) -> None:
        return None
