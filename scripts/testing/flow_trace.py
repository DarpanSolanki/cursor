#!/usr/bin/env python3
"""Unified cross-repo flow trace — one view for RCA, onboarding, gap analysis."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle/flow-test"
REGISTRY = ROOT / "scripts/testing/registry.json"
KG = ROOT / "cursor-bundle/kg/bin/kg.py"

MONEY_KW = re.compile(
    r"disburse|repay|prepay|foreclos|writeoff|billing|accrual|dpi|collection|"
    r"provision|closure|cancel.*loan|neft|posting|transaction",
    re.I,
)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _kg(cmd: str, *args: str, limit: int = 1600) -> str:
    if not KG.is_file():
        return "(kg missing)"
    try:
        p = subprocess.run(
            [sys.executable, str(KG), "--no-drift-check", cmd, *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return ((p.stdout or p.stderr) or "").strip()[:limit]
    except Exception as ex:
        return f"(kg error: {ex})"


def _platform_row(api: str) -> dict | None:
    for row in _load_jsonl(FLOW / "platform_map.jsonl"):
        if row.get("request") == api:
            return row
    return None


def _chain_row(api: str) -> dict | None:
    for row in _load_jsonl(FLOW / "chains.jsonl"):
        if row.get("request") == api:
            return row
    return None


def _registry_cases(api: str) -> list[tuple[str, dict]]:
    if not REGISTRY.is_file():
        return []
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    hits: list[tuple[str, dict]] = []
    for cid, case in raw.items():
        if cid.startswith("_"):
            continue
        if case.get("api") == api or api in (case.get("apis") or []):
            hits.append((cid, case))
    return hits


def _upstream_contracts(api: str) -> list[dict]:
    hits: list[dict] = []
    for row in _load_jsonl(FLOW / "contracts.jsonl"):
        consumer = row.get("consumer") or {}
        if consumer.get("request") == api or consumer.get("api") == api:
            hits.append(row)
    return hits[:12]


def _downstream_contracts(api: str) -> list[dict]:
    hits: list[dict] = []
    for row in _load_jsonl(FLOW / "contracts.jsonl"):
        producer = row.get("producer") or {}
        if producer.get("request") == api:
            hits.append(row)
    return hits[:12]


def _coverage(api: str) -> dict | None:
    for row in _load_jsonl(FLOW / "test_coverage.jsonl"):
        if row.get("api") == api:
            return row
    return None


def _ftg_rows(api: str) -> list[dict]:
    return [r for r in _load_jsonl(FLOW / "flows.jsonl") if r.get("request") == api]


def trace(api: str, *, fast: bool = False) -> str:
    lines = [f"# Flow trace: `{api}`", ""]
    pm = _platform_row(api)
    if pm:
        lines.append(
            f"**Owner:** `{pm.get('repo', '?').split('/')[-1]}` · "
            f"category={pm.get('category')} · money={pm.get('money')} · "
            f"multi_service={pm.get('multi_service')}"
        )
    else:
        lines.append("**Owner:** NOT in platform_map — run `sync-test-intelligence.sh --quick`")

    reg = _registry_cases(api)
    lines.append(f"**Registry:** {len(reg)} case(s)" + (f" — {', '.join(c[0] for c in reg[:5])}" if reg else " — **NONE**"))

    cov = _coverage(api)
    if cov:
        lines.append(
            f"**Test proof:** footprint={cov.get('footprint_best')} gaps={cov.get('gaps')} "
            f"tiers={cov.get('tiers')}"
        )
    else:
        lines.append("**Test proof:** no test_coverage row")

    lines.extend(["", "## Upstream (calls this api)"])
    ups = _upstream_contracts(api)
    if ups:
        for c in ups:
            prod = c.get("producer") or {}
            lines.append(
                f"- `{prod.get('repo', '?').split('/')[-1]}:{prod.get('request', prod.get('class', '?'))}` "
                f"→ {c.get('protocol')} ({c.get('id', '')[:48]})"
            )
    else:
        lines.append("- (none indexed — grep Java `callInternalAPI` or check gateway)")

    lines.extend(["", "## In-service spine"])
    ch = _chain_row(api)
    if ch:
        procs = ch.get("processors") or []
        xapis = ch.get("cross_service_apis") or ch.get("internal_apis") or []
        lines.append(f"- Processors: **{len(procs)}** · XML internal APIs: **{len(xapis)}**")
        if procs and not fast:
            lines.append(f"- First: `{procs[0]}` … last: `{procs[-1]}`")
        if xapis and not fast:
            lines.append(f"- XML APIs: {', '.join(str(x) for x in xapis[:8])}")
    else:
        lines.append("- No chains.jsonl row — in-service only via KG below")

    if not fast:
        lines.extend(["", "### KG flow (truncated)", "```", _kg("flow", api), "```"])

    lines.extend(["", "## Downstream (this api calls)"])
    downs = _downstream_contracts(api)
    if downs:
        for c in downs:
            cons = c.get("consumer") or {}
            lines.append(
                f"- → `{cons.get('repo', '?').split('/')[-1]}:{cons.get('request', '?')}` "
                f"({c.get('protocol')})"
            )
    else:
        lines.append("- (none in contracts.jsonl)")

    ftgs = _ftg_rows(api)
    if ftgs:
        lines.extend(["", "## FTG"])
        for f in ftgs[:4]:
            t = f.get("tests") or {}
            lines.append(
                f"- `{f['id']}` tier={f.get('tier')} coverage={f.get('coverage')} "
                f"unit={len(t.get('unit') or [])} ntest={len(t.get('ntest') or [])}"
            )

    lines.extend([
        "",
        "## Next commands",
        "```bash",
        f"super-agent.sh orient {api} --fast",
        f"ntest auto {api}          # if registry case exists",
        f"flow-onboard.sh {api}      # scaffold registry + e2e if missing",
        f"python3 scripts/testing/ftg.py registry-gaps --money | rg {api} || true",
        "scripts/db-local.sh --canned 01-loan-status-by-lan --param account_number=$ACCOUNT_NUMBER",
        "```",
    ])
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Unified flow trace")
    p.add_argument("api", help="apiName / Request name")
    p.add_argument("--fast", action="store_true", help="Skip full KG flow block")
    p.add_argument("--json", action="store_true", help="Minimal JSON summary")
    args = p.parse_args()

    if args.json:
        api = args.api
        print(json.dumps({
            "api": api,
            "platform": _platform_row(api),
            "registry_cases": [c[0] for c in _registry_cases(api)],
            "coverage": _coverage(api),
            "upstream_count": len(_upstream_contracts(api)),
            "downstream_count": len(_downstream_contracts(api)),
            "chain_processors": len((_chain_row(api) or {}).get("processors") or []),
        }, indent=2))
        return 0

    print(trace(args.api, fast=args.fast))
    return 0


if __name__ == "__main__":
    sys.exit(main())
