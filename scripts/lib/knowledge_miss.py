"""What this session read that the workspace had no note on — the self-learning queue.

`knowledge-answer.py` answers a search when the index knows the term and stays silent
when it does not. Silence is the interesting half: it marks source that was read line by
line because nothing was written down. Recording only the hits made the loop look closed.

    python3 scripts/lib/knowledge_miss.py report          # top misses, newest window
    python3 scripts/lib/knowledge_miss.py report --since 2026-08-07
    python3 scripts/lib/knowledge_miss.py prune           # drop entries now indexed

A miss stops being a miss when someone writes the note — `prune` re-checks every recorded
probe against the current index and drops the ones that now resolve, so the queue shrinks
as knowledge is captured instead of growing forever like kg-grep-leak.jsonl did.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / ".cursor/knowledge-miss.jsonl"

sys.path.insert(0, str(ROOT / "scripts/lib"))


def _rows(since: str | None = None):
    if not LOG.is_file():
        return
    for line in LOG.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and (row.get("ts") or "") < since:
            continue
        yield row


def _resolved(probe: str) -> bool:
    import knowledge_index as ki
    return bool(ki.ask(ki.terms_from_command(probe)))


def report(since: str | None, limit: int) -> int:
    counts = collections.Counter(r.get("probe", "?") for r in _rows(since))
    if not counts:
        print("no recorded knowledge misses" + (f" since {since}" if since else ""))
        return 0
    print(f"{sum(counts.values())} miss events · {len(counts)} distinct probes"
          + (f" since {since}" if since else ""))
    for probe, n in counts.most_common(limit):
        print(f"  {n:4d}  {probe}")
    print("\nCapture what was learned: scripts/bin/learn.sh, or add it to the rule or brain "
          "doc that should have carried it. Then: knowledge_miss.py prune")
    return 0


def prune() -> int:
    rows = list(_rows())
    if not rows:
        print("nothing to prune")
        return 0
    keep = [r for r in rows if not _resolved(r.get("probe", ""))]
    LOG.write_text("".join(json.dumps(r) + "\n" for r in keep))
    print(f"pruned {len(rows) - len(keep)} of {len(rows)} — now indexed, no longer a gap")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--since")
    r.add_argument("--limit", type=int, default=15)
    sub.add_parser("prune")
    args = ap.parse_args(argv)
    return report(args.since, args.limit) if args.cmd == "report" else prune()


if __name__ == "__main__":
    sys.exit(main())
