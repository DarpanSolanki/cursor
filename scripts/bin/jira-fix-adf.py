#!/usr/bin/env python3
"""Build ADF payloads for SDCP JIRA fix handoff fields. No API calls."""

from __future__ import annotations

import json
import sys
from typing import Any


def text_node(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def paragraph(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": [text_node(text)]}


def bullet_list(items: list[str]) -> dict[str, Any]:
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [paragraph(item)],
            }
            for item in items
        ],
    }


def ordered_list(items: list[str]) -> dict[str, Any]:
    return {
        "type": "orderedList",
        "content": [
            {
                "type": "listItem",
                "content": [paragraph(item)],
            }
            for item in items
        ],
    }


def doc(*blocks: dict[str, Any]) -> dict[str, Any]:
    return {"type": "doc", "version": 1, "content": list(blocks)}


def rca_doc(situation: str, cause: str, resolution: str) -> dict[str, Any]:
    return doc(paragraph(situation), paragraph(cause), paragraph(resolution))


def impact_doc(bullets: list[str]) -> dict[str, Any]:
    return doc(bullet_list(bullets))


def dev_scenarios_doc(scenarios: list[str]) -> dict[str, Any]:
    return doc(ordered_list(scenarios))


def pre_post_doc(
    pre: str = "NA", post: str = "NA"
) -> dict[str, Any]:
    return doc(
        paragraph(f"Pre deployment: {pre}"),
        paragraph(f"Post deployment: {post}"),
    )


def micro_service_field(option_ids: list[str]) -> list[dict[str, str]]:
    return [{"id": oid} for oid in option_ids]


# Option ids — keep in sync with fields-reference.md
MICRO = {
    "accounting": "11843",
    "los": "11844",
    "payments": "11842",
    "actor": "11845",
    "batch": "11850",
    "lib": "11848",
    "task": "11840",
    "api_gateway": "11851",
    "approval": "11852",
    "audit": "11853",
    "authorization": "11854",
    "reporting": "11847",
    "bpmn": "11846",
    "android": "11849",
    "initial_setup": "11841",
}


def load_default_owners() -> dict[str, Any]:
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / ".cursor/skills/jira-fix-update/owners-defaults.json"
    raw = json.loads(path.read_text())
    out: dict[str, Any] = {}
    for key, val in raw.items():
        if key.startswith("_"):
            continue
        if isinstance(val, list):
            out[key] = [{"accountId": u["accountId"]} for u in val]
        elif isinstance(val, dict):
            out[key] = {"accountId": val["accountId"]}
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: jira-fix-adf.py <rca|impact|dev|prepost|micro|owners> ...", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "rca" and len(sys.argv) == 5:
        print(json.dumps(rca_doc(sys.argv[2], sys.argv[3], sys.argv[4])))
    elif cmd == "prepost":
        pre = sys.argv[2] if len(sys.argv) > 2 else "NA"
        post = sys.argv[3] if len(sys.argv) > 3 else "NA"
        print(json.dumps(pre_post_doc(pre, post)))
    elif cmd == "micro":
        keys = sys.argv[2:]
        ids = [MICRO[k] for k in keys]
        print(json.dumps(micro_service_field(ids)))
    elif cmd == "owners":
        print(json.dumps(load_default_owners(), indent=2))
    else:
        print("See .cursor/skills/jira-fix-update/SKILL.md", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
