#!/usr/bin/env python3
"""Money ship behavior-parity + column-audit gate (production-grade local bar).

Standing (2026-07-31): amount-only / sum-only PASS is forbidden when a change replaces
an existing write path (e.g. SHG INT distribute vs independent child calc). Calendar,
state, and FK columns that the old path wrote must still be asserted fail-closed.

Fail closed on money/service pending when:
  1) impacted money domain lacks value-level db_asserts (acceptance_coverage),
  2) group/SHG INT paths lack tip/calendar column audit checked_by,
  3) registry acceptance allows WARN-only for money calendar defects (anti-pattern).

Env: MONEY_BEHAVIOR_PARITY_GATE=0 to disable (escape only).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PENDING = ROOT / ".cursor" / ".pending-ship-work.json"
REGISTRY = ROOT / "scripts" / "testing" / "registry.json"

# Paths / apis that imply SHG parent→child INT Accrued distribute behavior
_SHG_INT_MARKERS = (
    "InterestGroupLoanAccrualDistribution",
    "interestaccrualcalculation",
    "interestAccrualCalculation",
    "shg_int_accrual",
    "grouploan/interest",
)

_WARN_AS_PASS_ANTIPATTERNS = (
    "warn-and-pass",
    "warn only",
    "tip lag warn",
    "calendar lag warn",
    "amount-only",
    "sum-only parity",
    "presence-only",
)


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _pending_implies_shg_int(pending: dict) -> bool:
    blob = " ".join(
        str(x) for x in (pending.get("files") or []) + (pending.get("apis") or []) + (pending.get("ntest_cases") or [])
    ).lower()
    return any(m.lower() in blob for m in _SHG_INT_MARKERS)


def _case_has_iad_column_audit(case: dict) -> bool:
    acc = case.get("acceptance") or {}
    for a in acc.get("db_asserts") or []:
        if not isinstance(a, dict):
            continue
        checked = str(a.get("checked_by") or "").lower()
        assert_txt = str(a.get("assert") or "").lower()
        cols = a.get("columns") or []
        if "iad_column_audit" in checked or "column audit" in assert_txt:
            return True
        if "interest_accrual_details" == str(a.get("table") or "") and (
            "end_date" in assert_txt or "end_date" in [str(c).lower() for c in cols]
        ):
            return True
    return False


def check(pending: dict | None = None, reg: dict | None = None) -> list[str]:
    if os.environ.get("MONEY_BEHAVIOR_PARITY_GATE", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return []
    pending = pending if pending is not None else _load(PENDING)
    if not pending.get("files") and not pending.get("apis"):
        return []
    tier = (pending.get("tier") or "workspace").lower()
    if tier not in ("money", "service"):
        return []

    reg = reg if reg is not None else _load(REGISTRY)
    errors: list[str] = []

    # SHG INT distribute / accrual calc: require column audit on stitch (or dedicated case)
    if _pending_implies_shg_int(pending):
        stitch = reg.get("flowtest.shg_int_accrual_stitch") or {}
        if not _case_has_iad_column_audit(stitch):
            errors.append(
                "SHG/INT money path: flowtest.shg_int_accrual_stitch must declare "
                "interest_accrual_details column audit (end_date/tip + accrued) via "
                "iad_column_audit — amount-only window parity is not enough"
            )
        note_blob = " ".join(
            str(x).lower()
            for x in (
                (stitch.get("acceptance") or {}).get("note"),
                stitch.get("note"),
                *(
                    (a.get("assert") or "")
                    for a in ((stitch.get("acceptance") or {}).get("db_asserts") or [])
                    if isinstance(a, dict)
                ),
            )
            if x
        )
        for pat in _WARN_AS_PASS_ANTIPATTERNS:
            if pat in note_blob and "fail-closed" not in note_blob:
                if "tip" in note_blob or "calendar" in note_blob or "amount-only" in note_blob:
                    errors.append(
                        f"SHG/INT acceptance allows '{pat}' — money calendar/column defects "
                        "must FAIL closed (independent-calc behavior parity)"
                    )
                    break

        disc = _load(ROOT / ".cursor" / ".ship-discipline.json")
        if disc and (disc.get("tier") or "").lower() == "money":
            impact = " ".join(
                str(disc.get(k) or "")
                for k in (
                    "minimal_fix",
                    "layers_dropped",
                    "fix_plan",
                )
            ).lower()
            fp = disc.get("fix_plan") if isinstance(disc.get("fix_plan"), dict) else {}
            impact += " " + " ".join(str(v).lower() for v in (fp or {}).values())
            ia = disc.get("impact_analysis") if isinstance(disc.get("impact_analysis"), dict) else {}
            impact += " " + " ".join(str(v).lower() for v in (ia or {}).values())
            if not any(
                k in impact
                for k in (
                    "tip",
                    "end_date",
                    "calendar",
                    "behavior parity",
                    "independent",
                    "createorupdate",
                    "asof",
                )
            ):
                errors.append(
                    "ship-discipline impact/fix_plan missing tip/end_date/calendar/"
                    "independent-calc behavior parity — do not ship amount-only distribute"
                )

    return errors


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-pending", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    errs = check()
    if args.json:
        print(json.dumps({"ok": not errs, "errors": errs}, indent=2))
    else:
        if errs:
            print("money-behavior-parity-gate FAIL:")
            for e in errs:
                print(f"  - {e}")
        else:
            print("money-behavior-parity-gate PASS")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
