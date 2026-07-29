# MCP stdout protocol corruption (trustt-kg)

**Symptom:** Cursor `serverStatus=error` — "failed during live tool discovery"; logs show `Unexpected token 'O', "OK: 8015 n"... is not valid JSON` / `REUSE_FORBIDDEN is not valid JSON`.

**Root cause:** `kg validate` and `kg fixed-elsewhere` spawned subprocesses **without capturing stdout**. Child prints (`OK: N nodes…`, `RESULT:…`, `REUSE_FORBIDDEN`) went onto MCP fd1 and broke JSON-RPC mid-session → FSM `transport_error` → tools unavailable / timeouts.

**Fix (2026-07-29):**
1. `cursor-bundle/kg/bin/kg.py` — capture subprocess stdout for `validate` + `fixed-elsewhere`, print into Python stdout (redirected by MCP).
2. `kg_mcp_server.py` — `os.dup2(2,1)` so any leftover child inherit goes to stderr; JSON-RPC only on saved fd; lazy DB open; `kg_map_audit` tool; `tool_argv` only forwards schema-declared query.
3. Smoke: `bash scripts/bin/kg-mcp-smoke.sh` (15/15 + JSON-RPC-clean stdout).

**After pull:** reload MCP server **trustt-kg** in Cursor Settings (or restart window) so live discovery picks up the fixed process.
