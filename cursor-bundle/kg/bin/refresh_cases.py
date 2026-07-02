#!/usr/bin/env python3
"""
refresh_cases.py — re-ingest brain/changelog into kg.jsonl without rescanning orchestration.

Use when only cursor-bundle/brain/changelog/CHANGELOG.md changed (shipped fix audit).
Full graph rebuild: cursor-bundle/kg/bin/build.sh (code/orchestration drift).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
DATA = BIN.parent / "data"
JSONL = DATA / "kg.jsonl"
DB = DATA / "kg.db"
SEED = DATA / ".cases_seed.jsonl"


def _is_case_edge(o: dict) -> bool:
    rel = o.get("rel")
    fr = o.get("from", "")
    to = o.get("to", "")
    if fr.startswith("case:"):
        return True
    if rel == "hit_error" and fr.startswith("case:"):
        return True
    if rel == "touches" and fr.startswith("case:"):
        return True
    return False


def main() -> int:
    if not JSONL.exists():
        sys.stderr.write("kg.jsonl missing — run build.sh first\n")
        return 1

    nodes: list[dict] = []
    edges: list[dict] = []
    for line in JSONL.open(encoding="utf-8"):
        o = json.loads(line)
        if o["t"] == "node":
            if o.get("kind") in ("case", "error"):
                continue
            nodes.append(o)
        elif not _is_case_edge(o):
            edges.append(o)

    with SEED.open("w", encoding="utf-8") as fh:
        for n in nodes:
            fh.write(json.dumps(n, ensure_ascii=False) + "\n")

    proc = subprocess.run(
        [sys.executable, str(BIN / "build_cases.py"), str(SEED)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or "build_cases.py failed\n")
        return proc.returncode

    seen = {n["id"] for n in nodes}
    case_count = 0
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if o["t"] == "node":
            if o["id"] not in seen:
                nodes.append(o)
                seen.add(o["id"])
                if o.get("kind") == "case":
                    case_count += 1
        else:
            edges.append(o)

    with JSONL.open("w", encoding="utf-8") as out:
        for n in nodes:
            out.write(json.dumps(n, ensure_ascii=False) + "\n")
        for e in edges:
            out.write(json.dumps(e, ensure_ascii=False) + "\n")

    subprocess.run(
        [sys.executable, str(BIN / "build_db.py"), str(JSONL), str(DB)],
        check=True,
    )
    SEED.unlink(missing_ok=True)
    print(f"cases refreshed: {case_count} case node(s) from CHANGELOG → {JSONL.name} + {DB.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
