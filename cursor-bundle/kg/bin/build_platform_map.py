#!/usr/bin/env python3
"""Emit KG nodes/edges from platform_map + loan_flows + batch_jobs + kafka_index."""

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
    for row in load_jsonl(FLOW / "platform_map.jsonl"):
        rid = row["id"]
        emit({
            "t": "node",
            "id": rid,
            "kind": "platform_api",
            "label": row["request"],
            "repo": row["repo"],
            "role": row.get("category"),
            "src": "cursor-bundle/flow-test/platform_map.jsonl",
            "category": row.get("category"),
            "money": row.get("money", False),
        })
        emit({
            "t": "edge",
            "from": f"service:{row['repo']}",
            "to": rid,
            "rel": "exposes",
            "src": "platform_map.jsonl",
        })
        if row.get("kg_request"):
            emit({
                "t": "edge",
                "from": rid,
                "to": row["kg_request"],
                "rel": "maps_to",
                "src": "platform_map.jsonl",
            })

    for row in load_jsonl(FLOW / "loan_flows.jsonl"):
        emit({
            "t": "node",
            "id": f"loan_flow:{row.get('request', row['id'])}",
            "kind": "loan_flow",
            "label": row.get("request") or row.get("job_name"),
            "repo": row["repo"],
            "role": row.get("flow_type", "loan_account"),
            "src": "cursor-bundle/flow-test/loan_flows.jsonl",
            "money": True,
        })

    for row in load_jsonl(FLOW / "batch_jobs.jsonl"):
        jid = row["id"]
        emit({
            "t": "node",
            "id": jid,
            "kind": "batch_job",
            "label": row["job_name"],
            "repo": row["repo"],
            "role": "spring_batch",
            "src": row.get("src", "batch_jobs.jsonl"),
            "money": row.get("money", False),
        })
        emit({
            "t": "edge",
            "from": f"service:{row['repo']}",
            "to": jid,
            "rel": "runs_job",
            "src": row.get("src", ""),
        })
        if row.get("request"):
            emit({
                "t": "edge",
                "from": jid,
                "to": f"request:{row['request']}",
                "rel": "triggers",
                "src": row.get("src", ""),
            })

    for row in load_jsonl(FLOW / "kafka_index.jsonl"):
        kid = row["id"]
        emit({
            "t": "node",
            "id": kid,
            "kind": "kafka_topic",
            "label": row.get("topic_prefix", ""),
            "repo": row["repo"],
            "role": row.get("protocol"),
            "src": row.get("src", "kafka_index.jsonl"),
            "money": row.get("money", False),
        })


if __name__ == "__main__":
    main()
