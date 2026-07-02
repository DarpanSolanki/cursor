#!/usr/bin/env python3
"""Workspace self-improvement backlog — status + safe auto-drain markers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "scripts/workspace-backlog.json"


def load() -> dict:
    if not BACKLOG.is_file():
        return {"version": 1, "items": []}
    return json.loads(BACKLOG.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    BACKLOG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def cmd_status(_: argparse.Namespace) -> int:
    data = load()
    items = data.get("items") or []
    open_n = sum(1 for i in items if i.get("status") not in ("done", "cancelled"))
    auto = [i for i in items if i.get("status") not in ("done", "cancelled") and i.get("auto_safe")]
    print(f"workspace-backlog: {open_n} open ({len(auto)} auto_safe)")
    for i in items:
        st = i.get("status", "?")
        flag = " [auto_safe]" if i.get("auto_safe") else ""
        perf = " [perf]" if i.get("perf") else ""
        print(f"  {i.get('id')}: {st}{flag}{perf} — {i.get('title')}")
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    data = load()
    for i in data.get("items") or []:
        if i.get("id") == args.id:
            i["status"] = args.status
            save(data)
            print(f"marked {args.id} → {args.status}")
            return 0
    print(f"unknown id: {args.id}", file=sys.stderr)
    return 1


def cmd_open_ids(_: argparse.Namespace) -> int:
    for i in load().get("items") or []:
        if i.get("status") not in ("done", "cancelled"):
            print(i.get("id", "?"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("open-ids")
    p.set_defaults(func=cmd_open_ids)
    p = sub.add_parser("mark")
    p.add_argument("id")
    p.add_argument("status", choices=("open", "in_progress", "done", "cancelled"))
    p.set_defaults(func=cmd_mark)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
