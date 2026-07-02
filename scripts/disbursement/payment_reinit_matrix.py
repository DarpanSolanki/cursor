#!/usr/bin/env python3
"""Payment reinitiation matrix — JLG (NEFT v1 + MFT) and SHG parent (MFT).

Uses fast stage suite (fail-fast waits, predisburse API + REINITIATE_BANK).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLOWS = ("jlg", "jlg_mft", "shg")

if __name__ == "__main__":
    cmd = [
        sys.executable,
        str(HERE / "regression_driver.py"),
        "--stage-suite", "fast",
        "--neft-version", "v1",
        "--no-preflight",
        "--sanity-timeout-s", "150",
    ]
    for f in FLOWS:
        cmd.extend(["--flow", f])
    raise SystemExit(subprocess.call(cmd, cwd=str(HERE)))
