#!/usr/bin/env python3
"""Flow Test Graph (FTG) — test contracts aligned with KG request ids."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
FLOWS = WORKSPACE / "cursor-bundle/flow-test/flows.jsonl"
SOURCES = WORKSPACE / "cursor-bundle/flow-test/sources.jsonl"
CONTRACTS = WORKSPACE / "cursor-bundle/flow-test/contracts.jsonl"
CHANGELOG = WORKSPACE / "cursor-bundle/brain/changelog/CHANGELOG.md"
REGISTRY = WORKSPACE / "scripts/testing/registry.json"
LEARNINGS = WORKSPACE / "cursor-bundle/brain/testing/learnings.jsonl"
ACCOUNTING_DEPLOY = WORKSPACE / "trustt-platform-accounting/deploy"
ACCOUNTING_TESTS = WORKSPACE / "trustt-platform-accounting/src/test/java"
DISBURSE_EXPECTATIONS = WORKSPACE / "scripts/disbursement/disbursement_suite/expectations"
REQUIRED = {"id", "label", "request", "money", "tier", "coverage", "tests", "added"}
TIERS = {"local", "smoke", "regression", "full"}
COVERAGE = {"gap", "partial", "e2e"}
TEST_KEYS = ("unit", "ntest", "disburse_regression", "canned_sql")

# Path keyword → FTG id hints for unit test auto-discovery
UNIT_PATH_HINTS: list[tuple[str, str]] = [
    ("loan/prepayment/processor/ExpireLoanForeclosure", "ftf:foreclosure.batch_expiry_lms"),
    ("loan/repayment/advancerepayment", "ftf:repayment.standard"),
    ("loan/cancellation", "ftf:disb_cancellation.initiate"),
    ("loan/partprepayment", "ftf:partprepayment.approve"),
    ("loan/writeoff", "ftf:writeoff.status"),
    ("loan/interest/normal/booking", "ftf:interest.normal_accrual"),
    ("loan/interest/penal/accrual", "ftf:interest.penal_accrual"),
    ("loan/disbursement/processor", "ftf:disburse.jlg_neft"),
]


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def save_flows(rows: list[dict]) -> None:
    lines = ["# Flow Test Graph (FTG) — enriched from sources.jsonl + ntest registry"]
    for row in rows:
        lines.append(json.dumps(row, separators=(",", ":")))
    FLOWS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_flows() -> list[dict]:
    return load_jsonl(FLOWS)


def orch_has_request(request: str) -> bool:
    if not ACCOUNTING_DEPLOY.is_dir():
        return True
    pat = re.compile(rf'name="{re.escape(request)}"')
    for path in ACCOUNTING_DEPLOY.rglob("*.xml"):
        try:
            if pat.search(path.read_text(encoding="utf-8", errors="ignore")):
                return True
        except OSError:
            continue
    return False


def registry_has_request(request: str) -> bool:
    if not REGISTRY.is_file():
        return False
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for key, case in raw.items():
        if key.startswith("_"):
            continue
        if case.get("api") == request:
            return True
        apis = case.get("apis") or []
        if request in apis:
            return True
    return False


def _merge_unique(existing: list | None, new_items: list[str]) -> list[str]:
    out = list(existing or [])
    seen = set(out)
    for item in new_items:
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _normalize_tests(tests: dict | None) -> dict:
    base = tests if isinstance(tests, dict) else {}
    return {k: list(base.get(k) or []) for k in TEST_KEYS}


def scan_unit_tests() -> dict[str, list[str]]:
    """Map FTG id → unit test class names discovered on disk."""
    by_ftg: dict[str, list[str]] = defaultdict(list)
    if not ACCOUNTING_TESTS.is_dir():
        return by_ftg
    for path in ACCOUNTING_TESTS.rglob("*Test.java"):
        rel = str(path.relative_to(ACCOUNTING_TESTS))
        name = path.stem
        for hint, ftg_id in UNIT_PATH_HINTS:
            if hint in rel.replace("\\", "/"):
                by_ftg[ftg_id].append(name)
                break
    return by_ftg


def scan_disburse_regression() -> list[str]:
    if not DISBURSE_EXPECTATIONS.is_dir():
        return []
    return sorted(p.stem for p in DISBURSE_EXPECTATIONS.glob("*.yaml"))


def load_registry_cases() -> dict[str, dict]:
    if not REGISTRY.is_file():
        return {}
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def sources_by_ftg() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in load_jsonl(SOURCES):
        fid = row.get("ftg_id")
        if fid:
            grouped[fid].append(row)
    return grouped


def cmd_validate() -> int:
    errors: list[str] = []
    seen: set[str] = set()
    for row in load_flows():
        fid = row.get("id", "?")
        missing = REQUIRED - row.keys()
        if missing:
            errors.append(f"{fid}: missing {sorted(missing)}")
        if fid in seen:
            errors.append(f"{fid}: duplicate id")
        seen.add(fid)
        if row.get("tier") not in TIERS:
            errors.append(f"{fid}: invalid tier {row.get('tier')}")
        if row.get("coverage") not in COVERAGE:
            errors.append(f"{fid}: invalid coverage {row.get('coverage')}")
        req = row.get("request")
        kind = row.get("request_kind", "api")
        if req:
            if kind == "batch":
                if not registry_has_request(str(req)):
                    errors.append(f"{fid}: batch request '{req}' not in ntest registry")
            elif kind in ("api", "kafka"):
                if kind == "api" and not orch_has_request(str(req)) and not registry_has_request(str(req)):
                    errors.append(f"{fid}: request '{req}' not in accounting deploy XML or ntest registry")
        tests = row.get("tests") or {}
        if not isinstance(tests, dict):
            errors.append(f"{fid}: tests must be object")
    if errors:
        print("FTG validate: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"FTG validate: OK ({len(seen)} flows)")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = load_flows()
    if args.money:
        rows = [r for r in rows if r.get("money")]
    if args.tier:
        rows = [r for r in rows if r.get("tier") == args.tier]
    if args.coverage:
        rows = [r for r in rows if r.get("coverage") == args.coverage]
    for r in rows:
        tests = _normalize_tests(r.get("tests"))
        ntest_n = len(tests["ntest"])
        unit_n = len(tests["unit"])
        dr_n = len(tests["disburse_regression"])
        print(
            f"{r['id']}\t{r.get('tier')}\t{r.get('coverage')}\t{r['request']}\t"
            f"{unit_n}u {ntest_n}n {dr_n}d\t{r['label']}"
        )
    return 0


def cmd_show(flow_id: str) -> int:
    for r in load_flows():
        if r.get("id") == flow_id:
            print(json.dumps(r, indent=2))
            return 0
    print(f"Not found: {flow_id}", file=sys.stderr)
    return 1


def cmd_gaps() -> int:
    print("Money-path FTG gaps (no unit test AND no ntest/regression, or coverage=gap):\n")
    n = 0
    for r in load_flows():
        if not r.get("money"):
            continue
        tests = _normalize_tests(r.get("tests"))
        has_proof = bool(tests["unit"] or tests["ntest"] or tests["disburse_regression"])
        cov = r.get("coverage")
        if cov == "gap" or not has_proof:
            n += 1
            why = "coverage=gap" if cov == "gap" else "no unit/ntest/regression"
            print(f"  {r['id']}  [{r.get('tier')}]  {r['request']}  ({why})")
    if n == 0:
        print("  (none)")
    return 0


def cmd_suggest() -> int:
    if not CHANGELOG.is_file():
        print("No brain CHANGELOG")
        return 0
    flow_requests = {r.get("request") for r in load_flows()}
    kg_requests: set[str] = set()
    for line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        if "| kg-flow |" not in line and "KG-FLOW:" not in line:
            continue
        m = re.search(r"apiName\s+(\w+)", line)
        if m:
            kg_requests.add(m.group(1))
        for token in ("disburseLoan", "loanRepayment", "loanPrepayment", "updateCollectionBatchDetails",
                      "loanAccountTransactionReversal", "dpiAccrualBooking"):
            if token in line:
                kg_requests.add(token)
    missing = sorted(r for r in kg_requests if r not in flow_requests)
    if missing:
        print("kg-flow precedents without FTG row (consider adding to flows.jsonl):")
        for r in missing:
            print(f"  - {r}")
    else:
        print("All scanned kg-flow requests have an FTG row (heuristic).")
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    rows = load_jsonl(SOURCES)
    if args.ftg:
        rows = [r for r in rows if r.get("ftg_id") == args.ftg]
    if args.source:
        rows = [r for r in rows if r.get("source") == args.source]
    print(f"FTG sources: {len(rows)} entries\n")
    for r in rows:
        print(f"  [{r.get('source')}] {r.get('id')} → {r.get('ftg_id')}  ({r.get('tier')}, {r.get('coverage')})")
    return 0


def cmd_enrich(args: argparse.Namespace) -> int:
    flows = load_flows()
    by_id = {r["id"]: r for r in flows}
    grouped = sources_by_ftg()
    unit_by_ftg = scan_unit_tests()
    disburse_flows = scan_disburse_regression()
    registry = load_registry_cases()

    changes: list[str] = []

    for fid, row in by_id.items():
        tests = _normalize_tests(row.get("tests"))
        before = json.dumps(tests, sort_keys=True)

        # sources.jsonl → ntest / disburse / canned
        for src in grouped.get(fid, []):
            st = src.get("source")
            sid = src.get("id")
            if st == "ntest" and sid:
                tests["ntest"] = _merge_unique(tests["ntest"], [sid])
            elif st == "disburse_regression" and sid:
                tests["disburse_regression"] = _merge_unique(tests["disburse_regression"], [sid])
            elif st == "unit" and sid:
                tests["unit"] = _merge_unique(tests["unit"], [sid])
            for cs in src.get("canned_sql") or []:
                tests["canned_sql"] = _merge_unique(tests["canned_sql"], [cs])
            # promote tier/coverage from verified sources
            if src.get("coverage") == "e2e" and row.get("coverage") == "gap":
                row["coverage"] = "partial"
                changes.append(f"{fid}: coverage gap→partial (source {sid})")
            src_tier = src.get("tier")
            tier_order = ["local", "smoke", "regression", "full"]
            if src_tier in tier_order and tier_order.index(src_tier) > tier_order.index(row.get("tier", "local")):
                row["tier"] = src_tier
                changes.append(f"{fid}: tier → {src_tier} (source {sid})")

        # auto-discovered unit tests
        for ut in unit_by_ftg.get(fid, []):
            tests["unit"] = _merge_unique(tests["unit"], [ut])

        # registry api match → ntest keys
        req = row.get("request")
        if req:
            for reg_id, case in registry.items():
                api = case.get("api")
                apis = case.get("apis") or []
                if api == req or req in apis:
                    tests["ntest"] = _merge_unique(tests["ntest"], [reg_id])

        # disburse flows linked to disburseLoan request
        if req == "disburseLoan":
            tests["disburse_regression"] = _merge_unique(tests["disburse_regression"], disburse_flows)

        after = json.dumps(tests, sort_keys=True)
        if before != after:
            changes.append(f"{fid}: tests updated")
        row["tests"] = tests
        row["enriched"] = "2026-06-19"

    # Merge API chains into FTG rows
    chains_by_req: dict[str, dict] = {}
    chains_path = WORKSPACE / "cursor-bundle/flow-test/chains.jsonl"
    for cr in load_jsonl(chains_path):
        chains_by_req[cr.get("request", "")] = cr
    for fid, row in by_id.items():
        cr = chains_by_req.get(row.get("request", ""))
        if cr:
            row["chain_id"] = cr.get("id")
            row["internal_apis"] = cr.get("internal_apis", [])
            row["cross_service_apis"] = cr.get("cross_service_apis", [])
            row["processor_count"] = cr.get("processor_count", 0)

    print(f"FTG enrich scan: {len(flows)} flows, {len(load_jsonl(SOURCES))} sources, "
          f"{sum(len(v) for v in unit_by_ftg.values())} unit tests mapped, "
          f"{len(disburse_flows)} disburse regression flows\n")

    if args.apply:
        save_flows(list(by_id.values()))
        print(f"Applied enrichment to {FLOWS.relative_to(WORKSPACE)}")
    else:
        print("(dry-run — use --apply to write flows.jsonl)\n")

    for c in changes[:40]:
        print(f"  • {c}")
    if len(changes) > 40:
        print(f"  … and {len(changes) - 40} more")

    # unmapped registry money cases
    mapped_ntest: set[str] = set()
    for r in by_id.values():
        mapped_ntest.update(_normalize_tests(r.get("tests"))["ntest"])
    unmapped = []
    for reg_id, case in registry.items():
        if case.get("type") not in ("api", "batch", "flow"):
            continue
        api = (case.get("api") or "").lower()
        if not any(x in api for x in ("loan", "disburse", "foreclos", "repay", "dpi", "reversal", "batch", "collection")):
            if case.get("type") != "flow":
                continue
        if reg_id not in mapped_ntest and not reg_id.startswith("health.") and not reg_id.startswith("workspace."):
            unmapped.append(reg_id)
    if unmapped:
        print("\nRegistry cases not yet linked to any FTG row:")
        for u in sorted(unmapped):
            print(f"  - {u}")

    return 0


def cmd_contracts(args: argparse.Namespace) -> int:
    """Delegate to contract_graph for cross-service contract queries."""
    import subprocess
    cg = WORKSPACE / "scripts/testing/contract_graph.py"
    cmd = [sys.executable, str(cg), args.contract_cmd]
    if args.contract_cmd == "list":
        if getattr(args, "money", False):
            cmd.append("--money")
        if getattr(args, "protocol", None):
            cmd.extend(["--protocol", args.protocol])
    elif args.contract_cmd == "show" and getattr(args, "contract_id", None):
        cmd.append(args.contract_id)
    return subprocess.call(cmd, cwd=str(WORKSPACE))


def main() -> int:
    parser = argparse.ArgumentParser(description="Flow Test Graph CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="Validate flows.jsonl")
    p_list = sub.add_parser("list", help="List flows")
    p_list.add_argument("--money", action="store_true")
    p_list.add_argument("--tier", choices=sorted(TIERS))
    p_list.add_argument("--coverage", choices=sorted(COVERAGE))
    p_show = sub.add_parser("show", help="Show one flow JSON")
    p_show.add_argument("id")
    sub.add_parser("gaps", help="Money paths missing proof tests or coverage=gap")
    sub.add_parser("suggest", help="kg-flow changelog rows missing FTG")
    p_src = sub.add_parser("sources", help="List enrichment sources catalog")
    p_src.add_argument("--ftg")
    p_src.add_argument("--source", choices=["ntest", "disburse_regression", "unit", "learning"])
    p_enrich = sub.add_parser("enrich", help="Merge sources + registry + unit scan into flows")
    p_enrich.add_argument("--apply", action="store_true", help="Write flows.jsonl")
    p_contracts = sub.add_parser("contracts", help="Cross-service contract graph (see contract-sync.sh scan)")
    p_contracts.add_argument("contract_cmd", choices=["stats", "gaps", "list", "show", "precedents", "sync-ftg"])
    p_contracts.add_argument("contract_id", nargs="?", help="For show")
    p_contracts.add_argument("--money", action="store_true")
    p_contracts.add_argument("--protocol", choices=["HTTP_INTERNAL", "KAFKA"])

    args = parser.parse_args()
    if args.cmd == "validate":
        return cmd_validate()
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "show":
        return cmd_show(args.id)
    if args.cmd == "gaps":
        return cmd_gaps()
    if args.cmd == "suggest":
        return cmd_suggest()
    if args.cmd == "sources":
        return cmd_sources(args)
    if args.cmd == "enrich":
        return cmd_enrich(args)
    if args.cmd == "contracts":
        return cmd_contracts(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
