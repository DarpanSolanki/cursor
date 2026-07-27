#!/usr/bin/env python3
"""trustt-kg MCP server — in-process SQLite (read-only). No kg.py subprocess spawn."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # sliProd
BIN = ROOT / "cursor-bundle" / "kg" / "bin"
sys.path.insert(0, str(BIN))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import kg as kg_mod  # noqa: E402

MAX_CHARS = 10_000
TRUNC_MARK = "\n\n… [truncated — refine query / narrower args; max 10000 chars] …\n"
SERVER_INFO = {"name": "trustt-kg", "version": "1.1.0"}
PROTOCOL = "2024-11-05"

TOOLS = {
    "kg_orient": {
        "description": "Orient on an apiName/request: flow spine + silent branches + precedents. Prefer for LOOKUP before grepping.",
        "args": ["orient"],
        "schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "apiName / request / partial id"}},
            "required": ["query"],
        },
    },
    "kg_flow": {
        "description": "Ordered processor chain (flow spine) + DB footprint for a Request.",
        "args": ["flow"],
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    "kg_why": {
        "description": "Failure-mode / silent decision-point catalog for a request, processor, table, or symptom.",
        "args": ["why"],
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    "kg_impact": {
        "description": "Reverse blast radius — who reaches this node (recursive CTE).",
        "args": ["impact"],
        "schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "depth": {"type": "integer", "description": "optional --depth N"}},
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
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    "kg_cases": {
        "description": "Shipped-fix precedents (CHANGELOG cases) for a flow/table.",
        "args": ["cases"],
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
    "kg_crud": {
        "description": "DB footprint of a flow (reads/writes/deletes).",
        "args": ["crud"],
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    "kg_writes": {
        "description": "Who writes a table.",
        "args": ["writes"],
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
}

_DB = None
os.environ.setdefault("KG_NO_AUTO_REBUILD", "1")


def _db():
    global _DB
    if _DB is None:
        _DB = kg_mod.conn(readonly=True)
    return _DB


def truncate(s: str) -> str:
    if len(s) <= MAX_CHARS:
        return s
    return s[: MAX_CHARS - len(TRUNC_MARK)] + TRUNC_MARK


_HEADER_CACHE = None  # (mono, str)

def _header() -> str:
    global _HEADER_CACHE
    import time as _time
    now = _time.monotonic()
    if _HEADER_CACHE and (now - _HEADER_CACHE[0]) < 5.0:
        return _HEADER_CACHE[1]
    try:
        from kg_state_banner import provenance_header

        h = provenance_header()
    except Exception as exc:  # noqa: BLE001
        h = f"[KG @? set=? WIP:?] (header failed: {exc})"
    _HEADER_CACHE = (now, h)
    return h


def run_kg(argv: list[str]) -> str:
    cmd = argv[0]
    args = argv[1:]
    if cmd not in kg_mod.CMDS:
        return f"ERROR: unknown kg cmd {cmd}"
    # validate still shells to kg_validate for integrity PRAGMA (rare)
    if cmd == "validate":
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                kg_mod.CMDS[cmd](_db(), args)
            except SystemExit as e:
                if e.code not in (0, None):
                    return truncate((_header() + "\n" + buf.getvalue()).strip() or f"ERROR: validate exit {e.code}")
        body = buf.getvalue().strip()
        return truncate(_header() + "\n" + (body or "OK"))
    if cmd == "fixed-elsewhere":
        # keeps branch_train subprocess (rare path)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                kg_mod.CMDS[cmd](_db(), args)
            except SystemExit:
                pass
        body = buf.getvalue().strip()
        return truncate(_header() + "\n" + (body or "(empty)"))

    buf = io.StringIO()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        kg_mod.CMDS[cmd](_db(), args)
    ms = (time.perf_counter() - t0) * 1000
    body = buf.getvalue().strip() or "(empty)"
    if os.environ.get("KG_MCP_TIMING"):
        body = f"(mcp_inproc_ms={ms:.1f})\n" + body
    if body.startswith("[KG @"):
        return truncate(body)
    return truncate(_header() + "\n" + body)


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
            {"name": name, "description": meta["description"], "inputSchema": meta["schema"]}
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
                "result": {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True},
            }
        text = run_kg(tool_argv(name, arguments))
        return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}]}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if mid is None:
        return None
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main() -> None:
    # warm DB open once
    _db()
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
