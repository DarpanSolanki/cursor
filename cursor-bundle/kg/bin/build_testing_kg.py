#!/usr/bin/env python3
"""Testing KG layer — FTG footprints + sources → KG test nodes linked to requests/contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
WORKSPACE = BIN.parents[1]
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
    flows = {r["id"]: r for r in load_jsonl(FLOW / "flows.jsonl")}
    footprints = load_jsonl(FLOW / "footprints.jsonl")
    contracts = {r["id"]: r for r in load_jsonl(FLOW / "contracts.jsonl")}

    emit({
        "t": "node",
        "id": "testing:layer",
        "kind": "testing",
        "label": "Flow Test Intelligence Layer",
        "repo": "cursor-bundle",
        "role": "FTG + footprints + sources",
        "src": "cursor-bundle/flow-test/",
    })

    for fp in footprints:
        fid = fp["ftg_id"]
        tid = f"test:{fid}"
        status = fp.get("status", "untested")
        emit({
            "t": "node",
            "id": tid,
            "kind": "test_flow",
            "label": fp.get("label", fid),
            "repo": fp.get("entry_service", ""),
            "role": status,
            "src": "footprints.jsonl",
            "coverage": fp.get("coverage"),
            "tier": fp.get("tier"),
            "verified": fp.get("verified"),
        })
        emit({
            "t": "edge",
            "from": "testing:layer",
            "to": tid,
            "rel": "includes",
            "src": "build_testing_kg.py",
        })
        req = fp.get("request")
        if req:
            emit({
                "t": "edge",
                "from": tid,
                "to": f"request:{req}",
                "rel": "proves",
                "note": f"status={status}",
                "src": "footprints.jsonl",
            })
        for api in fp.get("internal_apis") or []:
            emit({
                "t": "edge",
                "from": tid,
                "to": f"api:{api}",
                "rel": "exercises_api",
                "src": "footprints.jsonl",
            })
        for cid in fp.get("contracts") or []:
            if cid in contracts:
                emit({
                    "t": "edge",
                    "from": tid,
                    "to": cid,
                    "rel": "covers_contract",
                    "src": "footprints.jsonl",
                })
        flow = flows.get(fid, {})
        tests = flow.get("tests") or {}
        for ut in tests.get("unit") or []:
            emit({
                "t": "node",
                "id": f"test_unit:{ut}",
                "kind": "test_unit",
                "label": ut,
                "repo": "trustt-platform-accounting",
                "role": "junit",
                "src": "flows.jsonl",
            })
            emit({
                "t": "edge",
                "from": tid,
                "to": f"test_unit:{ut}",
                "rel": "uses_unit_test",
                "src": "flows.jsonl",
            })
        for nt in tests.get("ntest") or []:
            emit({
                "t": "node",
                "id": f"test_ntest:{nt}",
                "kind": "test_ntest",
                "label": nt,
                "repo": "scripts/testing",
                "role": "ntest_registry",
                "src": "registry.json",
            })
            emit({
                "t": "edge",
                "from": tid,
                "to": f"test_ntest:{nt}",
                "rel": "uses_ntest",
                "src": "flows.jsonl",
            })

    # Loan flows without FTG — link untested loan APIs
    for lf in load_jsonl(FLOW / "loan_flows.jsonl"):
        req = lf.get("request")
        if not req:
            continue
        ftg_ids = [fp["ftg_id"] for fp in footprints if fp.get("request") == req]
        if ftg_ids:
            continue
        uid = f"test:gap:{lf['repo']}:{req}"
        emit({
            "t": "node",
            "id": uid,
            "kind": "test_gap",
            "label": f"UNTESTED {req}",
            "repo": lf["repo"],
            "role": "gap",
            "src": "loan_flows.jsonl",
        })
        emit({
            "t": "edge",
            "from": uid,
            "to": f"request:{req}",
            "rel": "needs_test",
            "src": "loan_flows.jsonl",
        })


if __name__ == "__main__":
    main()
