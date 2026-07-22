---
name: feedback_code_backed_simulation_testing
description: Prefer realtime ntest; when a stage is blocked use code-backed orch/processor simulation in registry — never guess expected outcomes
---

# Code-backed simulation testing (standing)

Triggered by TDPQA-102 (2026-07-15): fix shipped in orch without a registry case → autopilot end fell through to unrelated disburse smoke and reported "no verified test in queue".

## Standing rule

`.cursor/rules/20-ship-gates.mdc` (alwaysApply).

## Ladder

1. `RUNTIME_VERIFIED` — live flow + DB
2. `STAGE_PARTIAL` — real until documented blocker
3. `ORCH_SIBLING_SIM` — parse real orchestration XML (parent vs child Request beans)
4. `PROCESSOR_MIRROR_SIM` — extract expectations from `.java` on disk

Never invent amounts or processor lists from chat memory.

## Helpers / cases

- Lib: `scripts/testing/lib/orch_sibling_parity.py`
- Example case: `reopening.child_payments_parity_sim` → `scripts/testing/reopening/tdpqa102_child_reopen_payments_sim.py`
- Domain wiring: `scripts/lib/accounting_flow_domains.json` → `reopening`

## Agent failure mode to avoid

Declaring ship/close done after compile-only, or skipping registry enrichment when full E2E is "hard".
