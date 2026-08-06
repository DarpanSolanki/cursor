#!/usr/bin/env python3
"""Validate the MCP launch contract Cursor actually uses.

`kg-mcp-smoke` spawns the server itself with a resolved path, so it reports
tools=20 even when Cursor cannot start the server at all. That is exactly
how `.mcp.json` shipped with an unexpanded `${CLAUDE_PROJECT_DIR}` in argv and
every `mcp__trustt-kg__*` tool was silently missing for a whole session.

Checks, for each stdio server in .mcp.json:
  * no unexpanded ${...} anywhere in command/args/env (Cursor does not
    interpolate these — the literal string reaches execve)
  * the script argument resolves relative to the project dir (the client's cwd)

Deliberately does NOT check ~/.cursor.json for an approval key: project servers
load from a valid .mcp.json without one (verified — trustt-kg serves all 20 tools
while the project entry holds no MCP keys at all). Asserting otherwise produced a
false FAIL while MCP was demonstrably working.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
MCP_JSON = ROOT / ".mcp.json"
PLACEHOLDER = re.compile(r"\$\{[^}]+\}")


def main() -> int:
    if not MCP_JSON.is_file():
        print("no .mcp.json — nothing to check")
        return 0
    try:
        servers = (json.loads(MCP_JSON.read_text(encoding="utf-8")) or {}).get("mcpServers", {})
    except (json.JSONDecodeError, ValueError) as exc:
        print(f".mcp.json is not valid JSON: {exc}")
        return 1

    errors: list[str] = []
    for name, spec in servers.items():
        blob = json.dumps(spec)
        for hit in PLACEHOLDER.findall(blob):
            errors.append(f"{name}: unexpanded {hit} — Cursor passes this literally")
        if spec.get("type") in ("sse", "http") or "url" in spec:
            continue  # remote server: nothing local to resolve
        for arg in spec.get("args") or []:
            if PLACEHOLDER.search(arg) or not arg.endswith((".py", ".js", ".sh")):
                continue
            if not (ROOT / arg).is_file() and not Path(arg).is_file():
                errors.append(f"{name}: script not found from project dir: {arg}")

    if errors:
        for e in errors:
            print(f"  {e}")
        return 1
    print(f"mcp wiring OK — {len(servers)} server(s): {', '.join(sorted(servers))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
