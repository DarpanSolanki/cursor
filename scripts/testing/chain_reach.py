#!/usr/bin/env python3
"""What a passing transaction actually exercised — including the internal APIs it called.

Covering 1,858 APIs one case at a time is the wrong shape of work. A real transaction already
walks a tree of internal calls, and `chains.jsonl` records that tree statically from the
orchestration: `disburseLoan` calls `getLoanAccountDetails`, `postTransaction`, and
`submitApplication` — the last one in another repo. Running the transaction once reaches all
of them, across services, which is reach no per-API case can buy.

**Exercised is not proven.** An API on the chain of a passing flow ran with whatever inputs
that flow happened to supply; nothing asserted its own contract, and a conditional branch may
not have executed at all. Treating that as coverage would recreate GAP-090 — membership
dressed as evidence — so reach is reported as its own status (`flow_exercised`) and an API
with nothing but reach keeps a gap (`indirect_only`).

    chain_reach.py                 reach from every flow that last ran green
    chain_reach.py --json
    chain_reach.py --api NAME      which flows reach this API
    chain_reach.py --from disburseLoan   the full call tree under one entry API
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
OUT = FLOW / "chain_reach.jsonl"

sys.path.insert(0, str(ROOT / "scripts" / "testing"))

MAX_DEPTH = 6


def load_chains() -> dict[str, dict]:
    path = FLOW / "chains.jsonl"
    if not path.is_file():
        return {}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        row = json.loads(line)
        out.setdefault(row["request"], row)
    return out


def expand(entry: str, chains: dict[str, dict]) -> dict[str, int]:
    """Every API reachable from `entry`, with the depth it was first seen at.

    Depth is capped rather than assumed acyclic: orchestration chains can revisit an API
    (`disburseLoan` lists `submitApplication` twice), and a cycle would otherwise not
    terminate.
    """
    seen: dict[str, int] = {}
    frontier = [(entry, 0)]
    while frontier:
        name, depth = frontier.pop()
        if depth > MAX_DEPTH or name in seen:
            continue
        if depth:
            seen[name] = depth
        chain = chains.get(name)
        if not chain:
            continue
        for callee in chain.get("internal_apis") or []:
            if callee not in seen:
                frontier.append((callee, depth + 1))
    return seen


def passing_entries() -> dict[str, list[str]]:
    """entry apiName -> case ids whose last recorded run was green."""
    import run_evidence
    ev = run_evidence.evidence()
    out: dict[str, list[str]] = {}
    for api, row in ev.items():
        if run_evidence.status_for(api, ev) == "run_verified":
            out[api] = sorted(row.get("cases") or [])
    return out


def build() -> list[dict]:
    chains = load_chains()
    entries = passing_entries()
    reached: dict[str, dict] = {}

    for entry, cases in entries.items():
        for api, depth in expand(entry, chains).items():
            row = reached.setdefault(api, {"api": api, "via": [], "min_depth": depth,
                                           "repos": set()})
            row["via"].append({"entry": entry, "cases": cases, "depth": depth})
            row["min_depth"] = min(row["min_depth"], depth)
            chain = chains.get(api)
            if chain and chain.get("repo"):
                row["repos"].add(chain["repo"])

    rows = []
    for api, row in sorted(reached.items()):
        if api in entries:
            continue
        row["repos"] = sorted(row["repos"])
        row["cross_service"] = any(
            api in (chains.get(v["entry"], {}).get("cross_service_apis") or [])
            for v in row["via"])
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--api")
    ap.add_argument("--from", dest="entry")
    args = ap.parse_args()

    chains = load_chains()

    if args.entry:
        tree = expand(args.entry, chains)
        print(f"{args.entry} reaches {len(tree)} API(s):")
        for api, depth in sorted(tree.items(), key=lambda kv: (kv[1], kv[0])):
            chain = chains.get(api) or {}
            cross = " [cross-service]" if api in (
                chains.get(args.entry, {}).get("cross_service_apis") or []) else ""
            print(f"  d{depth}  {api:44} {chain.get('repo','?')}{cross}")
        return 0

    rows = build()

    if args.api:
        hit = next((r for r in rows if r["api"] == args.api), None)
        print(json.dumps(hit, indent=1) if hit else f"{args.api}: not reached by any green flow")
        return 0

    if args.json:
        print(json.dumps(rows, indent=1))
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        fh.write("# APIs exercised as part of a flow that last ran green.\n")
        fh.write("# Exercised is NOT proven — nothing asserted these contracts (see GAP-090).\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    cross = [r for r in rows if r["cross_service"]]
    print(f"chain reach: {len(rows)} API(s) exercised by a green flow → {OUT.relative_to(ROOT)}")
    print(f"  {len(cross)} reached across a service boundary")
    print("  exercised, not proven — an API with only reach keeps the `indirect_only` gap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
