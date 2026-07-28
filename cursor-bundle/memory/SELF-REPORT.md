# SELF-REPORT — FINAL SYNC 2026-07-27

Generated: 2026-07-27T14:13:14Z · post GAP-G / FINAL SYNC

## Fixed tax
- alwaysApply: doctor reports ≤35000B soft ceiling (see workspace-doctor)

## Speed (wall-clock by process class) — F4 permanent
- `question`: p50=31ms p95=31ms n=1
- `non-money-fix`: p50=42ms p95=42ms n=1
- `money-fix`: p50=62ms p95=62ms n=2
- `docs-kb`: p50=19062ms p95=19062ms n=1
- Rule: **fast = selection, never gate-weakening**. Money keeps FIX-PLAN + invariants + impact rails.

## Speed floors (F3 measured)
| Metric | ms | budget | verdict |
|--------|-----|--------|---------|
| session_start_hook | 51032 | 600000 | OK |
| kg_write_state | 1809 | 5000 | OK |
| mcp_kg_orient_warm | 767 | 100 | SLOW — CLI process spawn; in-process SQLite warm ≈0–1ms (MCP path); leave CLI budget soft |
| mcp_kg_orient_warm2 | 773 | 50 | SLOW — same — not MCP in-process; SU none — use trustt-kg MCP for LOOKUPs |
| question_e2e | 31 | 500 | OK |
| small_fix_e2e | 42 | 1000 | OK |
| doctor | 19062 | 120000 | OK |
| f2_money_plan_2 | 43 | 2000 | OK |

## KG
- grep-leak shell counter (cumulative jsonl lines): **117** (baseline sessions 172 grep / 50 kg — 2026-07-27)
- **Footnote (SU-KG-003 CLOSED):** IDE/agent Grep tool is **not** hookable via `beforeShellExecution` — only shell `rg`/`grep` count. Prefer MCP `trustt-kg` for LOOKUPs.
- map-completeness: consumer=44/44 (unique beans excl BeanName placeholders)
- stale docs: **0/393** (was 108/393)

## QA bar / invariants / tiering
- flow-coverage YES (scope=out excl): **16/33 (48.5%)**
- Universal invariants: ON for money flowtest + dcf e2e
- Selection: direct full / sibling smoke / dcf≤3 representatives — ForceBill wall_planned=2045s (prior 6860s; ~⅓); wall_saved vs naive printed on banner
- ship_baseline notes: serial-suite caveat recorded

## Backlog post-drain
- Open: **6** — SU-FLOW-EXCESS-RAILS, SU-FLOW-PARTPREP-PTC-GLAD, SU-FLOW-WRITEOFF-GAP062, W3, W4, W5
- Drained this round: SU-TIER-VARIANT, SU-IMPACT-002, SU-RES-001/002 wont-do, SU-STITCH-001/005/006, SU-KG-001 accepted-limitation, SU-KG-002/003, SU-PERF-IDIOMS-001 lean

## Red flags
- Only high-value waves + known flow blockers remain (see open list)

## 2026-07-28 Pipeline overhaul close
- One-brain ship path is active: `resolve_ship_impact` + `register_pending_ship` consume `impact_tests.build_plan` ordered cases (fallback prints `FALLBACK: no selection`).
- Watchdog discipline: `run-guarded` enforces step timeout; `chain_budgets` derives case/chain budgets; `stack-doctor` runs pre-ship to fail fast on dirty stack.
- Push discipline tightened: `push-origin.sh` now blocks if `ship_push_gate --satisfied` fails for current HEAD.
- MCP self-awareness: trustt-kg exposes read-only `workspace_status` and `ship_plan` (≤10K with provenance header).

# dirty 1785221894.7081027