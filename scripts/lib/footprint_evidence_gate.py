"""Flag footprints claiming `verified` with no recorded run behind them.

`capture-flow.sh` writes `status: verified` from a command-line flag, so the money-proof
metric can be satisfied by appending a line. This compares each claim against the
`test_pass` events `ntest` actually emitted.

A footprint is *backed* when its request API has at least one recorded pass. Unbacked is
not proof of a lie — the run may predate the bus, or go through a runner that does not
record (disburse_loan_sanity.py) — but it is a claim resting on nobody's memory.

    python3 scripts/lib/footprint_evidence_gate.py            # report
    python3 scripts/lib/footprint_evidence_gate.py --strict   # exit 2 when unbacked grows
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOOTPRINTS = ROOT / "cursor-bundle/flow-test/footprints.jsonl"
BASELINE = Path(__file__).with_name("footprint_evidence_baseline.json")

sys.path.insert(0, str(ROOT / "scripts/testing"))


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


def audit() -> tuple[list[str], list[str]]:
    import run_evidence
    import scope_out

    ev = run_evidence.evidence()
    backed: list[str] = []
    unbacked: list[str] = []
    for row in _rows(FOOTPRINTS):
        if row.get("status") != "verified":
            continue
        api = row.get("request") or row.get("ftg_id") or "?"
        # Flows that are not live in production carry no proof debt.
        if scope_out.is_scope_out(api):
            continue
        if ev.get(api, {}).get("passes"):
            backed.append(api)
        else:
            unbacked.append(api)
    return sorted(backed), sorted(unbacked)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--accept", action="store_true")
    args = parser.parse_args(argv)

    backed, unbacked = audit()
    known = 0
    if BASELINE.is_file():
        known = json.loads(BASELINE.read_text()).get("unbacked_count", 0)

    if args.accept:
        BASELINE.write_text(
            json.dumps(
                {
                    "unbacked_count": len(unbacked),
                    "note": "Footprints claiming verified with no recorded run. Real runs shrink this; it must never grow.",
                },
                indent=1,
            )
            + "\n"
        )
        print(f"baseline accepted: {len(unbacked)} unbacked")
        return 0

    print(f"verified footprints: {len(backed) + len(unbacked)}  backed={len(backed)}  unbacked={len(unbacked)}")
    for api in unbacked:
        print(f"  UNBACKED {api}")
    if args.strict and len(unbacked) > known:
        print(f"\nunbacked grew {known} -> {len(unbacked)} — a verified claim was added without a run")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
