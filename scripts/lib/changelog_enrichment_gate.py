"""Every shipped ticket in `.cursor/changelog.md` must also reach the brain CHANGELOG.

The workspace changelog is the human record; the brain CHANGELOG is what `kg cases` /
`kg enhance` read to turn a shipped fix into precedent for the next agent. A ticket in
the first and not the second is a fix nobody will find again.

    python3 scripts/lib/changelog_enrichment_gate.py            # report
    python3 scripts/lib/changelog_enrichment_gate.py --strict   # exit 2 when a NEW gap appears
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / ".cursor/changelog.md"
BRAIN = ROOT / "cursor-bundle/brain/changelog/CHANGELOG.md"
BASELINE = Path(__file__).with_name("changelog_enrichment_baseline.json")
TICKET = re.compile(r"\b((?:TDPQA|SDCP)-\d+)\b")


def _sort_key(ticket: str) -> tuple[str, int]:
    project, number = ticket.split("-")
    return project, int(number)


def gaps() -> list[str]:
    workspace = TICKET.findall(WORKSPACE.read_text()) if WORKSPACE.exists() else []
    brain = set(TICKET.findall(BRAIN.read_text())) if BRAIN.exists() else set()
    return sorted(set(workspace) - brain, key=_sort_key)


def baseline() -> set[str]:
    if not BASELINE.exists():
        return set()
    return set(json.loads(BASELINE.read_text()).get("known_gaps", []))


def heading_for(ticket: str) -> str:
    if not WORKSPACE.exists():
        return ""
    match = re.search(rf"^## .*{re.escape(ticket)}.*$", WORKSPACE.read_text(), re.M)
    return match.group(0)[3:].strip() if match else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit 2 on a gap outside the baseline")
    parser.add_argument("--accept", action="store_true", help="rewrite the baseline to the current gaps")
    args = parser.parse_args(argv)

    current = gaps()
    known = baseline()

    if args.accept:
        BASELINE.write_text(
            json.dumps(
                {
                    "known_gaps": current,
                    "note": "Historical entries missing from the brain CHANGELOG. Backfill shrinks this list; it must never grow.",
                },
                indent=1,
            )
            + "\n"
        )
        print(f"baseline accepted: {len(current)} known gap(s)")
        return 0

    fresh = [ticket for ticket in current if ticket not in known]
    for ticket in current:
        marker = "NEW" if ticket in fresh else "known"
        print(f"{marker:6s} {ticket:12s} {heading_for(ticket)[:80]}")
    print(f"\n{len(current)} ticket(s) in .cursor/changelog.md with no brain CHANGELOG entry ({len(fresh)} new)")
    if fresh:
        print("Add via scripts/bin/changelog-add.sh so `kg cases` can surface them as precedent.")
    if args.strict and fresh:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
