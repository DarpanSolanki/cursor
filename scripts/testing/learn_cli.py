#!/usr/bin/env python3
"""CLI for test-learn.sh — capture gotchas/correlators into learning bus + ntest hints."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/testing"))

from learning_bus import append_event, gotchas_for_api, load_events  # noqa: E402

HINTS = ROOT / "cursor-bundle/flow-test/test_hints.jsonl"


def _append_hint(api: str, kind: str, text: str, key: str | None = None, value: str | None = None) -> None:
    row = {"api": api, "kind": kind, "text": text}
    if key:
        row["key"] = key
    if value:
        row["value"] = value
    HINTS.parent.mkdir(parents=True, exist_ok=True)
    if not HINTS.is_file():
        HINTS.write_text("# Test hints — auto from test-learn.sh\n", encoding="utf-8")
    with HINTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def cmd_add(args: argparse.Namespace) -> int:
    api = args.api
    if args.kind == "gotcha":
        append_event(
            "gotcha",
            source="test-learn",
            api=api,
            detail=args.text,
            evidence=args.evidence,
        )
        _append_hint(api, "gotcha", args.text)
    elif args.kind == "correlator":
        append_event(
            "gotcha",
            source="test-learn",
            api=api,
            detail=f"{args.key}={args.value}",
            evidence=args.evidence,
            meta={"kind": "correlator", "key": args.key, "value": args.value},
        )
        _append_hint(api, "correlator", args.text or f"{args.key} must be set", key=args.key, value=args.value)
    else:
        append_event(
            "gotcha",
            source="test-learn",
            api=api,
            detail=args.text,
            evidence=args.evidence,
            meta={"kind": args.kind},
        )
        _append_hint(api, args.kind, args.text)
    print(json.dumps({"ok": True, "api": api, "kind": args.kind}))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    if args.api:
        rows = gotchas_for_api(args.api)
    else:
        rows = load_events(limit=args.limit, event_type="gotcha")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Capture test learning")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add", help="Add gotcha/correlator")
    pa.add_argument("--api", required=True)
    pa.add_argument("--kind", default="gotcha", choices=["gotcha", "correlator", "payload", "db"])
    pa.add_argument("--text", required=True)
    pa.add_argument("--key")
    pa.add_argument("--value")
    pa.add_argument("--evidence")
    pa.set_defaults(func=cmd_add)

    pl = sub.add_parser("list")
    pl.add_argument("--api")
    pl.add_argument("--limit", type=int, default=20)
    pl.set_defaults(func=cmd_list)

    args = p.parse_args()
    if args.cmd == "add" and args.kind == "correlator":
        if not args.key or not args.value:
            print("correlator requires --key and --value", file=sys.stderr)
            return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
