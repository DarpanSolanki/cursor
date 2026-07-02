#!/usr/bin/env python3
"""
Incremental sync engine — fingerprint-gated rebuilds; learning bus always hot.

Fast path: skip rebuild when inputs unchanged (~0–2s).
Full path: explicit --full only (~minutes if KG/platform scan).

Self-learning is NEVER skipped: learning_bus append + hint propagation run always.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle/flow-test"
FP = ROOT / ".cursor/.intel-fingerprint.json"
CACHE = ROOT / ".cursor/.intel-cache.json"
HUB = ROOT / ".cursor/workspace-intelligence-state.md"
METRICS = ROOT / ".cursor/.intel-metrics.jsonl"
KG_STATE = ROOT / ".cursor/workspace-kg-state.md"
HUB_MAX_AGE_S = 600  # refresh hub at most every 10 min on fast path
METRICS_MAX_LINES = 500

LAYER_INPUTS: dict[str, list[str]] = {
    "platform": [],  # special: orchestration XML mtimes via _orch_inputs_max()
    "ftg": [
        "cursor-bundle/flow-test/sources.jsonl",
        "scripts/testing/registry.json",
        "cursor-bundle/flow-test/chains.jsonl",
    ],
    "footprints": [
        "cursor-bundle/flow-test/flows.jsonl",
        "cursor-bundle/flow-test/sources.jsonl",
        "cursor-bundle/flow-test/contracts.jsonl",
    ],
    "test_map": [
        "scripts/testing/registry.json",
        "cursor-bundle/flow-test/flows.jsonl",
        "cursor-bundle/flow-test/footprints.jsonl",
    ],
    "hub": [
        "cursor-bundle/flow-test/test_coverage.jsonl",
        "cursor-bundle/flow-test/learning_bus.jsonl",
        "cursor-bundle/kg/data/kg.db",
    ],
}

LAYER_OUTPUTS: dict[str, str] = {
    "platform": "cursor-bundle/flow-test/chains.jsonl",
    "ftg": "cursor-bundle/flow-test/flows.jsonl",
    "footprints": "cursor-bundle/flow-test/footprints.jsonl",
    "test_map": "cursor-bundle/flow-test/test_map.jsonl",
    "hub": ".cursor/workspace-intelligence-state.md",
}


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _inputs_max(rel_paths: list[str]) -> float:
    return max((_mtime(ROOT / p) for p in rel_paths), default=0.0)


def _orch_inputs_max() -> float:
    """Latest mtime of orchestration XML across service repos."""
    mx = 0.0
    for repo in ROOT.iterdir():
        if not repo.is_dir():
            continue
        name = repo.name
        if not (name.startswith("novopay-") or name.startswith("trustt-")):
            continue
        orch = repo / "deploy/application/orchestration"
        if not orch.is_dir():
            continue
        for xml in orch.rglob("*.xml"):
            mx = max(mx, _mtime(xml))
    return mx


def _platform_inputs_max() -> float:
    imax = _orch_inputs_max()
    for rel in (
        "cursor-bundle/flow-test/contracts.jsonl",
        "cursor-bundle/flow-test/platform_map.jsonl",
    ):
        imax = max(imax, _mtime(ROOT / rel))
    return imax


def _layer_inputs_max(layer: str) -> float:
    if layer == "platform":
        return _platform_inputs_max()
    return _inputs_max(LAYER_INPUTS.get(layer, []))


def log_metrics(result: dict) -> None:
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": result.get("mode"),
        "elapsed_s": result.get("elapsed_s"),
        "ok": result.get("ok"),
        "rebuilt": result.get("rebuilt"),
        "skipped": result.get("skipped"),
        "steps": result.get("steps"),
    }
    line = json.dumps(row, separators=(",", ":")) + "\n"
    lines: list[str] = []
    if METRICS.is_file():
        lines = METRICS.read_text(encoding="utf-8").splitlines()
    lines.append(line.strip())
    if len(lines) > METRICS_MAX_LINES:
        lines = lines[-METRICS_MAX_LINES:]
    METRICS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _kg_validate_recent(max_age_s: int = 90) -> bool:
    if not KG_STATE.is_file():
        return False
    return time.time() - _mtime(KG_STATE) < max_age_s


def load_fp() -> dict:
    if not FP.is_file():
        return {}
    try:
        return json.loads(FP.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_fp(data: dict) -> None:
    FP.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    FP.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def is_stale(layer: str) -> bool:
    out_rel = LAYER_OUTPUTS.get(layer, "")
    out = ROOT / out_rel
    if not out.is_file():
        return True
    imax = _layer_inputs_max(layer)
    fp = load_fp()
    rec = fp.get("layers", {}).get(layer, {})
    if imax > rec.get("inputs_max", 0) + 0.001:
        return True
    if _mtime(out) < imax:
        return True
    return False


def mark_layer(layer: str) -> None:
    fp = load_fp()
    layers = fp.setdefault("layers", {})
    out_rel = LAYER_OUTPUTS[layer]
    layers[layer] = {
        "inputs_max": _layer_inputs_max(layer),
        "output_mtime": _mtime(ROOT / out_rel),
        "built_at": time.time(),
    }
    save_fp(fp)


def hub_needs_refresh() -> bool:
    if not HUB.is_file():
        return True
    if is_stale("hub"):
        return True
    age = time.time() - _mtime(HUB)
    return age > HUB_MAX_AGE_S


def run(cmd: list[str], timeout: int = 120, quiet: bool = False) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout,
        )
        out = (p.stdout or "") + (p.stderr or "")
        if not quiet and out.strip():
            print(out.strip()[:2000])
        return p.returncode, out
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT ({timeout}s): {' '.join(cmd)}", file=sys.stderr)
        return 124, "timeout"


def always_learn() -> dict:
    """Hot path — never skip; keeps cross-layer hints current."""
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    from cross_learn import propagate_learnings_to_hints
    n = propagate_learnings_to_hints()
    return {"hints_propagated": n}


def write_cache(stats: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    stats["cached_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    CACHE.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")


def read_cache() -> dict:
    if not CACHE.is_file():
        return {}
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def fast_session(*, quiet: bool = False, skip_kg_ensure: bool = False) -> dict:
    """Target <5s: KG cache restore if needed, validate, cached stats, hub if stale."""
    t0 = time.time()
    result: dict = {"mode": "fast", "steps": []}

    skip = skip_kg_ensure or os.environ.get("SKIP_KG_ENSURE", "").strip() in ("1", "true", "yes")
    if not skip:
        rc, _ = run(["bash", "scripts/bin/kg-ensure-fresh.sh", "--quiet"], timeout=90, quiet=quiet)
        result["steps"].append({"kg_ensure": rc})
    else:
        result["steps"].append({"kg_ensure": "skipped"})

    skip_validate = os.environ.get("SKIP_KG_VALIDATE", "").strip() in ("1", "true", "yes")
    if skip_validate or _kg_validate_recent():
        result["steps"].append({"kg_validate": "skipped_recent"})
        rc = 0
    else:
        rc, out = run(
            [sys.executable, str(ROOT / "cursor-bundle/kg/bin/kg.py"), "validate"],
            timeout=30, quiet=quiet,
        )
        result["steps"].append({"kg_validate": rc})
    if rc != 0:
        result["ok"] = False
        result["elapsed_s"] = round(time.time() - t0, 2)
        log_metrics(result)
        return result

    learn = always_learn()
    result["learn"] = learn

    if hub_needs_refresh():
        rc, _ = run(
            [sys.executable, str(ROOT / "scripts/testing/intelligence_hub.py"), "--write", "--fast"],
            timeout=45, quiet=quiet,
        )
        result["steps"].append({"hub_refresh": rc})
        if rc == 0:
            mark_layer("hub")
    else:
        result["steps"].append({"hub_refresh": "skipped_fresh"})

    cache = read_cache()
    if not cache.get("test_map"):
        rc, out = run(
            [sys.executable, str(ROOT / "scripts/testing/test_map_builder.py"), "stats", "--json"],
            timeout=15, quiet=True,
        )
        if rc == 0:
            try:
                cache["test_map"] = json.loads(out)
                write_cache(cache)
            except json.JSONDecodeError:
                pass
    result["cache"] = cache.get("test_map", {})
    result["ok"] = True
    result["elapsed_s"] = round(time.time() - t0, 2)
    log_metrics(result)
    return result


def _rebuild_platform(*, quiet: bool = False) -> bool:
    kg_chains = ROOT / "cursor-bundle/kg/bin/build_api_chains.py"
    contract = ROOT / "scripts/testing/contract_graph.py"
    ok = True
    if contract.is_file():
        rc, _ = run([sys.executable, str(contract), "scan"], timeout=180, quiet=quiet)
        ok = ok and rc == 0
    if kg_chains.is_file():
        rc, _ = run([sys.executable, str(kg_chains)], timeout=120, quiet=quiet)
        ok = ok and rc == 0
    return ok


def fast_sync(*, quiet: bool = False) -> dict:
    """Incremental rebuild only stale layers; always propagate learnings."""
    t0 = time.time()
    result: dict = {"mode": "fast", "rebuilt": [], "skipped": []}

    learn = always_learn()
    result["learn"] = learn

    if is_stale("platform"):
        if _rebuild_platform(quiet=quiet):
            mark_layer("platform")
            result["rebuilt"].append("platform")
        else:
            result["skipped"].append("platform_failed")
    else:
        result["skipped"].append("platform")

    if is_stale("ftg") or "platform" in result["rebuilt"]:
        rc, _ = run(
            [sys.executable, str(ROOT / "scripts/testing/ftg.py"), "enrich", "--apply"],
            timeout=60, quiet=quiet,
        )
        if rc == 0:
            mark_layer("ftg")
            result["rebuilt"].append("ftg")
    else:
        result["skipped"].append("ftg")

    if is_stale("footprints") or "ftg" in result["rebuilt"]:
        rc, _ = run(
            [sys.executable, str(ROOT / "scripts/testing/footprint_builder.py"), "build", "--apply"],
            timeout=60, quiet=quiet,
        )
        if rc == 0:
            mark_layer("footprints")
            result["rebuilt"].append("footprints")
    else:
        result["skipped"].append("footprints")

    if is_stale("test_map") or result["rebuilt"]:
        rc, _ = run(
            [sys.executable, str(ROOT / "scripts/testing/test_map_builder.py"), "build", "--apply"],
            timeout=30, quiet=quiet,
        )
        if rc == 0:
            mark_layer("test_map")
            result["rebuilt"].append("test_map")
            rc2, out = run(
                [sys.executable, str(ROOT / "scripts/testing/test_map_builder.py"), "stats", "--json"],
                timeout=10, quiet=True,
            )
            if rc2 == 0:
                try:
                    write_cache({"test_map": json.loads(out)})
                except json.JSONDecodeError:
                    pass
    else:
        result["skipped"].append("test_map")

    if hub_needs_refresh() or result["rebuilt"]:
        rc, _ = run(
            [sys.executable, str(ROOT / "scripts/testing/intelligence_hub.py"), "--write", "--fast"],
            timeout=45, quiet=quiet,
        )
        if rc == 0:
            mark_layer("hub")
            result["rebuilt"].append("hub")
    else:
        result["skipped"].append("hub")

    try:
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        from learning_bus import append_event
        append_event(
            "hub_refresh",
            source="sync_engine.fast_sync",
            detail=f"rebuilt={result['rebuilt']} skipped={result['skipped']}",
        )
    except Exception:
        pass

    result["elapsed_s"] = round(time.time() - t0, 2)
    result["ok"] = True
    log_metrics(result)
    return result


def full_sync(*, with_kg: bool = False, quiet: bool = False) -> dict:
    """Explicit heavy path — use after branch checkout or orchestration drift."""
    t0 = time.time()
    result: dict = {"mode": "full", "steps": []}

    for label, cmd, timeout in [
        ("sync_test", ["bash", "scripts/bin/sync-test-intelligence.sh", "--full"], 180),
        ("sync_intel", ["bash", "scripts/bin/sync-intelligence.sh", "--quick"], 300),
    ]:
        rc, _ = run(cmd, timeout=timeout, quiet=quiet)
        result["steps"].append({label: rc})

    if with_kg:
        rc, _ = run(["bash", "scripts/bin/kg-switch.sh", "--force"], timeout=1800, quiet=quiet)
        result["steps"].append({"kg_rebuild": rc})

    for layer in LAYER_OUTPUTS:
        mark_layer(layer)

    always_learn()
    try:
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        from learning_bus import compact_bus
        compact_bus()
    except Exception:
        pass
    result["elapsed_s"] = round(time.time() - t0, 2)
    result["ok"] = all(v == 0 for s in result["steps"] for v in s.values())
    log_metrics(result)
    return result


def cmd_status(_: argparse.Namespace) -> int:
    fp = load_fp()
    print("Intelligence sync status:\n")
    for layer in LAYER_OUTPUTS:
        inputs = LAYER_INPUTS.get(layer, [])
        stale = is_stale(layer)
        extra = f"orch_max={int(_orch_inputs_max())}" if layer == "platform" else f"inputs={len(inputs)}"
        print(f"  {layer:12} {'STALE' if stale else 'fresh':5}  {extra}")
    print(f"\nHub age: {int(time.time() - _mtime(HUB))}s  fingerprint: {FP}")
    print(f"Cache: {CACHE}")
    if METRICS.is_file():
        last = METRICS.read_text(encoding="utf-8").strip().splitlines()[-1:]
        if last:
            try:
                m = json.loads(last[0])
                print(f"Last sync: {m.get('mode')} {m.get('elapsed_s')}s ok={m.get('ok')}")
            except json.JSONDecodeError:
                pass
    return 0


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Incremental intelligence sync")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    pf = sub.add_parser("fast-session")
    pf.add_argument("--quiet", action="store_true")
    ps = sub.add_parser("fast-sync")
    ps.add_argument("--quiet", action="store_true")
    pfull = sub.add_parser("full-sync")
    pfull.add_argument("--kg", action="store_true")
    pfull.add_argument("--quiet", action="store_true")
    pcompact = sub.add_parser("compact-bus")
    pcompact.add_argument("--max-events", type=int, default=5000)
    args = p.parse_args()

    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "compact-bus":
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        from learning_bus import compact_bus
        print(json.dumps(compact_bus(max_events=args.max_events), indent=2))
        return 0
    if args.cmd == "fast-session":
        r = fast_session(quiet=args.quiet)
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1
    if args.cmd == "fast-sync":
        r = fast_sync(quiet=args.quiet)
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1
    if args.cmd == "full-sync":
        r = full_sync(with_kg=args.kg, quiet=args.quiet)
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
