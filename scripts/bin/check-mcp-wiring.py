#!/usr/bin/env python3
"""CLI wrapper — implementation lives in scripts/lib/mcp_wiring_gate.py."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from mcp_wiring_gate import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
