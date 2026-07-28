#!/usr/bin/env python3
"""Single-call ship impact resolution for ship-loop-gate (tier, apis, ntest cases)."""
from __future__ import annotations

import argparse
import json
import os
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
from ship_fingerprint import repo_head_shas  # noqa: E402


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
    honor_explicit = os.environ.get("SHIP_HONOR_EXPLICIT_CASES", "") == "1"
    explicit_cases = pending.get("registry_cases") or pending.get("ntest_cases") or []

    dpi_scoped = False
    impact_scoped = False
    accounting_scoped = False
    repos: list[str] = list(pending.get("repos") or [])
    apis = list(dict.fromkeys(cli_apis or []))
    cases: list[str] = []
    tier = cli_tier or pending.get("tier") or "workspace"

    if paths:
        impact = build_impact(paths)
        tier = impact["tier"] or tier
        dpi_scoped = bool(impact.get("dpi_scoped"))
        impact_scoped = bool(impact.get("impact_scoped"))
        accounting_scoped = bool(impact.get("accounting_scoped"))
        repos = impact.get("repos") or repos
        if not cli_apis:
            # Fresh path→api resolution wins over stale pending apis
            apis = list(impact.get("apis") or [])
        if honor_explicit and explicit_cases and not cli_apis:
            cases = strip_money_cases_for_workspace(list(explicit_cases), tier)
        else:
            cases = strip_money_cases_for_workspace(
                filter_dpi_batch_cases(
                    ntest_cases_for_impact(paths, apis, tier),
                    apis,
                    paths,
                    tier,
                ),
                tier,
            )
        # Persist re-resolved impact so afterFileEdit freeze cannot stick
        if from_pending and pending_path and not honor_explicit:
            pending["tier"] = tier
            pending["apis"] = apis
            pending["repos"] = repos
            pending["registry_cases"] = cases
            pending["ntest_cases"] = cases
            pending["resolution"] = "resolve_ship_impact"
            pending["repo_head_shas"] = repo_head_shas(pending)
            try:
                pending_path.write_text(json.dumps(pending, indent=2) + "\n", encoding="utf-8")
            except OSError:
                pass
    else:
        cases = ntest_cases_for_impact(paths, apis, tier)

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
