#!/usr/bin/env python3
"""Every KG lookup an agent is told to use must be reachable over MCP.

Agents are instructed to reach for MCP first (`30-kg-discipline.md`). A command that
exists only on the CLI is, in practice, a command that does not get used: the CLI costs
~690ms of interpreter start per call and does not appear in the tool list at all.

`kg schema` was the expensive case. `.cursorrules` and `40-knowledge-upkeep.md` both tell
agents to resolve every column through it, and it lists every reader and writer of that
column — but it had no MCP tool, so a session hunting for "who writes loan_status" grepped
for setters instead of asking.

CLI-only is allowed, but must be deliberate: add the command to CLI_ONLY with a reason.

    python3 scripts/lib/test_kg_mcp_cli_parity.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "cursor-bundle/kg/mcp/kg_mcp_server.py"
CLI = ROOT / "cursor-bundle/kg/bin/kg.py"

CLI_ONLY = {
    "fresh": "folded into kg_doctor",
    "validate": "folded into kg_doctor",
    "stats": "graph size — diagnostic, not a lookup",
    "neighbors": "raw edge walk; kg_node covers the agent-facing case",
    "path": "raw traversal; kg_impact covers blast radius",
    "sql": "escape hatch for ad-hoc KG SQL, deliberately not exposed",
    "stale": "diagnostic; kg_doctor reports staleness",
    "deps": "service call graph; kg_node / orient cover agent lookups",
    "docs": "doc mentions; kg_search / kg_concept cover agent lookups",
    "table": "folded into kg_schema + kg_writes for agent use",
    "deletes": "reverse delete map; kg_writes covers money write paths",
}


def mcp_tools() -> set[str]:
    src = SERVER.read_text()
    start = src.index("TOOLS")
    return set(re.findall(r'^\s{4}"([a-z_]+)"\s*:\s*\{', src[start:], re.M))


def cli_commands() -> set[str]:
    """Parse kg.py help — commands are `  name …` (not always double-spaced)."""
    out = subprocess.run([sys.executable, str(CLI)], capture_output=True, text=True).stdout
    cmds: set[str] = set()
    for line in out.splitlines():
        m = re.match(
            r"^  ([a-z][a-z0-9_-]*(?:\s*\|\s*[a-z][a-z0-9_-]*)*)\b",
            line,
        )
        if not m:
            continue
        for part in re.split(r"\s*\|\s*", m.group(1)):
            part = part.strip()
            if part:
                cmds.add(part)
    return cmds


class KgMcpCliParityTest(unittest.TestCase):

    def test_every_cli_lookup_has_an_mcp_tool_or_a_stated_reason(self) -> None:
        tools = {t[3:] if t.startswith("kg_") else t for t in mcp_tools()}
        missing = sorted(
            c for c in cli_commands()
            if c.replace("-", "_") not in tools and c not in CLI_ONLY
        )
        self.assertEqual(
            [], missing,
            "CLI commands with no MCP tool and no stated reason: "
            f"{missing}. Add an MCP tool, or add it to CLI_ONLY with why.")

    def test_schema_is_exposed_because_the_rules_mandate_it(self) -> None:
        self.assertIn("kg_schema", mcp_tools(),
                      "40-knowledge-upkeep.md requires resolving every column through "
                      "kg schema; it must be reachable over MCP")

    def test_declared_tools_have_timeouts(self) -> None:
        src = SERVER.read_text()
        timed = set(re.findall(r'^\s{4}"([a-z_]+)"\s*:\s*[\d.]+,', src, re.M))
        untimed = sorted(t for t in mcp_tools() if t not in timed)
        self.assertEqual(
            [], untimed,
            f"tools without an explicit timeout fall back to {2.0}s: {untimed}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
