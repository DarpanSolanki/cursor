#!/usr/bin/env python3
"""Emit KG nodes/edges from test_map + test_coverage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
from _paths import WORKSPACE  # noqa: E402

FLOW = WORKSPACE / "cursor-bundle/flow-test"


def emit(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def main() -> None:
    emit({
        "t": "node",
        "id": "testing:ntest",
        "kind": "testing",
        "label": "ntest registry + test map",
        "repo": "scripts/testing",
        "role": "test_runner",
        "src": "scripts/testing/registry.json",
    })

    for row in load_jsonl(FLOW / "test_map.jsonl"):
        mid = row["id"]
        emit({
            "t": "node",
            "id": mid,
            "kind": "test_registry_case",
            "label": row["case_id"],
            "repo": row.get("service") or "scripts/testing",
            "role": row.get("tier"),
            "src": "test_map.jsonl",
            "money": row.get("money", False),
        })
        emit({"t": "edge", "from": "testing:ntest", "to": mid, "rel": "includes", "src": "build_test_map.py"})
        if row.get("api"):
            emit({"t": "edge", "from": mid, "to": f"request:{row['api']}", "rel": "tests_request", "src": "test_map.jsonl"})
        for fid in row.get("ftg_ids") or []:
            emit({"t": "edge", "from": mid, "to": f"test:{fid}", "rel": "covers_ftg", "src": "test_map.jsonl"})

    for row in load_jsonl(FLOW / "test_coverage.jsonl"):
        cid = row["id"]
        emit({
            "t": "node",
            "id": cid,
            "kind": "test_coverage",
            "label": row["api"],
            "repo": "cursor-bundle",
            "role": row.get("footprint_best", "?"),
            "src": "test_coverage.jsonl",
            "money": row.get("money", False),
        })
        emit({"t": "edge", "from": cid, "to": f"request:{row['api']}", "rel": "coverage_for", "src": "test_coverage.jsonl"})
        if row.get("gaps"):
            emit({
                "t": "edge",
                "from": cid,
                "to": f"test:gap:coverage:{row['api']}",
                "rel": "has_test_gap",
                "note": ",".join(row["gaps"]),
                "src": "test_coverage.jsonl",
            })


if __name__ == "__main__":
    main()
