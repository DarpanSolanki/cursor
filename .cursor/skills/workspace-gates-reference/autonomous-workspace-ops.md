<!-- VERBATIM archive of former alwaysApply `.cursor/rules/autonomous-workspace-ops.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Autonomous workspace ops

Agents **must not** skip tooling or declare "service down / blocked" without running ops scripts first.

## Session start (silent)

1. Read `.cursor/workspace-kg-state.md` + `.cursor/workspace-ops-state.md`
2. `bash scripts/bin/kg-ensure-fresh.sh --quiet` if KG stale
3. Hooks run `agent-ops.sh preflight` on session start

## Decision matrix — what runs automatically

| Situation | Auto action | Command |
|-----------|---------------|---------|
| `ntest auto/run` batch or `dpi*` API | ensure service; compile **only if** `.java` newer than boot log | `agent-ops.sh before-test <api>` |
| `ntest auto/run` any API, service down | ensure (no compile unless Java changed) | same |
| HTTP 000 / connection refused on fire | ensure + compile once, **retry** API | built into `ntest` |
| Test/batch **failure** | log snap + batch DB if batch | `agent-ops.sh on-failure` |
| Wait >10s (boot/batch) | heartbeats already print log hints; then `novopay-logs.sh snap` | on timeout |
| User: sanity / after DPI Java ship | full DPI regression | `agent-ops.sh verify-dpi` |
| User: push money-path fix | build + changelog + kg-flow + `ship-knowledge-gate.sh` | post-ship gate |
| Stuck / "where are logs?" | never guess paths | `novopay-logs.sh guide accounting` |

## Do not

- Skip sanity because port 8002 is down — `novopay-service.sh ensure accounting --compile`
- Blind-sleep >10s without `novopay-logs.sh errors` or `snap`
- Re-implement wait loops — use `wait_batch_job.sh`, `novopay-service.sh wait`
- Ask user for log paths — use `workspace-ops-state.md` or `novopay-logs.sh guide`

## ntest defaults (wired in code)

- `ntest auto <api>` → auto `before-test` for batch/DPI/disburse/foreclosure APIs
- `--no-ensure` / `NTEST_NO_ENSURE=1` to opt out
- `--compile` forces compile; otherwise compile only when Java newer than boot log
- Failure → auto `run_log_snap` + analyze hints

## Skill

`.cursor/skills/autonomous-workspace-ops/SKILL.md`
