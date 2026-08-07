#!/usr/bin/env python3
"""Per-domain coverage, ratcheted — the same pressure money already has, everywhere.

The workspace had exactly one coverage ratchet and it counted money APIs. Everything else
could rot silently: `read_api` sat at 562 APIs with 4 covered, and the accounting `write_ops`
domain at 45 with 1, and no gate anywhere reported a direction. A single global number cannot
substitute either — 1,458 gaps falling by one while `read_api` grows by ten reads as progress.

So the ratchet is per domain, on two dimensions that answer different questions:

  category  — platform-wide (`platform_map.jsonl`): what kind of thing is untested
  domain    — accounting flow domains: which money-adjacent flow is untested

A domain's gap count may fall or hold. It may never grow. New APIs arriving from a rescan are
the one legitimate way a count rises, so the baseline records `total` alongside `gaps` and a
domain that grew only because it got bigger is reported, not failed.

    domain_coverage_gate.py              report + ratchet (exit 1 on regression)
    domain_coverage_gate.py --json
    domain_coverage_gate.py --accept     record current counts as the baseline
    domain_coverage_gate.py --worst 10   the domains to attack first
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
BASELINE = FLOW / "domain_coverage_baseline.json"

sys.path.insert(0, str(ROOT / "scripts" / "lib"))


def _jsonl(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def measure() -> dict[str, dict[str, int]]:
    coverage = {r["api"]: r for r in _jsonl(FLOW / "test_coverage.jsonl") if r.get("api")}
    buckets: dict[str, dict[str, int]] = {}

    def add(key: str, api: str) -> None:
        row = coverage.get(api)
        if row is None:
            return
        b = buckets.setdefault(key, {"total": 0, "gaps": 0})
        b["total"] += 1
        if row.get("gaps"):
            b["gaps"] += 1

    seen: set[tuple[str, str]] = set()
    for row in _jsonl(FLOW / "platform_map.jsonl"):
        api, category = row.get("request"), row.get("category")
        if not api or not category:
            continue
        key = f"category:{category}"
        if (key, api) in seen:
            continue
        seen.add((key, api))
        add(key, api)

    # `coverage_report` names the field `gap`, singular. Reading `gaps` here returned 0 for
    # every domain and the gate reported perfect accounting coverage — a false green is
    # worse than no gate, so the shape is asserted rather than defaulted.
    import accounting_flow_domains as afd
    for entry in afd.coverage_report():
        name = entry.get("domain")
        if not name:
            continue
        if "gap" not in entry or "apis" not in entry:
            raise KeyError(
                f"coverage_report() row for {name!r} lacks 'gap'/'apis' — shape changed; "
                f"got {sorted(entry)}")
        buckets[f"domain:{name}"] = {"total": int(entry["apis"]), "gaps": int(entry["gap"])}

    return dict(sorted(buckets.items()))


def load_baseline() -> dict[str, dict[str, int]]:
    if not BASELINE.is_file():
        return {}
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def compare(now: dict, base: dict) -> tuple[list[str], list[str], dict]:
    regressions: list[str] = []
    grew_by_size: list[str] = []
    merged = dict(base)

    for key, cur in now.items():
        prev = base.get(key)
        if prev is None:
            merged[key] = cur
            continue
        if cur["gaps"] > prev["gaps"]:
            if cur["total"] > prev["total"]:
                grew_by_size.append(
                    f"{key}: gaps {prev['gaps']}→{cur['gaps']} but total {prev['total']}→"
                    f"{cur['total']} — new APIs, not a regression")
                merged[key] = cur
            else:
                regressions.append(
                    f"{key}: gaps grew {prev['gaps']}→{cur['gaps']} "
                    f"(total {cur['total']}) — coverage went backwards")
        else:
            merged[key] = cur
    return regressions, grew_by_size, merged


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--accept", action="store_true")
    ap.add_argument("--worst", type=int, default=0)
    args = ap.parse_args()

    now = measure()

    if args.accept:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"baseline recorded: {len(now)} domain(s), "
              f"{sum(v['gaps'] for v in now.values())} gaps")
        return 0

    base = load_baseline()
    if not base:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"domain-coverage baseline set: {len(now)} domain(s)")
        return 0

    regressions, grew, merged = compare(now, base)

    if args.json:
        print(json.dumps({"now": now, "regressions": regressions, "grew_by_size": grew},
                         indent=1))
        return 1 if regressions else 0

    if args.worst:
        ranked = sorted(now.items(), key=lambda kv: -kv[1]["gaps"])[: args.worst]
        print(f"worst {len(ranked)} domain(s) by untested APIs:")
        for key, v in ranked:
            covered = v["total"] - v["gaps"]
            print(f"  {key:34} {covered:5}/{v['total']:<5} covered   {v['gaps']:5} gaps")
        return 0

    for line in grew:
        print(f"  grew-by-size  {line}")

    if regressions:
        print("DOMAIN COVERAGE REGRESSION:")
        for line in regressions:
            print(f"  - {line}")
        print("  A domain's untested surface may fall or hold. It may never grow.")
        return 1

    if merged != base:
        BASELINE.write_text(json.dumps(merged, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    total_gaps = sum(v["gaps"] for v in now.values())
    improved = sum(1 for k, v in now.items()
                   if k in base and v["gaps"] < base[k]["gaps"])
    note = f", {improved} improved" if improved else ""
    print(f"domain coverage OK — {len(now)} domain(s), {total_gaps} gaps{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
