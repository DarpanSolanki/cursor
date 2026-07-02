#!/usr/bin/env python3
"""
Parallel platform scan — one shot: map + contracts + chains + footprints + testing KG prep.

  platform_scan.py run [--workers N] [--with-kg]
  platform_scan.py stats

Workers run in parallel; merge + enrich + optional KG rebuild sequential.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle/flow-test"
KG_BIN = ROOT / "cursor-bundle/kg/bin"


def _run(cmd: list[str], label: str) -> tuple[str, dict | str, int]:
    t0 = time.time()
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    elapsed = round(time.time() - t0, 2)
    if r.returncode != 0:
        return label, {"error": r.stderr[-2000:] or r.stdout[-500:], "elapsed_s": elapsed}, r.returncode
    out = r.stdout.strip()
    try:
        if out.startswith("{") or out.startswith("["):
            return label, {**json.loads(out), "elapsed_s": elapsed}, 0
    except json.JSONDecodeError:
        pass
    return label, {"output": out[-3000:], "elapsed_s": elapsed}, 0


def worker_platform_map() -> tuple[str, dict | str, int]:
    return _run(
        [sys.executable, str(ROOT / "scripts/testing/platform_map_worker.py")],
        "platform_map",
    )


def worker_contracts() -> tuple[str, dict | str, int]:
    return _run(
        [sys.executable, str(ROOT / "scripts/testing/contract_graph.py"), "scan", "--json"],
        "contracts",
    )


def worker_chains() -> tuple[str, dict | str, int]:
    return _run(
        [sys.executable, str(KG_BIN / "build_api_chains.py"), "--json"],
        "api_chains",
    )


def worker_orchestration_bootstrap() -> tuple[str, dict | str, int]:
    """Light scan: request count per repo (validates orch readable)."""
    return _run(
        [sys.executable, "-c", """
import json, sys
sys.path.insert(0, 'cursor-bundle/kg/bin')
from _contract_scan import scan_workspace
from _paths import WORKSPACE
r = scan_workspace(WORKSPACE)
print(json.dumps({'requests': len(r.request_owners), 'repos': len(r.requests_by_repo)}))
"""],
        "orch_bootstrap",
    )


def phase_merge_and_enrich() -> dict:
    steps = {}
    for name, cmd in [
        ("footprint", [sys.executable, str(ROOT / "scripts/testing/footprint_builder.py"), "build", "--apply"]),
        ("ftg_enrich", [sys.executable, str(ROOT / "scripts/testing/ftg.py"), "enrich", "--apply"]),
        ("footprint2", [sys.executable, str(ROOT / "scripts/testing/footprint_builder.py"), "build", "--apply"]),
        ("contract_rescan", [sys.executable, str(ROOT / "scripts/testing/contract_graph.py"), "scan"]),
    ]:
        label, result, code = _run(cmd, name)
        steps[name] = {"result": result, "ok": code == 0}
    return steps


def phase_kg_rebuild(force: bool = True) -> dict:
    cmd = ["bash", str(ROOT / "scripts/bin/kg-switch.sh")]
    if force:
        cmd.append("--force")
    else:
        cmd.append("--quiet")
    label, result, code = _run(cmd, "kg_rebuild")
    return {"kg_rebuild": {"result": result, "ok": code == 0}}


def cmd_run(args: argparse.Namespace) -> int:
    workers = max(2, min(args.workers, 8))
    print(f"Platform parallel scan — {workers} workers\n")
    t0 = time.time()

    tasks = {
        "platform_map": worker_platform_map,
        "contracts": worker_contracts,
        "api_chains": worker_chains,
        "orch_bootstrap": worker_orchestration_bootstrap,
    }

    results: dict = {}
    fail = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fn): name for name, fn in tasks.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                label, result, code = fut.result()
                results[label] = result
                status = "OK" if code == 0 else "FAIL"
                elapsed = result.get("elapsed_s", "?") if isinstance(result, dict) else "?"
                print(f"  [{status}] {label} ({elapsed}s)")
                if code != 0:
                    fail += 1
                    if isinstance(result, dict) and "error" in result:
                        print(f"         {result['error'][:400]}")
            except Exception as ex:
                results[name] = {"error": str(ex)}
                print(f"  [FAIL] {name}: {ex}")
                fail += 1

    print("\n── Merge + enrich (sequential) ──")
    merge = phase_merge_and_enrich()
    for k, v in merge.items():
        print(f"  [{'OK' if v['ok'] else 'FAIL'}] {k}")
        if not v["ok"]:
            fail += 1

    if args.with_kg:
        print("\n── KG rebuild (includes platform_map + testing_kg) ──")
        kg = phase_kg_rebuild(force=args.force_kg)
        ok = kg["kg_rebuild"]["ok"]
        print(f"  [{'OK' if ok else 'FAIL'}] kg_rebuild")
        if not ok:
            fail += 1
        results["kg"] = kg

    # Write scan manifest
    manifest = {
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s": round(time.time() - t0, 2),
        "parallel_workers": workers,
        "results": results,
        "artifacts": {
            "platform_map": str(FLOW / "platform_map.jsonl"),
            "loan_flows": str(FLOW / "loan_flows.jsonl"),
            "batch_jobs": str(FLOW / "batch_jobs.jsonl"),
            "kafka_index": str(FLOW / "kafka_index.jsonl"),
            "contracts": str(FLOW / "contracts.jsonl"),
            "chains": str(FLOW / "chains.jsonl"),
            "footprints": str(FLOW / "footprints.jsonl"),
        },
    }
    stats = cmd_stats_internal()
    manifest["stats"] = stats
    (FLOW / "scan_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"\n── Summary ({manifest['elapsed_s']}s total) ──")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print(f"\nManifest: cursor-bundle/flow-test/scan_manifest.json")
    if fail:
        print(f"\nplatform_scan: FAIL ({fail} step(s))")
        return 1
    print("\nplatform_scan: PASS")
    try:
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        from learning_bus import append_event
        append_event("scan_complete", source="platform_scan.py", detail=f"elapsed={manifest['elapsed_s']}s",
                     meta=manifest.get("stats", {}))
    except Exception:
        pass
    return 0


def _count_jsonl(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#"))


def cmd_stats_internal() -> dict:
    by_cat: dict[str, int] = {}
    pm = FLOW / "platform_map.jsonl"
    if pm.is_file():
        for line in pm.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            try:
                c = json.loads(line).get("category", "?")
                by_cat[c] = by_cat.get(c, 0) + 1
            except json.JSONDecodeError:
                pass
    fp = load_footprints_stats()
    return {
        "platform_apis": _count_jsonl(FLOW / "platform_map.jsonl"),
        "loan_flows": _count_jsonl(FLOW / "loan_flows.jsonl"),
        "batch_jobs": _count_jsonl(FLOW / "batch_jobs.jsonl"),
        "kafka_entries": _count_jsonl(FLOW / "kafka_index.jsonl"),
        "contracts": _count_jsonl(FLOW / "contracts.jsonl"),
        "chains": _count_jsonl(FLOW / "chains.jsonl"),
        "ftg_flows": _count_jsonl(FLOW / "flows.jsonl"),
        "footprints_verified": fp.get("verified", 0),
        "footprints_untested": fp.get("untested", 0),
        "categories": by_cat,
    }


def load_footprints_stats() -> dict:
    v = u = 0
    for line in (FLOW / "footprints.jsonl").read_text(encoding="utf-8").splitlines() if (FLOW / "footprints.jsonl").is_file() else []:
        if line.startswith("#") or not line.strip():
            continue
        try:
            s = json.loads(line).get("status")
            if s == "verified":
                v += 1
            elif s == "untested":
                u += 1
        except json.JSONDecodeError:
            pass
    return {"verified": v, "untested": u}


def cmd_stats(_: argparse.Namespace) -> int:
    print(json.dumps(cmd_stats_internal(), indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Parallel platform scan")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run", help="Parallel scan + enrich + optional KG")
    pr.add_argument("--workers", type=int, default=4)
    pr.add_argument("--with-kg", action="store_true", help="Rebuild KG after scan")
    pr.add_argument("--force-kg", action="store_true", default=True)
    sub.add_parser("stats")
    args = p.parse_args()
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "stats":
        return cmd_stats(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
