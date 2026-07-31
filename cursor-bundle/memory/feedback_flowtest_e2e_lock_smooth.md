# Flowtest e2e lock — smooth multitask (2026-07-31)

## Standing
- **One money harness owner** at a time via exclusive flock on `/tmp/flowtest_e2e.lock` (override `FLOWTEST_E2E_LOCK`).
- Owner metadata in lock file: `pid=`, `case=`, `started_at=`, `cmdline=` (also `json=` line).
- Wait: `FLOWTEST_LOCK_WAIT_S` default **120**; set `0` for fail-fast (tests).
- Status: `bash scripts/bin/flowtest-lock-status.sh` (`--json` ok).
- **stack-doctor** must check **flock held + live pid** — never `rm -f` lock on file presence alone.
- **Never** `pgrep -f` patterns that match the waiter/`flowtest_e2e` string (self-hang / Multitask collisions).

## Re-entrant
`FLOWTEST_E2E_LOCK_HELD=1` / `DCF_E2E_LOCK_HELD=1` → `lock_held()` skips second acquire in same process tree.

## L2 follow-up (not shipped)
Ship-loop skip re-fire when same case already PASS this session **and** lock held by that case — only if low-risk; keep fail-closed serialize otherwise.
