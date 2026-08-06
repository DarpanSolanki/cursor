#!/usr/bin/env python3
"""
Test map — link registry ↔ FTG ↔ footprints ↔ chains ↔ unit tests ↔ contracts.

  test_map_builder.py build [--apply]
  test_map_builder.py stats [--json]
  test_map_builder.py show --api <apiName>
  test_map_builder.py show --case <registry_id>
  test_map_builder.py gaps [--money]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import run_evidence
import scope_out

WORKSPACE = Path(__file__).resolve().parents[2]
FLOW = WORKSPACE / "cursor-bundle/flow-test"
REGISTRY = WORKSPACE / "scripts/testing/registry.json"
TEST_MAP = FLOW / "test_map.jsonl"
TEST_COVERAGE = FLOW / "test_coverage.jsonl"
JUNIT_INDEX = FLOW / "junit_index.jsonl"
TIERS = ("local", "smoke", "regression", "full")
ACCOUNTING_TESTS = WORKSPACE / "trustt-platform-accounting/src/test/java"


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, header: str, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {header}"]
    for row in rows:
        lines.append(json.dumps(row, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_registry() -> tuple[dict, dict]:
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    correlators = raw.get("_correlators") or {}
    cases = {k: v for k, v in raw.items() if not k.startswith("_")}
    return cases, correlators


def load_flows() -> list[dict]:
    return load_jsonl(FLOW / "flows.jsonl")


def load_footprints() -> dict[str, dict]:
    return {r["ftg_id"]: r for r in load_jsonl(FLOW / "footprints.jsonl") if r.get("ftg_id")}


def ftg_by_api(flows: list[dict]) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = defaultdict(list)
    for f in flows:
        req = f.get("request")
        if req:
            by[req].append(f)
    return by


def ftg_by_ntest_case(flows: list[dict]) -> dict[str, list[str]]:
    """registry case id → ftg ids."""
    m: dict[str, list[str]] = defaultdict(list)
    for f in flows:
        fid = f["id"]
        tests = f.get("tests") or {}
        for nid in tests.get("ntest") or []:
            if fid not in m[nid]:
                m[nid].append(fid)
        for fid2 in tests.get("disburse_regression") or []:
            key = f"disbursement.{fid2}" if not fid2.startswith("disbursement.") else fid2
            if fid not in m[key]:
                m[key].append(fid)
    return m


def scan_junit_index() -> list[dict]:
    rows: list[dict] = []
    if not ACCOUNTING_TESTS.is_dir():
        return rows
    api_pat = re.compile(
        r"(disburseLoan|loanRepayment|loanPrepayment|loanDisbursementCancellation|"
        r"ExpireLoanForeclosure|dpiAccrual|InterestAccrual|PenalInterest|PartPrepayment|Writeoff)",
        re.I,
    )
    for path in ACCOUNTING_TESTS.rglob("*Test.java"):
        rel = str(path.relative_to(WORKSPACE))
        name = path.stem
        hint = None
        m = api_pat.search(name) or api_pat.search(rel)
        if m:
            hint = m.group(1)
        rows.append({
            "id": f"junit:{name}",
            "class": name,
            "repo": "trustt-platform-accounting",
            "src": rel,
            "api_hint": hint,
        })
    return rows


def infer_tier(case_id: str, case: dict, ftg_ids: list[str], flows_by_id: dict[str, dict]) -> str:
    if case.get("tier") in TIERS:
        return case["tier"]
    if case.get("quick"):
        return "smoke"
    if case.get("type") == "health":
        return "smoke"
    if case.get("type") == "flow":
        if "demo" in case_id or "sanity" in case_id or "e2e" in case_id:
            return "regression"
        return "regression"
    for fid in ftg_ids:
        t = flows_by_id.get(fid, {}).get("tier")
        if t in TIERS:
            return t
    if case.get("type") == "batch":
        return "regression"
    return "local"


def best_footprint_status(ftg_ids: list[str], footprints: dict[str, dict]) -> str:
    order = {"verified": 4, "partial": 3, "untested": 2}
    best = "none"
    for fid in ftg_ids:
        fp = footprints.get(fid)
        if not fp:
            continue
        st = fp.get("status", "untested")
        if order.get(st, 0) > order.get(best, 0):
            best = st
    return best


def build_maps() -> tuple[list[dict], list[dict], list[dict], dict]:
    cases, _ = load_registry()
    flows = load_flows()
    flows_by_id = {f["id"]: f for f in flows}
    by_api = ftg_by_api(flows)
    by_ntest = ftg_by_ntest_case(flows)
    footprints = load_footprints()
    run_ev = run_evidence.evidence()
    chains = {c["request"]: c for c in load_jsonl(FLOW / "chains.jsonl")}
    junit = scan_junit_index()
    junit_by_hint: dict[str, list[str]] = defaultdict(list)
    for j in junit:
        if j.get("api_hint"):
            junit_by_hint[j["api_hint"].lower()].append(j["class"])

    map_rows: list[dict] = []
    coverage_by_api: dict[str, dict] = {}

    for case_id, case in sorted(cases.items()):
        ctype = case.get("type", "api")
        api = case.get("api") or ""
        service = case.get("service") or ""
        ftg_ids = list(by_ntest.get(case_id, []))
        if api and not ftg_ids:
            ftg_ids = [f["id"] for f in by_api.get(api, [])]
        tier = infer_tier(case_id, case, ftg_ids, flows_by_id)
        fp_status = best_footprint_status(ftg_ids, footprints)
        unit_tests: list[str] = []
        for fid in ftg_ids:
            unit_tests.extend((flows_by_id.get(fid, {}).get("tests") or {}).get("unit") or [])
        unit_tests = sorted(set(unit_tests))
        chain = chains.get(api) if api else None
        money = any(flows_by_id.get(fid, {}).get("money") for fid in ftg_ids)
        if not money and api:
            money = any(x in api.lower() for x in ("loan", "disburse", "repay", "foreclos", "dpi", "batch", "collection"))

        row = {
            "id": f"map:registry:{case_id}",
            "kind": "registry_case",
            "case_id": case_id,
            "type": ctype,
            "api": api or None,
            "service": service or None,
            "tier": tier,
            "ftg_ids": ftg_ids,
            "footprint_status": fp_status,
            "unit_tests": unit_tests,
            "chain_id": chain.get("id") if chain else None,
            "processor_count": chain.get("processor_count") if chain else None,
            "money": money,
            "quick": bool(case.get("quick")),
        }
        map_rows.append(row)

        if api:
            cov = coverage_by_api.setdefault(api, {
                "api": api,
                "request": api,
                "money": money,
                "registry_cases": [],
                "ftg_ids": [],
                "unit_tests": [],
                "disburse_regression": [],
                "ntest_cases": [],
                "footprint_best": "none",
                "tiers": set(),
            })
            cov["registry_cases"].append(case_id)
            cov["ntest_cases"].append(case_id)
            cov["tiers"].add(tier)
            for fid in ftg_ids:
                if fid not in cov["ftg_ids"]:
                    cov["ftg_ids"].append(fid)
            for ut in unit_tests:
                if ut not in cov["unit_tests"]:
                    cov["unit_tests"].append(ut)
            st = best_footprint_status(cov["ftg_ids"], footprints)
            if {"verified": 4, "partial": 3, "untested": 2}.get(st, 0) > {"verified": 4, "partial": 3, "untested": 2, "none": 0}.get(cov["footprint_best"], 0):
                cov["footprint_best"] = st

    # FTG-only coverage (no registry case)
    for f in flows:
        req = f.get("request")
        if not req:
            continue
        cov = coverage_by_api.setdefault(req, {
            "api": req,
            "request": req,
            "money": bool(f.get("money")),
            "registry_cases": [],
            "ftg_ids": [],
            "unit_tests": [],
            "disburse_regression": [],
            "ntest_cases": [],
            "footprint_best": "none",
            "tiers": set(),
        })
        if f["id"] not in cov["ftg_ids"]:
            cov["ftg_ids"].append(f["id"])
        tests = f.get("tests") or {}
        for ut in tests.get("unit") or []:
            if ut not in cov["unit_tests"]:
                cov["unit_tests"].append(ut)
        for dr in tests.get("disburse_regression") or []:
            if dr not in cov["disburse_regression"]:
                cov["disburse_regression"].append(dr)
        for nid in tests.get("ntest") or []:
            if nid not in cov["ntest_cases"]:
                cov["ntest_cases"].append(nid)
        cov["tiers"].add(f.get("tier", "local"))
        st = best_footprint_status(cov["ftg_ids"], footprints)
        cov["footprint_best"] = st if st != "none" else cov["footprint_best"]
        if f.get("money"):
            cov["money"] = True

    coverage_rows: list[dict] = []
    for api, cov in sorted(coverage_by_api.items()):
        has_proof = bool(
            cov["registry_cases"] or cov["unit_tests"] or cov["disburse_regression"]
            or cov["ntest_cases"]
        )
        gap_reasons: list[str] = []
        # A curated footprint is typed, not proven. A recorded ntest pass is evidence, so it
        # satisfies the money-proof gate; a recorded fail is worse than silence and is named.
        run_status = run_evidence.status_for(api, run_ev)
        # Flows that are not live in production (penal, write-off) carry no coverage debt —
        # their absence of proof is correct, not a gap. Scoping one in is a product decision.
        scoped_out = scope_out.is_scope_out(api)
        proven = cov["footprint_best"] == "verified" or run_status == "run_verified"
        if scoped_out:
            pass
        elif cov["money"] and not proven:
            gap_reasons.append("money_no_verified_footprint")
        if not scoped_out and cov["money"] and run_status == "run_failed":
            gap_reasons.append("last_run_failed")
        if not scoped_out and cov["money"] and not has_proof:
            gap_reasons.append("no_tests")
        if not scoped_out:
            for f in flows_by_id.values():
                if f.get("request") == api and f.get("coverage") == "gap":
                    gap_reasons.append("ftg_coverage_gap")
                    break
        row = {
            "id": f"coverage:{api}",
            "api": api,
            "money": cov["money"],
            "registry_cases": sorted(cov["registry_cases"]),
            "ftg_ids": cov["ftg_ids"],
            "unit_tests": sorted(cov["unit_tests"]),
            "disburse_regression": sorted(cov["disburse_regression"]),
            "ntest_cases": sorted(cov["ntest_cases"]),
            "footprint_best": cov["footprint_best"],
            "tiers": sorted(cov["tiers"]),
            "has_proof": has_proof,
            "scope": "out" if scoped_out else "in",
            "gaps": sorted(set(gap_reasons)),
        }
        if chain := chains.get(api):
            row["chain_id"] = chain.get("id")
            row["processor_count"] = chain.get("processor_count")
        coverage_rows.append(row)

    stats = {
        "registry_cases": len(map_rows),
        "apis_covered": len(coverage_rows),
        "money_apis": sum(1 for r in coverage_rows if r["money"]),
        "money_gaps": sum(1 for r in coverage_rows if r["money"] and r["gaps"]),
        "junit_classes": len(junit),
        "verified_footprints": sum(1 for r in coverage_rows if r["footprint_best"] == "verified"),
    }
    return map_rows, coverage_rows, junit, stats


def cmd_build(args: argparse.Namespace) -> int:
    map_rows, cov_rows, junit, stats = build_maps()
    if args.apply:
        write_jsonl(TEST_MAP, "Registry case → FTG → footprint map", map_rows)
        write_jsonl(TEST_COVERAGE, "Per-apiName test coverage matrix", cov_rows)
        write_jsonl(JUNIT_INDEX, "JUnit classes (accounting-v2)", junit)
        try:
            sys.path.insert(0, str(WORKSPACE / "scripts/testing"))
            from learning_bus import append_event
            append_event("scan_complete", source="test_map_builder.py", detail="test map built", meta=stats)
        except Exception:
            pass
    print("Test map build:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if args.apply:
        print(f"  written: {TEST_MAP.relative_to(WORKSPACE)}")
        print(f"  written: {TEST_COVERAGE.relative_to(WORKSPACE)}")
    else:
        print("(dry-run — use --apply to write)")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    if not TEST_COVERAGE.is_file():
        _, cov, _, stats = build_maps()
    else:
        cov = load_jsonl(TEST_COVERAGE)
        stats = {
            "registry_cases": len(load_jsonl(TEST_MAP)),
            "apis_covered": len(cov),
            "money_gaps": sum(1 for r in cov if r.get("money") and r.get("gaps")),
        }
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        for k, v in stats.items():
            print(f"{k}: {v}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    if args.api:
        for r in load_jsonl(TEST_COVERAGE):
            if r.get("api") == args.api:
                print(json.dumps(r, indent=2))
                return 0
        print(f"No coverage row for api={args.api}", file=sys.stderr)
        return 1
    if args.case:
        for r in load_jsonl(TEST_MAP):
            if r.get("case_id") == args.case:
                print(json.dumps(r, indent=2))
                return 0
        print(f"No map row for case={args.case}", file=sys.stderr)
        return 1
    print("Provide --api or --case", file=sys.stderr)
    return 2


def cmd_gaps(args: argparse.Namespace) -> int:
    rows = load_jsonl(TEST_COVERAGE) if TEST_COVERAGE.is_file() else build_maps()[1]
    n = 0
    print("Test coverage gaps:\n")
    for r in rows:
        if args.money and not r.get("money"):
            continue
        if not r.get("gaps"):
            continue
        n += 1
        print(f"  {r['api']:45} {r['gaps']}  footprint={r.get('footprint_best')}")
    if n == 0:
        print("  (none with gap flags)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Test intelligence map")
    sub = p.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    pb.add_argument("--apply", action="store_true")
    ps = sub.add_parser("stats")
    ps.add_argument("--json", action="store_true")
    psh = sub.add_parser("show")
    psh.add_argument("--api")
    psh.add_argument("--case")
    pg = sub.add_parser("gaps")
    pg.add_argument("--money", action="store_true")
    args = p.parse_args()
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "stats":
        return cmd_stats(args)
    if args.cmd == "show":
        return cmd_show(args)
    if args.cmd == "gaps":
        return cmd_gaps(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
