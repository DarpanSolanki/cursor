---
name: feedback_mcp_server_stale_after_code_fix
description: Fixing a file the MCP server imports does not fix the running server — hot-reload may not fire; kill the process
metadata:
  type: feedback
---

On 2026-08-06 a thread pool added to `_drift_check` hung every MCP call. The pool was removed and
the code verified clean — **and MCP still hung**, twice more, because the *running server* was
started 41 minutes before the fix and had never re-exec'd.

`kg_mcp_server` claims hot-reload ("re-exec when this server or kg.py changes on disk"), but its
start time was unchanged after the edit, so it did not fire. The process held the pre-fix module in
memory.

**Why:** the fix lives in files; a long-lived server holds an imported copy. Verifying the file — or
even running the function in a fresh `python3 -c` — proves nothing about the live process.

**How to apply:**

- After changing anything the MCP server imports (`kg.py`, `kg_composite.py`, `kg_state_banner.py`),
  **check the server's start time against the file mtime**:
  `ps -o lstart= -p $(pgrep -f "python3 .*kg_mcp_server.py")` vs `stat -c %y <file>`.
  Start time older than the fix ⇒ it is running stale code.
- Fix: `kill <pid>`. The server is read-only with no state; the harness respawns it on the next
  call. Verify with a fresh spawn over stdio rather than trusting the running one.
- **Diagnose before theorising.** Two rounds were wasted profiling hooks and autopilot while the
  answer was a stale process. When one specific call type hangs and everything else is fast,
  suspect the long-lived process behind that call type first.
- A fresh server answers `kg_watermark` in ~0.65s under its 2s cap. Anything near or past the cap
  means stale code or a blocking construct — see `scripts/lib/mcp_abandonable_gate.py`.

Related: [[reference_router_v2_minimal_path]] · [[feedback_never_bare_git_stash_pop]]
