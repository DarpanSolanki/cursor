#!/usr/bin/env python3
"""Change-scoped ship resolution — verify only what changed (workspace-wide).

Partitions pending paths into service / harness / workspace-kb, resolves minimal
registry cases from service code, and maps harness edits to their runner scripts.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from ws_paths import norm_rel

ROOT = Path(__file__).resolve().parents[2]

# Harness script → registry case (built from registry cmd + explicit rows)
_HARNESS_EXPLICIT: dict[str, str] = {
    "scripts/dpic/run_dpi_ship_close_verify.sh": "dpic.ship_close_verify",
    "scripts/dpic/sql/helpers/verify_dpi_full_pipeline.sql": "dpic.ship_close_verify",
    "scripts/dpic/run_dpi_fresh_disburse_e2e.sh": "dpic.push_release",
    "scripts/bin/dpi-booking-posting-guard.sh": "__static_guard__",
    "scripts/bin/disburse-quick.sh": "disbursement.quick",
}

# Cases subsumed by a consolidated runner (do not run twice)
_SUBSUMED_BY: dict[str, frozenset[str]] = {
    "dpic.ship_close_verify": frozenset(
        {
            "dpic.posting_calendar_regression",
            "dpic.eod_txn_regression",
            "dpic.cross_eod_replay_134497",
            "dpic.billing_ud_next_emi",
            "dpic.grace_e2e",
        }
    ),
}

_MONEY_HARNESS_MARKERS = (
    "scripts/dpic/",
    "scripts/bin/dpi-",
    "scripts/bin/disburse",
    "scripts/bin/foreclosure",
    "scripts/sql/",
)


def _norm(rel: str) -> str:
    return norm_rel(rel)


def _to_workspace_rel(path: str) -> str:
    """Normalize absolute or relative paths to workspace-relative form."""
    raw = (path or "").strip()
    if not raw:
        return ""
    p = Path(raw)
    if p.is_absolute():
        try:
            return str(p.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        except ValueError:
            s = str(p).replace("\\", "/")
            root_s = str(ROOT.resolve()).replace("\\", "/")
            if s.startswith(root_s + "/"):
                return s[len(root_s) + 1 :]
            return _norm(s)
    return _norm(raw)


def is_harness_path(path: str) -> bool:
    s = _to_workspace_rel(path)
    if not s.startswith("scripts/"):
        return False
    if s.startswith("scripts/scratch/"):
        return False
    if s.startswith("scripts/testing/"):
        return s.endswith("registry.json") or "/testing/" in s
    if s.startswith("scripts/bin/"):
        return any(m in s for m in _MONEY_HARNESS_MARKERS) or "ship-" in s
    return True


def is_testing_infra_path(path: str) -> bool:
    s = _to_workspace_rel(path)
    return s == "scripts/testing/registry.json" or (
        s.startswith("scripts/testing/") and s.endswith((".py", ".json"))
    )


def is_workspace_kb_path(path: str) -> bool:
    from infer_ship_apis import is_workspace_path

    s = _to_workspace_rel(path)
    if is_harness_path(s) or is_testing_infra_path(s):
        return False
    return is_workspace_path(s)


def is_money_harness_path(path: str) -> bool:
    s = _to_workspace_rel(path)
    return is_harness_path(s) and any(m in s for m in _MONEY_HARNESS_MARKERS)


def is_scratch_path(path: str) -> bool:
    s = _to_workspace_rel(path)
    return s.startswith("scripts/scratch/")


def is_workspace_push_safe_paths(paths: list[str]) -> bool:
    """True when HEAD/paths touch zero service repos (trustt-*/novopay-* code).

    Cursor harness / docs / testing-infra pushes must not re-run sticky money
    ship-loop left by an earlier accounting edit. Service code in HEAD → False.
    """
    if not paths:
        return False
    from infer_ship_apis import is_knowledge_path, is_service_path, infer_repo_from_path

    for raw in paths:
        p = _to_workspace_rel(raw)
        if not p or is_scratch_path(p):
            continue
        # Harness/kb/testing first — filenames like novopay-service.sh must not
        # trip infer_repo_from_path and force a money close on harness push.
        if (
            is_harness_path(p)
            or is_testing_infra_path(p)
            or is_workspace_kb_path(p)
            or is_knowledge_path(p)
        ):
            continue
        if is_service_path(p) or infer_repo_from_path(p):
            return False
        parts = partition_ship_paths([p])
        if parts["service"]:
            return False
    usable = [_to_workspace_rel(p) for p in paths if _to_workspace_rel(p) and not is_scratch_path(p)]
    return bool(usable)


def partition_ship_paths(paths: list[str]) -> dict[str, list[str]]:
    """Split changed paths: service code vs verification harness vs kb vs test infra."""
    service: list[str] = []
    harness: list[str] = []
    workspace_kb: list[str] = []
    testing_infra: list[str] = []

    from infer_ship_apis import infer_repo_from_path, is_service_path

    for raw in paths:
        p = _to_workspace_rel(raw)
        if not p:
            continue
        if is_testing_infra_path(p):
            testing_infra.append(p)
        elif is_workspace_kb_path(p):
            workspace_kb.append(p)
        elif is_harness_path(p):
            harness.append(p)
        elif is_service_path(p) or infer_repo_from_path(p):
            service.append(p)
        elif p.startswith("scripts/"):
            harness.append(p)
        else:
            workspace_kb.append(p)

    return {
        "service": service,
        "harness": harness,
        "workspace_kb": workspace_kb,
        "testing_infra": testing_infra,
    }


def _harness_index(reg: dict) -> dict[str, str]:
    idx = dict(_HARNESS_EXPLICIT)
    for cid, meta in reg.items():
        if cid.startswith("_") or not isinstance(meta, dict):
            continue
        cmd = meta.get("cmd") or ""
        for m in re.finditer(r"(scripts/[^\s\"']+\.(?:sh|py))", cmd):
            script = m.group(1)
            if script not in idx:
                idx[script] = cid
    return idx


def harness_cases_for_paths(harness_paths: list[str], reg: dict) -> list[str]:
    """Map harness file edits → the registry case that runs that script."""
    if not harness_paths:
        return []
    idx = _harness_index(reg)
    out: list[str] = []
    blob = " ".join(harness_paths).lower()
    for script, cid in idx.items():
        if cid == "__static_guard__":
            continue
        if script.lower() in blob or any(script.lower() in _norm(p).lower() for p in harness_paths):
            if cid not in out:
                out.append(cid)
    # SQL helper under dpic/sql → parent runner from filename
    if "verify_dpi_posting" in blob or "posting_calendar" in blob:
        _add("dpic.posting_calendar_regression", out)
    if "verify_dpi_eod" in blob or "eod_txn" in blob:
        _add("dpic.eod_txn_regression", out)
    if "cross_eod" in blob or "134497" in blob:
        _add("dpic.cross_eod_replay_134497", out)
    if "verify_dpi_billing" in blob or "billing_ud" in blob:
        _add("dpic.billing_ud_next_emi", out)
    if "grace_dpi" in blob or "run_grace_dpi" in blob:
        _add("dpic.grace_e2e", out)
    if "run_dpi_full_gate" in blob:
        _add("dpic.ship_close_verify", out)
    return out


def _add(cid: str, out: list[str]) -> None:
    if cid not in out:
        out.append(cid)


def collapse_subsumed_cases(cases: list[str]) -> list[str]:
    drop: set[str] = set()
    for cid in cases:
        drop.update(_SUBSUMED_BY.get(cid, frozenset()))
    return [c for c in cases if c not in drop]


def dpi_ship_modules(service_blob: str, apis: set[str]) -> list[str]:
    """DPI verify modules implied by service code changes only."""
    modules: list[str] = []
    booking = "dpiaccrualbooking" in service_blob or "/dpi/booking/" in service_blob
    billing = "dpibilling" in service_blob or "/dpi/billing/" in service_blob
    calc = any(
        k in service_blob
        for k in ("dpiaccrualcalculation", "/dpi/calculation/", "dpicalculationservice")
    )
    grace = any(k in service_blob for k in ("grace", "ispastgracegate", "computoverduedate"))
    shared_installment = "loaninstallmentdetails" in service_blob.replace("_", "")

    if "dpiAccrualBooking" in apis:
        booking = True
    if "dpiBilling" in apis:
        billing = True
    if "dpiAccrualCalculation" in apis:
        calc = True

    if booking or "postingdate" in service_blob or "accrualbooking" in service_blob:
        modules.extend(["posting", "eod", "cross"])
    if billing or (shared_installment and billing):
        modules.append("billing")
    if calc or grace:
        modules.append("grace")

    if not modules and (booking or billing or calc):
        modules = ["posting", "eod", "cross", "billing", "grace"]
    return list(dict.fromkeys(modules))


def case_env_for_cases(
    cases: list[str], service_paths: list[str], apis: list[str], reg: dict
) -> dict[str, dict[str, str]]:
    from resolve_ship_cases import path_blob

    env: dict[str, dict[str, str]] = {}
    blob = path_blob(service_paths)
    api_set = set(apis)
    if "dpic.ship_close_verify" in cases:
        mods = dpi_ship_modules(blob, api_set)
        if mods:
            env["dpic.ship_close_verify"] = {"DPI_SHIP_MODULES": ",".join(mods)}
    return env


def changed_domains(service_paths: list[str], apis: list[str]) -> list[str]:
    try:
        from accounting_flow_domains import detect_domains, service_path_blob

        blob = service_path_blob(service_paths) if service_paths else ""
        return detect_domains(blob, set(apis))
    except Exception:
        return []


def resolve_change_scope(
    paths: list[str],
    *,
    cli_apis: list[str] | None = None,
    reg: dict | None = None,
) -> dict[str, Any]:
    """Full change-scoped ship plan from a path list (pending files or CLI)."""
    from infer_ship_apis import (
        classify_path,
        filter_dpi_batch_cases,
        infer_repo_from_path,
        merge_tier,
        ntest_cases_for_impact,
        strip_money_cases_for_workspace,
        touches_dpi,
    )

    def _accounting_scoped(paths_in: list[str], apis_in: list[str], tier_in: str) -> bool:
        if any(
            ("trustt-platform-accounting" in p or "novopay-platform-accounting" in p)
            for p in paths_in
        ):
            return True
        return tier_in == "money" and bool(apis_in)

    if reg is None:
        from infer_ship_apis import load_registry

        reg = load_registry()

    parts = partition_ship_paths(paths)
    service = parts["service"]
    harness = parts["harness"]
    workspace_kb = parts["workspace_kb"]
    testing_infra = parts["testing_infra"]

    tier_paths = list(service) + [p for p in harness if is_money_harness_path(p)]
    tier = "workspace"
    repos: list[str] = []
    for p in tier_paths:
        tier = merge_tier(tier, classify_path(str(ROOT / p) if not p.startswith("/") else p))
        repo = infer_repo_from_path(p)
        if repo and repo not in repos:
            repos.append(repo)

    from infer_ship_apis import _focus_apis_for_paths, resolve_apis_smart

    apis: list[str] = list(cli_apis or [])
    if not apis and service:
        apis = _focus_apis_for_paths(service, resolve_apis_smart(service))

    cases: list[str] = []
    if service and tier != "workspace":
        cases = ntest_cases_for_impact(service, apis, tier)
        cases = filter_dpi_batch_cases(cases, apis, service, tier)

    harness_cases = harness_cases_for_paths(harness, reg)

    if harness and not service:
        # Harness-only: run the scripts that were edited, not full domain sweep
        cases = harness_cases
        if harness_cases and any(is_money_harness_path(p) for p in harness):
            tier = merge_tier(tier, "money")
    else:
        for hc in harness_cases:
            if hc not in cases:
                cases.append(hc)

    cases = collapse_subsumed_cases(cases)
    cases = strip_money_cases_for_workspace(cases, tier)

    domains = changed_domains(service, apis)
    case_env = case_env_for_cases(cases, service, apis, reg)

    build_repos = list(repos) if service else []
    harness_only = bool(harness and not service)
    service_only = bool(service and not harness)

    summary_parts: list[str] = []
    if service:
        summary_parts.append(f"service={len(service)}")
    if harness:
        summary_parts.append(f"harness={len(harness)}")
    if workspace_kb:
        summary_parts.append(f"kb={len(workspace_kb)}")
    if domains:
        summary_parts.append(f"domains={','.join(domains[:6])}")
    if harness_only:
        summary_parts.append("mode=harness-only")

    return {
        "tier": tier,
        "apis": apis,
        "ntest_cases": cases,
        "repos": repos,
        "build_repos": build_repos,
        "partitions": parts,
        "domains": domains,
        "case_env": case_env,
        "scope_summary": " ".join(summary_parts) or "empty",
        "harness_only": harness_only,
        "service_only": service_only,
        "dpi_scoped": touches_dpi(service, apis) and tier == "money",
        "accounting_scoped": _accounting_scoped(service, apis, tier),
        "impact_scoped": bool(cases) and tier != "workspace",
        "testing_paths_touched": bool(testing_infra),
    }


def release_cases_for_scope(
    scope: dict[str, Any], reg: dict, *, for_push: bool = False
) -> list[str]:
    """Push-time release cases — only domains touched by service code."""
    if not for_push or scope.get("tier") != "money":
        return []
    from ship_test_plan import build_test_plan

    service = (scope.get("partitions") or {}).get("service") or []
    if not service:
        return []
    plan = build_test_plan(
        service,
        scope.get("apis") or [],
        scope.get("tier") or "money",
        reg,
        changed_domains=scope.get("domains"),
    )
    return list(plan.get("release") or [])
