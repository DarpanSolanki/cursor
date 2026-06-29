#!/usr/bin/env python3
"""Single-call ship impact resolution for ship-loop-gate (tier, apis, ntest cases)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from infer_ship_apis import (  # noqa: E402
    build_impact,
    filter_dpi_batch_cases,
    git_dirty_repos,
    git_diff_paths,
    ntest_cases_for_impact,
    resolve_apis_smart,
    strip_money_cases_for_workspace,
)


def resolve(
    root: Path,
    pending_path: Path | None,
    cli_tier: str,
    cli_apis: list[str],
    from_pending: bool,
) -> dict:
    pending: dict = {}
    if pending_path and pending_path.is_file():
        try:
            pending = json.loads(pending_path.read_text(encoding="utf-8"))
        except Exception:
            pending = {}

    paths = [
        str(root / f)
        for f in pending.get("files") or []
        if f and not f.startswith(".cursor/") and not f.startswith("scripts/scratch/")
    ]
    apis = list(dict.fromkeys(cli_apis or (pending.get("apis") or [])))
    explicit_cases = pending.get("registry_cases") or pending.get("ntest_cases") or []

    if paths and not explicit_cases:
        impact = build_impact(paths)
        tier = impact["tier"]
        apis = list(dict.fromkeys(apis + (impact.get("apis") or []))) if not cli_apis else apis
        cases = strip_money_cases_for_workspace(
            filter_dpi_batch_cases(impact.get("ntest_cases") or [], apis, paths, tier), tier
        )
        repos = impact.get("repos") or []
        dpi_scoped = bool(impact.get("dpi_scoped"))
        impact_scoped = bool(impact.get("impact_scoped"))
        accounting_scoped = bool(impact.get("accounting_scoped"))
    elif paths:
        impact = build_impact(paths)
        tier = impact["tier"]
        dpi_scoped = bool(impact.get("dpi_scoped"))
        impact_scoped = bool(impact.get("impact_scoped"))
        accounting_scoped = bool(impact.get("accounting_scoped"))
        if cli_apis:
            apis = list(dict.fromkeys(cli_apis))
            cases = strip_money_cases_for_workspace(
                filter_dpi_batch_cases(ntest_cases_for_impact(paths, apis, tier), apis, paths, tier),
                tier,
            )
        else:
            if not apis:
                apis = list(impact.get("apis") or [])
            # Honor explicit registry_cases from pending — do not expand via resolve_ship_cases.
            cases = strip_money_cases_for_workspace(list(explicit_cases), tier)
        repos = impact.get("repos") or pending.get("repos") or []
    else:
        tier = pending.get("tier") or cli_tier or "workspace"
        cases = ntest_cases_for_impact(paths, apis, tier)
        repos = pending.get("repos") or []
        dpi_scoped = False
        impact_scoped = False
        accounting_scoped = False

    if not apis and not from_pending:
        for repo in git_dirty_repos():
            for p in git_diff_paths(repo):
                api_paths = [str(root / repo / p)]
                apis.extend(resolve_apis_smart(api_paths))
        apis = list(dict.fromkeys(apis))
        if apis and not cases:
            cases = ntest_cases_for_impact(paths, apis, tier)

    if not tier and paths:
        impact = build_impact(paths)
        tier = impact["tier"]
        dpi_scoped = bool(impact.get("dpi_scoped"))
        impact_scoped = bool(impact.get("impact_scoped"))
        accounting_scoped = bool(impact.get("accounting_scoped"))
    tier = tier or cli_tier or "workspace"

    cases = strip_money_cases_for_workspace(cases, tier)

    testing_paths = any(
        "registry.json" in f or (f.startswith("scripts/testing/") and f.endswith((".py", ".json", ".sh")))
        for f in pending.get("files") or []
    )

    return {
        "tier": tier,
        "apis": apis,
        "ntest_cases": cases,
        "repos": repos,
        "pending_files": len(pending.get("files") or []),
        "testing_paths_touched": testing_paths,
        "dpi_scoped": dpi_scoped,
        "impact_scoped": impact_scoped,
        "accounting_scoped": accounting_scoped,
        "test_plan": _test_plan_summary(paths, apis, tier),
    }


def _test_plan_summary(paths: list[str], apis: list[str], tier: str) -> dict:
    try:
        from ship_test_plan import build_test_plan

        reg_path = ROOT / "scripts/testing/registry.json"
        reg = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.is_file() else {}
        plan = build_test_plan(paths, apis, tier, reg)
        return {
            "impact": plan.get("impact") or [],
            "deep": plan.get("deep") or [],
            "release": plan.get("release") or [],
        }
    except Exception:
        return {"impact": [], "deep": [], "release": []}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--pending", default=str(ROOT / ".cursor/.pending-ship-work.json"))
    ap.add_argument("--tier", default="")
    ap.add_argument("--api", action="append", default=[])
    ap.add_argument("--from-pending", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()
    out = resolve(
        Path(args.root),
        Path(args.pending) if args.pending else None,
        args.tier,
        args.api,
        args.from_pending,
    )
    if args.as_json:
        print(json.dumps(out, indent=2))
    else:
        print(out["tier"])
        for a in out["apis"]:
            print(f"API:{a}")
        for c in out["ntest_cases"]:
            print(f"CASE:{c}")
        for r in out["repos"]:
            print(f"REPO:{r}")
        print(f"FILES:{out['pending_files']}")
        print(f"TESTING_PATHS:{1 if out['testing_paths_touched'] else 0}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
