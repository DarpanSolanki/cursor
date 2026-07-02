#!/usr/bin/env python3
"""Cross-layer KG edges — test_coverage ↔ test_flow ↔ test_registry ↔ precedents."""

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
        "id": "superagent:layer",
        "kind": "superagent",
        "label": "Unified intelligence layer (KG + test KG + bus)",
        "repo": "cursor-bundle",
        "role": "orchestrator",
        "src": "scripts/testing/super_agent.py",
    })

    for row in load_jsonl(FLOW / "test_coverage.jsonl"):
        cid = row["id"]
        emit({"t": "edge", "from": "superagent:layer", "to": cid, "rel": "indexes", "src": "build_cross_learn.py"})
        for fid in row.get("ftg_ids") or []:
            emit({"t": "edge", "from": cid, "to": f"test:{fid}", "rel": "links_ftg", "src": "build_cross_learn.py"})
        for nid in row.get("ntest_cases") or []:
            emit({"t": "edge", "from": cid, "to": f"map:registry:{nid}", "rel": "links_ntest", "src": "build_cross_learn.py"})

    for row in load_jsonl(FLOW / "test_map.jsonl"):
        mid = row["id"]
        emit({"t": "edge", "from": "superagent:layer", "to": mid, "rel": "indexes", "src": "build_cross_learn.py"})
        if row.get("chain_id"):
            emit({"t": "edge", "from": mid, "to": row["chain_id"], "rel": "uses_chain", "src": "build_cross_learn.py"})

    # testing layer nodes → superagent
    for kind in ("testing:layer", "testing:ntest"):
        emit({"t": "edge", "from": "superagent:layer", "to": kind, "rel": "unifies", "src": "build_cross_learn.py"})


if __name__ == "__main__":
    main()
