#!/usr/bin/env python3
"""DCF fixture CLI — thin wrapper over flowtest.fixture (profile=dcf_group).

Keeps existing schema names: dcf_bak_<parent_lan>.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/testing"))

from flowtest.fixture import drop, restore, snapshot, verify  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402

__doc__ = """
DCF fixture snapshot / restore — retest the SAME group LANs repeatably.

Usage:
  python3 scripts/dcf_sanity/dcf_fixture_backup.py snapshot <parent_lan>
  python3 scripts/dcf_sanity/dcf_fixture_backup.py restore  <parent_lan>
  python3 scripts/dcf_sanity/dcf_fixture_backup.py verify   <parent_lan>
  python3 scripts/dcf_sanity/dcf_fixture_backup.py drop     <parent_lan>
"""


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("snapshot", "restore", "verify", "drop"):
        print(__doc__)
        return 2
    op, parent = sys.argv[1], sys.argv[2]
    {"snapshot": snapshot, "restore": restore, "verify": verify, "drop": drop}[op](
        parent, DCF_GROUP
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
