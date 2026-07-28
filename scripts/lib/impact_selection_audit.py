#!/usr/bin/env python3
"""Ground-truth replay: compare resolver selection vs KG-derived SHOULD for real diffs."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from impact_tests import build_plan  # noqa: E402

KG_DB = ROOT / "cursor-bundle/kg/data/kg.db"
REGISTRY = ROOT / "scripts/testing/registry.json"


def _recent_diffs(n: int = 10) -> list[dict]:
    """Collect recent commit diffs from service repos."""
    out: list[dict] = []
    repos = sorted(ROOT.glob("trustt-*")) + sorted(ROOT.glob("novopay-*"))
    if (ROOT / ".git").is_dir():
        repos = [ROOT] + list(repos)
    for repo in repos:
        if not (repo / ".git").is_dir():
            continue
        r = subprocess.run(
            ["git", "-C", str(repo), "log", "-3", "--pretty=format:%H", "--name-only"],
            capture_output=True,
            text=True,
            check=False,
        )
        prefix = "" if repo == ROOT else f"{repo.name}/"
        commit = ""
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
                commit = line[:12]
                files: list[str] = []
                continue
            if commit and line:
                files.append(prefix + line)
                if len(files) >= 5:
                    out.append({"repo": repo.name if repo != ROOT else "sliProd", "commit": commit, "files": files})
                    commit = ""
                    if len(out) >= n:
                        return out
        if commit and files:
            out.append({"repo": repo.name if repo != ROOT else "sliProd", "commit": commit, "files": files})
            if len(out) >= n:
                return out
    return out[:n]


def _kg_should_cases(paths: list[str]) -> set[str]:
    """Fresh KG path: files → flows → registry cases (ignore resolver)."""
    plan = build_plan(paths=paths, from_pending=False, shipped_only=False)
    apis = {f.get("api") for f in plan.get("flows") or []}
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.is_file() else {}
    cases: set[str] = set(plan.get("ordered_cases") or [])
    for cid, meta in reg.items():
        if isinstance(meta, dict) and meta.get("api") in apis:
            cases.add(cid)
    return cases


def _verdict(chosen: set[str], should: set[str]) -> str:
    if not chosen and should:
        return "EMPTY-WRONG"
    if chosen == should:
        return "RIGHT"
    if chosen > should:
        return "OVER"
    if chosen < should:
        return "UNDER"
    if chosen != should:
        return "UNDER" if len(chosen) < len(should) else "OVER"
    return "RIGHT"


def main() -> int:
    diffs = _recent_diffs(10)
    if not diffs:
        print("no diffs found")
        return 1
    print("| # | repo@commit | files | resolver | should | verdict |")
    print("|---|-------------|-------|----------|--------|---------|")
    counts = {"RIGHT": 0, "OVER": 0, "UNDER": 0, "EMPTY-WRONG": 0}
    for i, d in enumerate(diffs, 1):
        paths = [p for p in d["files"] if p.endswith((".java", ".xml", ".py", ".sh"))]
        if not paths:
            continue
        plan = build_plan(paths=paths, from_pending=False, shipped_only=True)
        chosen = set(plan.get("ordered_cases") or [])
        should = _kg_should_cases(paths)
        v = _verdict(chosen, should)
        counts[v] = counts.get(v, 0) + 1
        label = f"{d['repo']}@{d['commit'][:8]}"
        print(
            f"| {i} | {label} | {len(paths)} | {len(chosen)} | {len(should)} | {v} |"
        )
    print(f"\nclass_counts: {json.dumps(counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
