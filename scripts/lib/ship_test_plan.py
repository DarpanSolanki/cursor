#!/usr/bin/env python3
"""Automated ship test planning — what to run, when (impact → deep → release).

No manual verify-dpi / full regression by default on every edit.
Phases run automatically from ship-loop-gate + workspace-close + ship-test-auto.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from infer_ship_apis import (  # noqa: E402
    _focus_apis_for_paths,
    build_impact,
    load_registry,
    resolve_apis_smart,
)
from resolve_ship_cases import (  # noqa: E402
    path_blob,
    resolve_ship_cases,
    touches_dpi_blob,
)

PENDING = ROOT / ".cursor/.pending-ship-work.json"


def _paths_from_pending(root: Path) -> tuple[list[str], list[str], str]:
    if not PENDING.is_file():
        return [], [], "workspace"
    try:
        data = json.loads(PENDING.read_text(encoding="utf-8"))
    except Exception:
        return [], [], "workspace"
    files = data.get("files") or []
    paths = [str(root / f) if not str(f).startswith("/") else str(f) for f in files]
    apis = list(data.get("apis") or [])
    tier = data.get("tier") or "workspace"
    if paths and not apis:
        apis = build_impact(paths).get("apis") or []
    return paths, apis, tier


def _dedupe(seq: list[str]) -> list[str]:
    out: list[str] = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def _disburse_touch(blob: str) -> bool:
    return any(h in blob for h in ("disburse", "disbursement", "neft", "dtfc", "clmt"))


def _foreclosure_write_touch(blob: str) -> bool:
    return any(
        h in blob
        for h in (
            "individualchildloanforeclosure",
            "childloanforeclosureprocessor",
            "loanforeclosureprocessor",
        )
    )


def _death_touch(blob: str) -> bool:
    return any(h in blob for h in ("deathforeclosure", "death_foreclosure", "dcf_", "/death/"))


def case_env(case_id: str, reg: dict) -> dict[str, str]:
    """Extra env for registry cmd cases (release profiles)."""
    meta = reg.get(case_id) or {}
    env = dict(meta.get("env") or {})
    if case_id == "dpic.ud_compliance":
        env.setdefault("DPI_UD_PROFILE", "grace,multi,go-live")
        env.setdefault("DPI_UD_CERTIFY", "0")
        if "certify" in path_blob([]):  # noqa: intentional no-op
            pass
    return env


def build_test_plan(
    paths: list[str],
    apis: list[str],
    tier: str,
    reg: dict | None = None,
) -> dict[str, Any]:
    reg = reg if reg is not None else load_registry()
    apis = _focus_apis_for_paths(paths, apis) if paths else list(apis)
    api_set = set(apis)
    blob = path_blob(paths)

    impact = resolve_ship_cases(paths, apis, tier, reg, focus_apis=_focus_apis_for_paths)
    deep: list[str] = []
    release: list[str] = []

    if tier != "money":
        return {
            "tier": tier,
            "apis": apis,
            "impact": impact,
            "deep": deep,
            "release": release,
            "all_automated": _dedupe(impact),
        }

    # --- Deep (auto after impact PASS — broader slice, still path-aware) ---
    if touches_dpi_blob(blob, api_set):
        for cid in ("dpic.grace_e2e", "dpic.multi_emi_installment_e2e", "dpic.go_live_ud"):
            if cid not in impact and cid in reg:
                if cid == "dpic.grace_e2e" and any(
                    k in blob for k in ("grace", "computoverduedate", "dpicalculation")
                ):
                    deep.append(cid)
                elif cid == "dpic.multi_emi_installment_e2e" and any(
                    k in blob for k in ("installment", "multi_emi", "latestunpaid")
                ):
                    deep.append(cid)
                elif cid == "dpic.go_live_ud" and any(
                    k in blob for k in ("golive", "maturity", "posting", "dpiaccrualcalculation")
                ):
                    deep.append(cid)

    if _death_touch(blob):
        cid = "foreclosure.dpi_waiver_smoke"
        if cid not in impact and cid in reg:
            deep.append(cid)

    if _foreclosure_write_touch(blob):
        cid = "foreclosure.individual_child"
        if cid not in impact and cid in reg:
            deep.append(cid)

    # --- Release (auto at money-tier workspace-close / push gate) ---
    if touches_dpi_blob(blob, api_set):
        release.append("dpic.ud_compliance")
        if "certify" in blob or "certified_fixtures" in blob:
            if "dpic.certify_scenarios" in reg:
                release.append("dpic.certify_scenarios")

    if _disburse_touch(blob) and "disbursement.quick" not in impact:
        release.append("disbursement.quick")

    if _foreclosure_write_touch(blob) and "foreclosure.individual_child" not in impact + deep:
        release.append("foreclosure.individual_child")

    impact_set = set(impact)
    deep = [c for c in _dedupe(deep) if c not in impact_set]
    release = [c for c in _dedupe(release) if c not in impact_set and c not in set(deep)]

    return {
        "tier": tier,
        "apis": apis,
        "impact": impact,
        "deep": deep,
        "release": release,
        "all_automated": _dedupe(impact + deep + release),
    }


def run_phase(
    plan: dict[str, Any],
    phase: str,
    *,
    root: Path,
    quiet: bool = False,
) -> dict[str, Any]:
    reg = load_registry()
    cases = list(plan.get(phase) or [])
    results: list[dict[str, Any]] = []
    for cid in cases:
        meta = reg.get(cid) or {}
        env = case_env(cid, reg)
        if cid == "dpic.ud_compliance" and phase == "release":
            env["DPI_UD_PROFILE"] = "grace,multi,go-live"
            env["DPI_UD_CERTIFY"] = "1" if "dpic.certify_scenarios" in plan.get("release", []) else "0"
        env_exports = " ".join(f'{k}="{v}"' for k, v in env.items())
        cmd = f"{env_exports} bash scripts/bin/ntest.sh run {cid}".strip()
        if not quiet:
            print(f"→ [{phase}] {cmd}", flush=True)
        p = subprocess.run(cmd, shell=True, cwd=str(root), capture_output=True, text=True)
        ok = p.returncode == 0
        results.append({"case": cid, "phase": phase, "ok": ok, "rc": p.returncode})
        if not quiet and p.stdout:
            print(p.stdout[-1200:])
        if not ok:
            if not quiet and p.stderr:
                print(p.stderr[-800:], file=sys.stderr)
            return {"phase": phase, "ok": False, "results": results}
    return {"phase": phase, "ok": True, "results": results}


def main() -> int:
    ap = argparse.ArgumentParser(description="Automated ship test plan")
    ap.add_argument("--from-pending", action="store_true")
    ap.add_argument("--path", action="append", default=[])
    ap.add_argument("--phase", choices=("impact", "deep", "release"), default="")
    ap.add_argument("--list", action="store_true", help="Print case ids for --phase")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--run", action="store_true", help="Execute phase(s)")
    ap.add_argument(
        "--phases",
        default="impact,deep",
        help="Comma list when --run (release added by workspace-close)",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    paths = list(args.path)
    apis: list[str] = []
    tier = "workspace"
    if args.from_pending:
        paths, apis, tier = _paths_from_pending(ROOT)
    elif paths:
        apis = resolve_apis_smart(paths)
        tier = build_impact(paths).get("tier") or "workspace"

    plan = build_test_plan(paths, apis, tier)

    if args.json and not args.run:
        print(json.dumps(plan, indent=2))
        return 0

    if args.list and args.phase:
        for cid in plan.get(args.phase) or []:
            print(cid)
        return 0

    if args.run:
        phases = [p.strip() for p in args.phases.split(",") if p.strip()]
        for ph in phases:
            out = run_phase(plan, ph, root=ROOT, quiet=args.quiet)
            if not out.get("ok"):
                return 1
        if args.json:
            print(json.dumps({"ok": True, "plan": plan, "phases": phases}, indent=2))
        return 0

    if args.phase:
        for cid in plan.get(args.phase) or []:
            print(cid)
        return 0

    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(f"tier={plan['tier']} impact={plan['impact']} deep={plan['deep']} release={plan['release']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
