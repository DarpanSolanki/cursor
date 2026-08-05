"""Flow definitions referencing registry cases that do not exist.

`flows.jsonl` lists the ntest cases that cover a flow, and the coverage map copies those
into `ntest_cases`. Nothing checked that the case exists, so a renamed or deleted case left
the flow still claiming coverage — `ntest run` answers "unknown case" while the map counts
it as proof.

    python3 scripts/lib/phantom_case_gate.py            # report
    python3 scripts/lib/phantom_case_gate.py --strict   # exit 2 when a new phantom appears
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOWS = ROOT / "cursor-bundle/flow-test/flows.jsonl"
REGISTRY = ROOT / "scripts/testing/registry.json"
BASELINE = Path(__file__).with_name("phantom_case_baseline.json")


def _rows(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def phantoms() -> dict[str, list[str]]:
    """flow id -> case ids it claims that the registry does not define."""
    try:
        reg = json.loads(REGISTRY.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, list[str]] = {}
    for flow in _rows(FLOWS):
        claimed = (flow.get("tests") or {}).get("ntest") or []
        missing = [c for c in claimed if c not in reg]
        if missing:
            out[flow.get("id", "?")] = sorted(missing)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--accept", action="store_true")
    args = parser.parse_args(argv)

    found = phantoms()
    total = sum(len(v) for v in found.values())
    known = 0
    if BASELINE.is_file():
        known = json.loads(BASELINE.read_text()).get("phantom_count", 0)

    if args.accept:
        BASELINE.write_text(
            json.dumps(
                {
                    "phantom_count": total,
                    "note": "Flow-claimed ntest cases missing from registry.json. Fixing a reference shrinks this; it must never grow.",
                },
                indent=1,
            )
            + "\n"
        )
        print(f"baseline accepted: {total} phantom reference(s)")
        return 0

    for flow_id, cases in sorted(found.items()):
        print(f"{flow_id}: {', '.join(cases)}")
    print(f"\n{total} phantom case reference(s) across {len(found)} flow(s)")
    if args.strict and total > known:
        print(f"phantom references grew {known} -> {total}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
