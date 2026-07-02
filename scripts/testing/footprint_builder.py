#!/usr/bin/env python3
"""
Flow footprints — verified test runs with full internal API chain.
Merge: FTG + sources + chains + contracts + changelog precedents.

  footprint_builder.py build [--apply]
  footprint_builder.py show <ftg_id>
  footprint_builder.py list [--verified]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
FLOWS = WORKSPACE / "cursor-bundle/flow-test/flows.jsonl"
SOURCES = WORKSPACE / "cursor-bundle/flow-test/sources.jsonl"
CHAINS = WORKSPACE / "cursor-bundle/flow-test/chains.jsonl"
CONTRACTS = WORKSPACE / "cursor-bundle/flow-test/contracts.jsonl"
FOOTPRINTS = WORKSPACE / "cursor-bundle/flow-test/footprints.jsonl"
CHANGELOG = WORKSPACE / "cursor-bundle/brain/changelog/CHANGELOG.md"
CURSOR_CL = WORKSPACE / ".cursor/changelog.md"
BRANCH_FILE = WORKSPACE / "cursor-bundle/flow-test/branch_watermark.json"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def save_jsonl(path: Path, rows: list[dict], header: str) -> None:
    lines = [f"# {header}"]
    for row in rows:
        lines.append(json.dumps(row, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def git_branch(repo: str) -> str:
    import subprocess
    p = WORKSPACE / repo
    if not (p / ".git").is_dir():
        return "unknown"
    r = subprocess.run(
        ["git", "-C", str(p), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def branch_watermark() -> dict:
    core = [
        "novopay-platform-accounting-v2",
        "novopay-platform-payments",
        "novopay-mfi-los",
        "novopay-platform-actor",
        "novopay-platform-batch",
    ]
    import subprocess
    wm = {"target": "mfi_integration_v3.3.1.1", "repos": {}, "scanned_at": ""}
    from datetime import datetime, timezone
    wm["scanned_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for repo in core:
        p = WORKSPACE / repo
        if not (p / ".git").is_dir():
            continue
        branch = git_branch(repo)
        head = subprocess.run(
            ["git", "-C", str(p), "rev-parse", "--short=10", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        upstream = subprocess.run(
            ["git", "-C", str(p), "rev-parse", "--short=10", "upstream/mfi_integration_v3.3.1.1"],
            capture_output=True, text=True,
        ).stdout.strip()
        wm["repos"][repo] = {
            "branch": branch,
            "head": head,
            "upstream_v3.3.1.1": upstream or None,
            "aligned": branch == "mfi_integration_v3.3.1.1",
        }
    return wm


def parse_precedents() -> dict[str, list[str]]:
    prec: dict[str, set[str]] = {}
    for path in (CHANGELOG, CURSOR_CL):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            tickets = re.findall(r"SDCP-\d+|GAP-\d+", line, re.I)
            if not tickets:
                continue
            for token in re.findall(r"\b[a-z][a-zA-Z0-9]{4,}\b", line):
                if token[0].islower() and len(token) > 5:
                    prec.setdefault(token, set()).update(tickets)
    return {k: sorted(v) for k, v in prec.items()}


def chain_for_request(chains: list[dict], repo: str, request: str) -> dict | None:
    cid = f"chain:{repo}:{request}"
    for c in chains:
        if c.get("id") == cid:
            return c
    for c in chains:
        if c.get("request") == request:
            return c
    return None


def contracts_for_request(contracts: list[dict], request: str) -> list[dict]:
    out = []
    for c in contracts:
        prod = c.get("producer") or {}
        cons = c.get("consumer") or {}
        if prod.get("request") == request or cons.get("request") == request:
            out.append(c)
    return out


def build_footprints() -> list[dict]:
    flows = load_jsonl(FLOWS)
    sources = load_jsonl(SOURCES)
    chains = load_jsonl(CHAINS)
    contracts = load_jsonl(CONTRACTS)
    precedents = parse_precedents()
    wm = branch_watermark()

    source_by_ftg: dict[str, list[dict]] = {}
    for s in sources:
        fid = s.get("ftg_id")
        if fid:
            source_by_ftg.setdefault(fid, []).append(s)

    fps: list[dict] = []
    for flow in flows:
        fid = flow["id"]
        req = flow.get("request", "")
        repo = (flow.get("producer") or {}).get("service") or "novopay-platform-accounting-v2"
        chain = chain_for_request(chains, repo, req)
        rel_contracts = contracts_for_request(contracts, req)
        tests = flow.get("tests") or {}
        src_rows = source_by_ftg.get(fid, [])
        verified = max((s.get("verified", "") for s in src_rows), default="")
        if verified == "scan":
            verified = ""

        prec: set[str] = set(flow.get("precedents") or [])
        for p in precedents.get(req, []):
            prec.add(p)
        for c in rel_contracts:
            for p in c.get("precedents") or []:
                prec.add(p)

        has_proof = bool(
            (tests.get("unit") or [])
            or (tests.get("ntest") or [])
            or (tests.get("disburse_regression") or [])
        )
        coverage = flow.get("coverage", "gap")
        status = "verified" if has_proof and coverage in ("partial", "e2e") else (
            "partial" if has_proof else "untested"
        )

        fp = {
            "id": f"fp:{fid.removeprefix('ftf:')}",
            "ftg_id": fid,
            "request": req,
            "entry_service": repo,
            "label": flow.get("label"),
            "money": flow.get("money", False),
            "tier": flow.get("tier"),
            "status": status,
            "coverage": coverage,
            "verified": verified or None,
            "branch_watermark": wm["target"],
            "branch_drift": [r for r, v in wm["repos"].items() if not v.get("aligned")],
            "internal_apis": (chain or {}).get("internal_apis", []),
            "processors": (chain or {}).get("processors", []),
            "cross_service_apis": (chain or {}).get("cross_service_apis", []),
            "chain_id": (chain or {}).get("id"),
            "contracts": [c["id"] for c in rel_contracts[:10]],
            "tests": tests,
            "precedents": sorted(prec),
            "post": flow.get("post") or {},
            "terminal_state": flow.get("post") or {},
        }
        fps.append(fp)
    return fps


def cmd_build(args: argparse.Namespace) -> int:
    wm = branch_watermark()
    BRANCH_FILE.write_text(json.dumps(wm, indent=2) + "\n", encoding="utf-8")
    fps = build_footprints()
    if args.apply:
        save_jsonl(FOOTPRINTS, fps, "Flow footprints — verified runs + full internal API chain")
    verified = sum(1 for f in fps if f["status"] == "verified")
    partial = sum(1 for f in fps if f["status"] == "partial")
    untested = sum(1 for f in fps if f["status"] == "untested")
    drift = wm["repos"]
    not_aligned = [r for r, v in drift.items() if not v.get("aligned")]
    print("Footprint build:")
    print(f"  flows: {len(fps)}  verified: {verified}  partial: {partial}  untested: {untested}")
    print(f"  branch target: {wm['target']}")
    if not_aligned:
        print(f"  ⚠ branch drift: {', '.join(not_aligned)}")
    else:
        print("  branch: core repos aligned to target (or on matching HEAD)")
    if args.apply:
        print(f"  written: {FOOTPRINTS.relative_to(WORKSPACE)}")
        print(f"  watermark: {BRANCH_FILE.relative_to(WORKSPACE)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = load_jsonl(FOOTPRINTS)
    if not rows:
        print("No footprints — run: footprint_builder.py build --apply (after chain build)")
        return 1
    if args.verified:
        rows = [r for r in rows if r.get("status") == "verified"]
    for r in rows:
        apis = len(r.get("internal_apis") or [])
        cross = len(r.get("cross_service_apis") or [])
        print(f"{r['ftg_id']}\t{r['status']}\t{r.get('coverage')}\t{apis} apis {cross} cross\t{r['request']}")
    return 0


def cmd_show(ftg_id: str) -> int:
    fid = ftg_id if ftg_id.startswith("ftf:") else f"ftf:{ftg_id}"
    for r in load_jsonl(FOOTPRINTS):
        if r.get("ftg_id") == fid:
            print(json.dumps(r, indent=2))
            return 0
    print(f"Not found: {fid}", file=sys.stderr)
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description="Flow footprint builder")
    sub = p.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    pb.add_argument("--apply", action="store_true")
    pl = sub.add_parser("list")
    pl.add_argument("--verified", action="store_true")
    ps = sub.add_parser("show")
    ps.add_argument("ftg_id")
    args = p.parse_args()
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "show":
        return cmd_show(args.ftg_id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
