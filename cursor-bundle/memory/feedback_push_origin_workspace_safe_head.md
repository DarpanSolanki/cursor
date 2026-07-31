# Push-origin must not hang on sticky money when HEAD is workspace-safe

**Standing (2026-07-30):** Cursor harness / docs / testing-infra pushes must **never**
re-run a sticky money ship-loop left by an earlier `trustt-*` / `novopay-*` edit.

## Failure mode

`push-origin` → auto `workspace-close` (money) because `.pending-ship-work.json`
still listed accounting Java + harness NEFT scripts mashed together, while HEAD
was only `scripts/disburse_*` / `complete_neft_v2_*`. Knowledge-only skip did not
apply (harness ≠ knowledge allowlist).

## Fix

- `ship_change_scope.is_workspace_push_safe_paths` — HEAD has zero service-repo paths
- `ship_push_gate.should_skip_auto_close_for_knowledge_head` — also skips for
  workspace-safe HEAD; prunes harness/scratch/kb from pending; then
  **`pending_ship_gc`** drops clean+pushed service zombies (no forever sticky money).
  Only dirty/unpushed service paths remain.
- `register_pending_ship` — never register `scripts/scratch/**`; GC before merge
- Regression: `scripts/lib/test_ship_push_workspace_safe.py`

See also: `feedback_pending_ship_gc_no_sticky.md` (2026-07-31 — sticky once-and-for-all).

## Not KG MCP

`trustt-kg` `ship_plan` is **advisory selection only**. Push-close ownership stays in
`ship_push_gate` / `push-origin.sh` (must work offline, fail-closed).
