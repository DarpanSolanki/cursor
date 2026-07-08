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


def load_mentions() -> dict[str, str]:
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / ".cursor/skills/jira-fix-update/mentions.json"
    )
    raw = json.loads(path.read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def mention_node(account_id: str, text: str) -> dict[str, Any]:
    return {"type": "mention", "attrs": {"id": account_id, "text": text}}


def _paragraph_with_mentions(line: str, mentions: dict[str, str]) -> dict[str, Any]:
    """Turn '@Name ...' tokens into ADF mention nodes. Longest name first so
    'Sudheer Pandey' wins over 'Sudheer'. Unknown @tokens stay plain text."""
    import re

    names = sorted(mentions.keys(), key=len, reverse=True)
    alt = "|".join(re.escape(n) for n in names)
    pattern = re.compile(r"@(" + alt + r")\b", re.IGNORECASE)
    lower = {k.lower(): v for k, v in mentions.items()}

    content: list[dict[str, Any]] = []
    pos = 0
    for m in pattern.finditer(line):
        if m.start() > pos:
            content.append(text_node(line[pos : m.start()]))
        name = m.group(1)
        content.append(mention_node(lower[name.lower()], f"@{name}"))
        content.append(text_node(" "))
        pos = m.end()
        if pos < len(line) and line[pos] == " ":
            pos += 1
    if pos < len(line):
        content.append(text_node(line[pos:]))
    if not content:
        content = [text_node(line)]
    return {"type": "paragraph", "content": content}


def comment_doc(text: str, mentions: dict[str, str] | None = None) -> dict[str, Any]:
    """Build a comment ADF doc. Blank lines separate paragraphs; @Name tokens
    that match the mentions map become real mention nodes (markdown @ does not tag)."""
    if mentions is None:
        mentions = load_mentions()
    blocks: list[dict[str, Any]] = []
    buf: list[str] = []
    for ln in text.splitlines():
        if ln.strip() == "":
            if buf:
                blocks.append(_paragraph_with_mentions(" ".join(buf).strip(), mentions))
                buf = []
            continue
        buf.append(ln.rstrip())
    if buf:
        blocks.append(_paragraph_with_mentions(" ".join(buf).strip(), mentions))
    return doc(*(blocks or [paragraph(text)]))


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
        print("Usage: jira-fix-adf.py <rca|impact|dev|scenario_titles|test_result|prepost|micro|owners|comment|aitdp_remarks> ...", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "rca" and len(sys.argv) == 5:
        print(json.dumps(rca_doc(sys.argv[2], sys.argv[3], sys.argv[4])))
    elif cmd == "impact":
        bullets = sys.argv[2:]
        if not bullets:
            print("Usage: jira-fix-adf.py impact <bullet> ...", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(impact_doc(bullets)))
    elif cmd == "dev":
        scenarios = sys.argv[2:]
        if not scenarios:
            print("Usage: jira-fix-adf.py dev <scenario> ...", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(dev_scenarios_doc(scenarios)))
    elif cmd == "scenario_titles":
        titles = sys.argv[2:]
        print(json.dumps(dev_scenarios_doc(titles)))
    elif cmd == "test_result":
        text = sys.argv[2] if len(sys.argv) > 2 else "All dev scenarios: Pass."
        print(json.dumps(doc(paragraph(text))))
    elif cmd == "aitdp_remarks":
        text = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip()
        print(json.dumps(doc(paragraph(text))))
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
    elif cmd == "comment":
        raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
        print(json.dumps(comment_doc(raw)))
    else:
        print("See .cursor/skills/jira-fix-update/SKILL.md", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
