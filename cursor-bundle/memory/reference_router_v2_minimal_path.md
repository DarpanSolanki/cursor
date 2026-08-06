---
name: reference_router_v2_minimal_path
description: Router v2 — process matrix is a weighted DAG with terminal state; how PLAN/GOAL/escalation work and what may never be traded for speed
metadata:
  type: reference
---

`scripts/lib/process_matrix.json` (v2, 2026-08-06) is a **weighted DAG**, not a checklist.

- `cost_s` seeds each gate · `requires` supplies edges · `phase` (orient/gate/verify/close) ranks them
- `process_router.order_path` orders the selected set; `plan_waves` groups independent gates into
  concurrent waves. `PLAN [class] ~<wave_s>s (<n> waves, serial <est_s>s)`
- measured run times relax weights (EWMA α=0.3) into `.cursor/.process-costs.json`, keyed by matrix
  node — `STEP_COST_KEY` in `workspace_autopilot.py` maps step ids onto process names
- `terminal_state` per class = the goal predicates; `GOAL [class]` prints beside `PLAN`
- `.cursor/.task-state.json` (via `scripts/bin/route-ledger.sh`) is the open task: planned, ran,
  escalations, terminal results. `resume` is subprocess-free — keep it that way

**Three things speed may never buy:**

1. A gate is skipped only when TTL-fresh or already run **in this open task**, and only for
   `orient` phase (`dedup_phases`). `gate`/`verify`/`close` always re-evaluate — the diff moves.
2. Money-floor cells stay `required`; `process_router.py ratchet` fails closed (and now also if a
   duplicate `process-matrix.json` reappears).
3. An edit heavier than the plan escalates via `.cursor/hooks/route-escalation.py`, which names the
   missing gates and raises the terminal state. Never dismiss that banner.

`evidence_cited` / `knowledge_loops` / `options_board` are **declared**, not checked — declaring a
tier you did not reach is the one failure the machine cannot catch. See the simulation ladder in
`.cursor/rules/20-ship-gates.md`.

`bash scripts/bin/route-ledger.sh learn` reports classifier-too-light, chronically-unmet predicates
and stale seed costs. Report-only by design — it never edits the matrix.

Related: [[feedback_ship_test_autonomy_change_map]] · [[feedback_keep_code_simple]]
