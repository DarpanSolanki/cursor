#!/usr/bin/env python3
"""LMS flow map audit — KG request↔processor vs change_test_map + domains + registry.

Fail-closed for money-path misroutes (map api not in KG invokes set for that processor).

Usage:
  python3 scripts/lib/lms_flow_map_audit.py
  python3 scripts/lib/lms_flow_map_audit.py --json
  python3 scripts/lib/lms_flow_map_audit.py --fail-on-mismatch
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

# Bust change_test_map lru caches when auditing after edits
import change_test_map as ctm  # noqa: E402

ctm.load_map.cache_clear()
ctm.known_batch_apis.cache_clear()
from change_test_map import api_from_class_stem, api_from_path, load_map  # noqa: E402

KG_DB = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"
ACC_JAVA = ROOT / "trustt-platform-accounting" / "src" / "main" / "java"
REGISTRY = ROOT / "scripts" / "testing" / "registry.json"
DOMAINS = ROOT / "scripts" / "lib" / "accounting_flow_domains.json"

# Money-path processors where map∉KG is a ship-selection bug (TDPQA-207 class)
CRITICAL_STEMS = {
    "GetLoanForeclosureDetailsProcessor",
    "PrepaymentDetailsRepository",
    "CancelLoanForeclosureProcessor",
    "FetchLoanForeclosureSimulationDetailsProcessor",
    "PopulateDdpBorrowerAndLoanDetailsProcessor",
    "GetDeathForeclosureDetailsProcessor",
    "BookChildLoanProcessor",
    "PopulateDataForChildLoanBookingProcessor",
    "DoGenericSyncSTPBankNeftCallBackProcessor",
    "GetLoanAccountDpdCountProcessor",
    "GetChildLoanAccountListProcessor",
    "UpdateChildLoanDisbursementStatusProcessor",
}


def _proc_to_reqs(conn: sqlite3.Connection) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for src, dst in conn.execute(
        "SELECT src_id, dst_id FROM edges WHERE rel = 'invokes'"
    ):
        if src.startswith("request:") and "processor:" in dst:
            api = src.split("/")[-1]
            proc = dst.split("processor:", 1)[-1]
            if "/" in proc:
                proc = proc.split("/")[-1]
            out[proc.lower()].add(api)
        elif dst.startswith("request:") and "processor:" in src:
            api = dst.split("/")[-1]
            proc = src.split("processor:", 1)[-1]
            if "/" in proc:
                proc = proc.split("/")[-1]
            out[proc.lower()].add(api)
    return out


def audit() -> dict:
    if not KG_DB.is_file():
        raise SystemExit(f"KG missing: {KG_DB}")
    conn = sqlite3.connect(str(KG_DB))
    proc_to = _proc_to_reqs(conn)
    conn.close()

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    domains = (json.loads(DOMAINS.read_text(encoding="utf-8")).get("domains") or {})

    processors = sorted(p.stem for p in ACC_JAVA.rglob("*Processor.java"))
    mismatches: list[dict] = []
    critical_fail: list[dict] = []
    ok_n = 0
    for stem in processors:
        kg_apis = sorted(proc_to.get(stem.lower(), set()))
        if not kg_apis:
            continue
        map_api = api_from_class_stem(stem)
        paths = list(ACC_JAVA.rglob(f"{stem}.java"))
        path_api = (
            api_from_path(str(paths[0].relative_to(ROOT))) if paths else None
        )
        effective = map_api or path_api
        if not effective:
            continue
        aliases = set((load_map().get("api_aliases") or {}).get(effective) or [])
        aliases.add(effective)
        if aliases & set(kg_apis):
            ok_n += 1
            continue
        row = {
            "stem": stem,
            "map_api": effective,
            "class_api": map_api,
            "path_api": path_api,
            "kg_apis": kg_apis,
        }
        mismatches.append(row)
        if stem in CRITICAL_STEMS:
            critical_fail.append(row)

    # Domain impact cases missing
    missing_cases = []
    for dname, d in domains.items():
        for cid in d.get("impact_cases") or []:
            if cid not in reg:
                missing_cases.append({"domain": dname, "case": cid})

    # Domain api_hints with zero registry cases
    bare_apis = []
    for dname, d in domains.items():
        for api in d.get("api_hints") or []:
            cases = [
                cid
                for cid, m in reg.items()
                if isinstance(m, dict) and m.get("api") == api
            ]
            if not cases:
                bare_apis.append({"domain": dname, "api": api})

    # class_to_api orphans (mapped class missing on live accounting train src)
    orphans = []
    for cls, api in (load_map().get("class_to_api") or {}).items():
        if not list(ACC_JAVA.rglob(f"{cls}.java")):
            orphans.append({"class": cls, "api": api})

    # Hot package collapse counts
    package_collapse: dict[str, int] = defaultdict(int)
    for p in ACC_JAVA.rglob("*.java"):
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        low = rel.lower()
        if any(
            x in low
            for x in (
                "/loan/prepayment/",
                "/loan/foreclosure/",
                "/loan/deathforeclosure/",
                "/loan/disbursement/",
                "/batchnew/",
            )
        ):
            api = api_from_path(rel) or "None"
            package_collapse[api] += 1

    soft_gap = len(mismatches) + len(bare_apis) + len(orphans) + len(missing_cases)
    return {
        "kg_db": str(KG_DB),
        "processors_scanned": len(processors),
        "ok_map_in_kg": ok_n,
        "mismatch_count": len(mismatches),
        "critical_mismatch_count": len(critical_fail),
        "critical_mismatches": critical_fail,
        "mismatches_sample": mismatches[:50],
        "domain_missing_impact_cases": missing_cases,
        "domain_apis_without_registry_case": bare_apis,
        "class_to_api_orphans": orphans,
        "hot_package_map_collapse": dict(
            sorted(package_collapse.items(), key=lambda kv: -kv[1])
        ),
        "soft_gap_count": soft_gap,
        "verdict": ("FAIL" if critical_fail or soft_gap else "PASS"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="exit 2 if any CRITICAL_STEMS map∉KG",
    )
    args = ap.parse_args()
    result = audit()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=== LMS FLOW MAP AUDIT ===")
        print(f"KG: {result['kg_db']}")
        print(f"Processors scanned: {result['processors_scanned']}")
        print(f"OK (map∈KG): {result['ok_map_in_kg']}")
        print(f"Mismatches (map∉KG): {result['mismatch_count']}")
        print(f"CRITICAL mismatches: {result['critical_mismatch_count']}")
        print(f"Soft gaps (mismatch+bare+orphan+missing): {result.get('soft_gap_count', 0)}")
        print(f"Verdict: {result['verdict']}")
        if result["critical_mismatches"]:
            print("\nCRITICAL:")
            for r in result["critical_mismatches"]:
                print(
                    f"  {r['stem']}: map={r['map_api']!r} KG={r['kg_apis']}"
                )
        if result.get("mismatches_sample"):
            print(f"\nMismatches ({result['mismatch_count']}):")
            for r in result["mismatches_sample"][:20]:
                print(f"  {r['stem']}: map={r['map_api']!r} KG={r['kg_apis']}")
        if result["domain_apis_without_registry_case"]:
            print(
                f"\nDomain api_hints with NO registry case: "
                f"{len(result['domain_apis_without_registry_case'])}"
            )
            for r in result["domain_apis_without_registry_case"][:20]:
                print(f"  {r['domain']}: {r['api']}")
        if result.get("class_to_api_orphans"):
            print(f"\nclass_to_api orphans: {len(result['class_to_api_orphans'])}")
            for r in result["class_to_api_orphans"][:20]:
                print(f"  {r['class']} → {r['api']}")
        print("\nHot-package collapse (files → map api):")
        for api, n in list(result["hot_package_map_collapse"].items())[:15]:
            print(f"  {api}: {n}")
    if args.fail_on_mismatch and (
        result["critical_mismatch_count"] or result.get("soft_gap_count")
    ):
        return 2
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
