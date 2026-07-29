#!/usr/bin/env python3
"""Single-call ship impact resolution for ship-loop-gate (tier, apis, ntest cases).

Selection source of truth: impact_tests.build_plan() ordered_cases.
resolve_ship_cases / ntest_cases_for_impact are FALLBACK only when plan is empty.
"""
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


def _cases_from_impact_tests(
    rel_paths: list[str],
    *,
    tier: str,
    from_pending: bool,
) -> tuple[list[str], dict, str, list[str]]:
    """Return (cases, plan, source_label, why_lines)."""
    from impact_tests import build_plan  # noqa: WPS433

    plan: dict = {}
    try:
        if rel_paths:
            plan = build_plan(from_pending=False, paths=rel_paths, shipped_only=True)
        elif from_pending:
            plan = build_plan(from_pending=True, shipped_only=True)
        ordered = list(plan.get("ordered_cases") or [])
        ordered = strip_money_cases_for_workspace(ordered, tier)
        if ordered:
            why = list(plan.get("why_lines") or []) + list(plan.get("selection_tier_lines") or [])
            return ordered, plan, "impact_tests", why
    except Exception:
        plan = {}
    return [], plan, "", []


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
    # Scope to one service repo when push-origin sets SHIP_CLOSE_REPO (train push).
    # Avoids re-running unrelated money suites accumulated in pending from other work.
    close_repo = (os.environ.get("SHIP_CLOSE_REPO") or "").strip()
    if close_repo:
        scoped = []
        for f in pending.get("files") or []:
            if not f:
                continue
            fl = f.replace("\\", "/")
            if fl == close_repo or fl.startswith(f"{close_repo}/"):
                scoped.append(str(root / f))
            # Keep harness tightly coupled to this ship: by-latest / map for same API only
            elif fl.startswith("scripts/testing/foreclosure/") or fl.startswith(
                "scripts/testing/map_coverage/"
            ):
                scoped.append(str(root / f))
        if scoped:
            paths = scoped
            pending = dict(pending)
            pending["files"] = [
                f for f in (pending.get("files") or [])
                if f
                and (
                    f.replace("\\", "/").startswith(f"{close_repo}/")
                    or f.replace("\\", "/") == close_repo
                    or f.replace("\\", "/").startswith("scripts/testing/foreclosure/")
                    or f.replace("\\", "/").startswith("scripts/testing/map_coverage/")
                )
            ]
            pending["repos"] = [close_repo]
    honor_explicit = os.environ.get("SHIP_HONOR_EXPLICIT_CASES", "") == "1"
    explicit_cases = pending.get("registry_cases") or pending.get("ntest_cases") or []

    dpi_scoped = False
    impact_scoped = False
    accounting_scoped = False
    repos: list[str] = list(pending.get("repos") or [])
    apis = list(dict.fromkeys(cli_apis or []))
    cases: list[str] = []
    tier = cli_tier or pending.get("tier") or "workspace"
    selection_source = "pending"
    why_lines: list[str] = []
    impact_plan: dict = {}

    if paths:
        impact = build_impact(paths)
        tier = impact["tier"] or tier
        dpi_scoped = bool(impact.get("dpi_scoped"))
        impact_scoped = bool(impact.get("impact_scoped"))
        accounting_scoped = bool(impact.get("accounting_scoped"))
        repos = impact.get("repos") or repos
        if not cli_apis:
            apis = list(impact.get("apis") or [])

        rel_paths = [f for f in pending.get("files") or [] if f]
        if honor_explicit and explicit_cases and not cli_apis:
            cases = strip_money_cases_for_workspace(list(explicit_cases), tier)
            selection_source = "explicit_cases"
        else:
            cases, impact_plan, src, why_lines = _cases_from_impact_tests(
                rel_paths, tier=tier, from_pending=from_pending
            )
            if cases:
                selection_source = src
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
                selection_source = "FALLBACK: no selection"
                why_lines = [f"FALLBACK {c}: resolve_ship_cases" for c in cases]

        if from_pending and pending_path and not honor_explicit:
            pending["tier"] = tier
            pending["apis"] = apis
            pending["repos"] = repos
            pending["registry_cases"] = cases
            pending["ntest_cases"] = cases
            pending["resolution"] = selection_source
            pending["selection_source"] = selection_source
            pending["repo_head_shas"] = repo_head_shas(pending)
            try:
                pending_path.write_text(json.dumps(pending, indent=2) + "\n", encoding="utf-8")
            except OSError:
                pass
    else:
        cases, impact_plan, src, why_lines = _cases_from_impact_tests(
            [], tier=tier, from_pending=from_pending
        )
        if cases:
            selection_source = src
        else:
            cases = ntest_cases_for_impact(paths, apis, tier)
            selection_source = "FALLBACK: no selection"

    if not apis and not from_pending:
        for repo in git_dirty_repos():
            for p in git_diff_paths(repo):
                api_paths = [str(root / repo / p)]
                apis.extend(resolve_apis_smart(api_paths))
        apis = list(dict.fromkeys(apis))
        if apis and not cases:
            cases, impact_plan, src, why_lines = _cases_from_impact_tests(
                [str(root / repo / p) for repo in git_dirty_repos() for p in git_diff_paths(repo)],
                tier=tier,
                from_pending=False,
            )
            if cases:
                selection_source = src
            else:
                cases = ntest_cases_for_impact(paths, apis, tier)
                selection_source = "FALLBACK: no selection"

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

    case_why: dict[str, str] = {}
    for line in why_lines:
        if ": " in line:
            cid, rest = line.split(": ", 1)
            case_why.setdefault(cid.strip(), rest.strip())
    for cid in cases:
        case_why.setdefault(cid, selection_source)

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
        "selection_source": selection_source,
        "case_why": case_why,
        "selection_tier_stats": impact_plan.get("selection_tier_stats") or {},
        "not_covered_blocking": impact_plan.get("not_covered_blocking") or [],
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
        print(f"SOURCE:{out.get('selection_source')}")
        for a in out["apis"]:
            print(f"API:{a}")
        for c in out["ntest_cases"]:
            why = (out.get("case_why") or {}).get(c, "")
            print(f"CASE:{c}\t{why}")
        for r in out["repos"]:
            print(f"REPO:{r}")
        print(f"FILES:{out['pending_files']}")
        print(f"TESTING_PATHS:{1 if out['testing_paths_touched'] else 0}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
