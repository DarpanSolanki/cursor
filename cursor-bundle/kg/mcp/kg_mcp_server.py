#!/usr/bin/env python3
"""trustt-kg MCP server — thin stdio wrapper around cursor-bundle/kg/bin/kg.py.

No business logic duplication: every tool shells out to kg.py.
Official MCP SDK optional; this file implements minimal JSON-RPC 2.0 stdio
(initialize, tools/list, tools/call) with zero external deps.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # sliProd
KG_PY = ROOT / "cursor-bundle" / "kg" / "bin" / "kg.py"
MAX_CHARS = 10_000
TRUNC_MARK = "\n\n… [truncated — refine query / narrower args; max 10000 chars] …\n"

SERVER_INFO = {"name": "trustt-kg", "version": "1.0.0"}
PROTOCOL = "2024-11-05"

# READ-ONLY tools only — map MCP name → kg.py argv prefix
TOOLS = {
    "kg_orient": {
        "description": "Orient on an apiName/request: flow spine + silent branches + precedents. Prefer for LOOKUP before grepping.",
        "args": ["orient"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "apiName / request / partial id"},
            },
            "required": ["query"],
        },
    },
    "kg_flow": {
        "description": "Ordered processor chain (flow spine) + DB footprint for a Request.",
        "args": ["flow"],
        "schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    "kg_why": {
        "description": "Failure-mode / silent decision-point catalog for a request, processor, table, or symptom.",
        "args": ["why"],
        "schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    "kg_impact": {
        "description": "Reverse blast radius — who reaches this node (recursive CTE).",
        "args": ["impact"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "depth": {"type": "integer", "description": "optional --depth N"},
            },
            "required": ["query"],
        },
    },
    "kg_fixed_elsewhere": {
        "description": "Verified higher-branch fixes + file-touch candidates (read-only). Use before proposing ports.",
        "args": ["fixed-elsewhere"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "repo": {"type": "string"},
                "base": {"type": "string", "description": "reported/base branch"},
            },
            "required": ["query"],
        },
    },
    "kg_validate": {
        "description": "KG integrity + min nodes/edges check.",
        "args": ["validate"],
        "schema": {"type": "object", "properties": {}},
    },
    "kg_watermark": {
        "description": "Per-repo branch@sha the KG was built from vs live HEAD.",
        "args": ["watermark"],
        "schema": {"type": "object", "properties": {}},
    },
    "kg_fresh": {
        "description": "One-line verdict: is KG branch-correct for current checkout?",
        "args": ["fresh"],
        "schema": {"type": "object", "properties": {}},
    },
    "kg_search": {
        "description": "Full-text node search (FTS5). Smallest query first.",
        "args": ["search"],
        "schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    "kg_cases": {
        "description": "Shipped-fix precedents (CHANGELOG cases) for a flow/table.",
        "args": ["cases"],
        "schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    },
}


def truncate(s: str) -> str:
    if len(s) <= MAX_CHARS:
        return s
    return s[: MAX_CHARS - len(TRUNC_MARK)] + TRUNC_MARK


def run_kg(argv: list[str]) -> str:
    if not KG_PY.is_file():
        return f"ERROR: kg.py not found at {KG_PY}"
    env = os.environ.copy()
    env.setdefault("KG_NO_AUTO_REBUILD", "1")  # MCP lookups stay fast; agent can kg-switch separately
    try:
        proc = subprocess.run(
            [sys.executable, str(KG_PY), *argv],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return "ERROR: kg.py timed out (120s)"
    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    if proc.returncode != 0 and not out.strip():
        out = f"ERROR: kg.py exit {proc.returncode}"
    return truncate(out.strip() or "(empty)")


def tool_argv(name: str, arguments: dict) -> list[str]:
    meta = TOOLS[name]
    argv = list(meta["args"])
    q = arguments.get("query")
    if q is not None and str(q).strip():
        argv.append(str(q).strip())
    if name == "kg_impact" and arguments.get("depth") is not None:
        argv.extend(["--depth", str(arguments["depth"])])
    if name == "kg_fixed_elsewhere":
        if arguments.get("repo"):
            argv.extend(["--repo", str(arguments["repo"])])
        if arguments.get("base"):
            argv.extend(["--base", str(arguments["base"])])
    return argv


def tools_list_payload():
    return {
        "tools": [
            {
                "name": name,
                "description": meta["description"],
                "inputSchema": meta["schema"],
            }
            for name, meta in TOOLS.items()
        ]
    }


def handle(msg: dict) -> dict | None:
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": tools_list_payload()}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True,
                },
            }
        text = run_kg(tool_argv(name, arguments))
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {"content": [{"type": "text", "text": text}]},
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    # Ignore other notifications
    if mid is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": mid,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
