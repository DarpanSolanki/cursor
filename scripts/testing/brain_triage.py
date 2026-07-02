#!/usr/bin/env python3
"""Triage cursor-bundle/brain/discoveries/INBOX.md."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INBOX = ROOT / "cursor-bundle/brain/discoveries/INBOX.md"
GAPS = ROOT / ".cursor/gaps-and-risks.md"


def list_entries() -> list[dict]:
    if not INBOX.is_file():
        return []
    text = INBOX.read_text(encoding="utf-8")
    entries = []
    for m in re.finditer(r"^## (DISC-\d+-[\d]+) — (.+)$", text, re.M):
        block = text[m.start():]
        nxt = re.search(r"\n## DISC-", block[10:])
        block = block[: 10 + nxt.start()] if nxt else block
        entries.append({"id": m.group(1), "title": m.group(2), "block": block.strip()})
    return entries


def cmd_list(_: argparse.Namespace) -> int:
    entries = list_entries()
    if not entries:
        print("INBOX empty")
        return 0
    for e in entries:
        print(f"{e['id']}: {e['title']}")
    print(f"\n{len(entries)} item(s) — triage via promote/dismiss")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    entries = {e["id"]: e for e in list_entries()}
    if args.disc_id not in entries:
        print(f"not found: {args.disc_id}", file=sys.stderr)
        return 1
    e = entries[args.disc_id]
    gap_id = args.gap_id or f"GAP-{datetime.now(timezone.utc).strftime('%m%d')}"
    row = (
        f"\n| {gap_id} | Medium | Open | {e['title']} | "
        f"INBOX {args.disc_id} | cursor-bundle/brain/discoveries/INBOX.md |\n"
    )
    if GAPS.is_file() and gap_id in GAPS.read_text(encoding="utf-8"):
        print(f"{gap_id} already in gaps file", file=sys.stderr)
        return 1
    with GAPS.open("a", encoding="utf-8") as f:
        f.write(row)
    _mark_inbox(args.disc_id, f"PROMOTED → {gap_id}")
    print(f"Promoted {args.disc_id} as {gap_id} in .cursor/gaps-and-risks.md")
    return 0


def cmd_dismiss(args: argparse.Namespace) -> int:
    if args.disc_id not in {e["id"] for e in list_entries()}:
        print(f"not found: {args.disc_id}", file=sys.stderr)
        return 1
    _mark_inbox(args.disc_id, f"DISMISSED: {args.reason}")
    print(f"Dismissed {args.disc_id}")
    return 0


def _mark_inbox(disc_id: str, note: str) -> None:
    text = INBOX.read_text(encoding="utf-8")
    marker = f"## {disc_id} —"
    idx = text.find(marker)
    if idx < 0:
        return
    insert = f"\n- **Triage note:** {note} ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})\n"
    end = text.find("\n## DISC-", idx + 1)
    if end < 0:
        INBOX.write_text(text + insert, encoding="utf-8")
    else:
        INBOX.write_text(text[:end] + insert + text[end:], encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    pp = sub.add_parser("promote")
    pp.add_argument("disc_id")
    pp.add_argument("--gap-id")
    pd = sub.add_parser("dismiss")
    pd.add_argument("disc_id")
    pd.add_argument("--reason", default="not confirmed")
    args = p.parse_args()
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "promote":
        return cmd_promote(args)
    if args.cmd == "dismiss":
        return cmd_dismiss(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
