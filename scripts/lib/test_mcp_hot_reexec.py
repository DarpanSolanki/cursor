#!/usr/bin/env python3
"""Red→green: MCP hot-reexec must answer in-flight calls (Cursor).

Deferred design: flag in _maybe_hot_reexec, exec after flush in main(), and never
exec while stdin still has buffered lines (bulk smoke).

  python3 scripts/lib/test_mcp_hot_reexec.py
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "cursor-bundle/kg/mcp/kg_mcp_server.py"


def _rpc(msgs: list[dict], timeout: float = 60) -> list[dict]:
    stdin = "\n".join(json.dumps(m) for m in msgs) + "\n"
    e = {**os.environ, "KG_NO_AUTO_REBUILD": "1", "PYTHONUNBUFFERED": "1"}
    p = subprocess.run(
        [sys.executable, str(SERVER)],
        input=stdin,
        text=True,
        capture_output=True,
        timeout=timeout,
        cwd=str(ROOT),
        env=e,
    )
    out = []
    for line in (p.stdout or "").splitlines():
        if not line.strip():
            continue
        out.append(json.loads(line))
    return out


class HotReexecTest(unittest.TestCase):
    def test_batched_calls_all_answer(self) -> None:
        msgs = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "hot-reexec", "version": "1"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "kg_watermark", "arguments": {}},
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "kg_doctor", "arguments": {}},
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "kg_error", "arguments": {"query": "134207", "no_template": True}},
            },
        ]
        resp = _rpc(msgs)
        by_id = {o.get("id"): o for o in resp if o.get("id") is not None}
        for i in (2, 3, 4):
            self.assertIn(i, by_id, f"missing response id={i}")
            text = ((by_id[i].get("result") or {}).get("content") or [{}])[0].get("text") or ""
            self.assertTrue(text.strip(), f"call id={i} empty — hot-reexec dropped response")

    def test_deferred_flag_not_immediate_execv_in_maybe(self) -> None:
        src = SERVER.read_text(encoding="utf-8")
        self.assertIn("_PENDING_REEXEC", src)
        self.assertIn("def _reexec_now", src)
        self.assertIn("def _stdin_has_pending", src)
        self.assertIn("buffer", src)
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "_maybe_hot_reexec":
                for child in ast.walk(node):
                    if isinstance(child, ast.Attribute) and child.attr == "execv":
                        self.fail("_maybe_hot_reexec must not call os.execv (defer to main)")
                break
        else:
            self.fail("_maybe_hot_reexec missing")

    def test_smoke_does_not_disable_hot_reexec(self) -> None:
        smoke = ROOT / "scripts/bin/kg-mcp-smoke.sh"
        text = smoke.read_text(encoding="utf-8")
        self.assertNotIn('"KG_MCP_NO_HOT_REEXEC"', text)
        self.assertNotIn("'KG_MCP_NO_HOT_REEXEC'", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
