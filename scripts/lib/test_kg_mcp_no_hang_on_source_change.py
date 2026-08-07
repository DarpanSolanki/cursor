#!/usr/bin/env python3
"""Every MCP request must get a response, including the one that triggers hot-reload.

The server re-execs itself when kg.py or the server file changes on disk. That exec used
to run inside tools/call handling, before the response was written: the client kept
waiting on a request id the replaced process had never seen. Editing kg.py cost the very
next MCP call, every time — the hang the user hit three or four times.

The old hot-reload test asserted that the string "os.execv" appeared in the source, so it
passed throughout. This one drives the real protocol over pipes and fails on a lost id.

    python3 scripts/lib/test_kg_mcp_no_hang_on_source_change.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "cursor-bundle/kg/mcp/kg_mcp_server.py"
TRACKED = ROOT / "cursor-bundle/kg/bin/kg.py"
DEADLINE_S = 25.0


def _send(proc, msg: dict) -> None:
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def _await_id(proc, want: int, deadline_s: float = DEADLINE_S) -> dict | None:
    end = time.time() + deadline_s
    while time.time() < end:
        line = proc.stdout.readline()
        if not line:
            return None
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want:
            return msg
    return None


def main() -> int:
    env = dict(os.environ, CURSOR_PROJECT_DIR=str(ROOT), KG_MCP_TOOL_TIMEOUT="10")
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, cwd=str(ROOT), env=env,
    )
    fails = 0

    def chk(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        print(f"  {'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            fails += 1

    try:
        _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        chk("initialize answered", _await_id(proc, 1) is not None)

        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                     "params": {"name": "kg_watermark", "arguments": {}}})
        chk("call before source change answered", _await_id(proc, 2) is not None)

        # The trigger: a tracked source file changes while the server is live.
        os.utime(TRACKED, None)

        _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": "kg_watermark", "arguments": {}}})
        got = _await_id(proc, 3)
        chk("call that triggers hot-reload is still answered", got is not None,
            "" if got else "no response for id 3 — the exec ate the request")

        # And the replaced process must keep serving.
        _send(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                     "params": {"name": "kg_watermark", "arguments": {}}})
        chk("server still serving after re-exec", _await_id(proc, 4) is not None)
    finally:
        proc.kill()
        proc.wait(timeout=10)

    print(f"=== DONE fails={fails} ===")
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
