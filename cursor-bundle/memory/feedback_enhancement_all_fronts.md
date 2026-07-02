---
name: feedback_enhancement_all_fronts
description: "Enhancement/improvement: best solution ship bar — tiered options for discussion, L1+ for delivery"
metadata:
  node_type: memory
  type: feedback
---

## Two modes

| Mode | Delivery |
|------|----------|
| **Fire** (prod down, hours) | L0 deploy OK; still document L1 in release |
| **Improvement** (rework, SDCP fix, user asks best/platform fix) | **Ship best solution only** — L1 minimum in code; L0-only is incomplete |

## Improvement ship bar (all unless N/A)

1. Root cause — not symptom retry
2. Cross-service — paired deploy, additive contract
3. Transaction boundaries — break circular lock / partial commit
4. Poison rows — code guard + replay idempotency
5. Batch — per-record isolation; reader status filters
6. SQL — full query matrix + Flyway indexes + ops script
7. Prod index baseline — `cursor-bundle/reference/db/prod-indexes-baseline.csv` (never ask user for export)
8. Live EXPLAIN on QA when available
9. Hot-path scan — significant N+1 in same PR
10. Registry / sibling regression

Present **L0–L3 in discussion** for trade-offs; **implement L1+ together** when mode = Improvement.

Skill: `.cursor/skills/query-index-perf-gate/SKILL.md`  
Rule: `.cursor/rules/enhancement-all-fronts-gate.mdc`
