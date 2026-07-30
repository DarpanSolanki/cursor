#!/usr/bin/env python3
"""Portable process budget — kill child process group when wall exceeds --budget seconds.

Replaces reliance on GNU/uutils `timeout` (PATH/cargo-coreutils quirks caused
`timeout: failed to execute process` during gap-hunt). Exit 124 on kill (same as GNU).

Usage:
  with-budget.py --budget 5 -- sleep 60
  with-budget.py --budget 30 --label hook:kg-after-file-edit -- bash .cursor/hooks/kg-after-file-edit.sh
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser(prog="with-budget.py")
    ap.add_argument("--budget", type=float, required=True, help="Wall seconds before SIGTERM/SIGKILL")
    ap.add_argument("--label", default="", help="Short name for stderr note")
    ap.add_argument("--grace", type=float, default=2.0, help="Seconds between SIGTERM and SIGKILL")
    ap.add_argument("cmd", nargs=argparse.REMAINDER, help="Command after --")
    args = ap.parse_args()
    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("with-budget.py: missing command after --", file=sys.stderr)
        return 2
    budget = max(0.1, float(args.budget))
    label = args.label or cmd[0]
    # New session so killpg reaps the whole tree.
    preexec = os.setsid if hasattr(os, "setsid") else None
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, preexec_fn=preexec)
    try:
        while True:
            rc = proc.poll()
            if rc is not None:
                return int(rc)
            elapsed = time.monotonic() - t0
            if elapsed >= budget:
                print(
                    f"with-budget TIMEOUT: {label} exceeded {budget:.0f}s — killing pgid",
                    file=sys.stderr,
                    flush=True,
                )
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + max(0.1, float(args.grace))
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        return 124
                    time.sleep(0.05)
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
                return 124
            time.sleep(0.05)
    except KeyboardInterrupt:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
