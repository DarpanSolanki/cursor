#!/usr/bin/env python3
"""Cached orchestration apiName index — avoid rglob on hot paths."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "cursor-bundle/flow-test/orch_api_index.json"

MONEY_RE = re.compile(
    r"disburse|repay|prepay|foreclos|writeoff|billing|accrual|dpi|collection|"
    r"provision|closure|cancel|neft|posting|transaction|loan",
    re.I,
)


def _orch_mtime_max() -> float:
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
            try:
                mx = max(mx, xml.stat().st_mtime)
            except OSError:
                pass
    return mx


def _scan() -> dict[str, str]:
    apis: dict[str, str] = {}
    for repo in sorted(ROOT.glob("novopay-*")) + sorted(ROOT.glob("trustt-*")):
        if not repo.is_dir():
            continue
        orch = repo / "deploy/application/orchestration"
        if not orch.is_dir():
            continue
        for xml in orch.rglob("*.xml"):
            try:
                text = xml.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in re.finditer(r'<Request\s+name="([^"]+)"', text):
                name = m.group(1)
                if name not in apis:
                    apis[name] = repo.name
    return apis


def load_index(*, force_rebuild: bool = False) -> dict:
    """Return {apis: {api: repo}, built_at, orch_mtime_max, count, money_count}."""
    orch_max = _orch_mtime_max()
    if not force_rebuild and INDEX_PATH.is_file():
        try:
            data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if float(data.get("orch_mtime_max") or 0) >= orch_max - 0.001:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    apis = _scan()
    money = sum(1 for a in apis if MONEY_RE.search(a))
    data = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "orch_mtime_max": orch_max,
        "count": len(apis),
        "money_count": money,
        "apis": apis,
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def apis_map(*, force_rebuild: bool = False) -> dict[str, str]:
    return load_index(force_rebuild=force_rebuild).get("apis") or {}


def is_money_api(name: str) -> bool:
    return bool(MONEY_RE.search(name))


def registry_gaps(*, money_only: bool = False, force_rebuild: bool = False) -> list[tuple[str, str]]:
    from pathlib import Path

    reg_path = ROOT / "scripts/testing/registry.json"
    reg: set[str] = set()
    if reg_path.is_file():
        raw = json.loads(reg_path.read_text(encoding="utf-8"))
        for cid, case in raw.items():
            if cid.startswith("_") or not isinstance(case, dict):
                continue
            if case.get("api"):
                reg.add(case["api"])
            for a in case.get("apis") or []:
                reg.add(a)
    orch = apis_map(force_rebuild=force_rebuild)
    missing = sorted(set(orch) - reg)
    if money_only:
        missing = [a for a in missing if is_money_api(a)]
    return [(a, orch.get(a, "?")) for a in missing]


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Orchestration API index cache")
    p.add_argument("--rebuild", action="store_true")
    p.add_argument("--stats", action="store_true")
    args = p.parse_args()
    data = load_index(force_rebuild=args.rebuild)
    if args.stats or not args.rebuild:
        print(json.dumps({
            "path": str(INDEX_PATH.relative_to(ROOT)),
            "count": data.get("count"),
            "money_count": data.get("money_count"),
            "built_at": data.get("built_at"),
        }, indent=2))
    else:
        print(f"Rebuilt {data.get('count')} apis → {INDEX_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
