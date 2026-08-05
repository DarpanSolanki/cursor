---
name: feedback_mcp_ide_catalog_not_stdio_smoke
description: "MCP green must mean Cursor loaded the server — kg-mcp-smoke alone is not enough; check ~/.cursor/projects/<ws>/mcps/."
metadata:
  node_type: memory
  type: feedback
---

**Miss:** Agents trusted `check-mcp-wiring` / `kg-mcp-smoke` while Cursor’s live tool list had no `trustt-kg` (and Atlassian flaky). Stdio smoke starts its own process.

**Fix (2026-08-05):** `scripts/lib/mcp_wiring_gate.py` (+ `check-mcp-wiring.py` CLI):
1. File contract — project `.mcp.json` must list `trustt-kg` only (no project Atlassian; no `/v1/sse`).
2. IDE catalog — require `*trustt-kg` + `kg_doctor` under `~/.cursor/projects/<slug>/mcps/`, and an Atlassian server (prefer marketplace plugin). WARN if both plugin + project Atlassian are loaded.

**Atlassian SoT:** Cursor marketplace plugin (Streamable HTTP). Remove duplicate from project mcp.json.

Escape: `MCP_IDE_CATALOG_SKIP=1` / `--file-only`.
