---
name: feedback_significant_perf_with_fix
description: "When fixing: bundle significant perf wins in same scope; skip slight/marginal optimizations. Standing rule for all future tasks."
metadata:
  node_type: memory
  type: feedback
---

## Standing rule (user-approved)

When implementing **any** fix (bug, gap, small feature), watch for **significant** performance improvement in the **same flow / files / hot path** you are already touching. **Include it in the same change** when the win is material. **Do not** chase **slight** gains or expand scope for cosmetic speedups.

## Significant vs slight

| **Significant — do it along the way** | **Slight — skip (use query ladder step 1)** |
|---------------------------------------|---------------------------------------------|
| Batch inner loop: N+1 (query per row × thousands) → bulk read / SQL aggregate | One fewer round-trip on per-loan API (2 calls → 1) |
| Same request re-fetches the same loan/entity multiple times | `IN (task_status)` merge on cold create/approve |
| Full list load + Java filter on **hot** path where indexed narrow read or SQL `SUM`/`MAX` exists | `stream()` vs `for` on a handful of rows |
| Redundant work in scheduler/batch segment loop you are already editing | New cache layer for a rare edge case |
| Missing pagination/chunk on large result set in batch | Renaming or micro-refactor “for clarity” with no perf/correctness gain |

**Heuristic:** If the win is “nice in theory” but callers are **one loan / one API / bounded rows** → **slight**. If the win changes **orders of magnitude** or **DB load under batch load** → **significant**.

## How this fits the query ladder

1. **Step 1** (reuse + Java) — default; **includes** accepting 2 cold-path calls.
2. **Step 2** (extend existing SQL) — when step 1 fails **or** when you are on a **hot path** and extension gives **significant** gain **without** degrading other callers.
3. **Step 3** (new query) — last resort **or** justified **significant** batch/hot-path fix (document why).

**Slight** perf is **not** a reason to skip step 1 or widen existing SQL. **Significant** perf on a path you are already fixing **is** a reason to use step 2/3 after caller grep + perf gate.

## Scope discipline (pairs with minimal-fix gate)

- **In scope:** same processor/service/batch job/query chain as the fix; same PR when risk is contained.
- **Out of scope:** unrelated module “while we’re here”; drive-by refactors; slight optimizations.
- State in impact/PR: *“Significant perf: …”* or *“Perf: no significant opportunity in this path.”*

## Agent checklist (every fix)

- [ ] Is this path **hot** (batch segment, inner loop, high QPS API)?
- [ ] While reading code for the fix, any **N+1**, duplicate fetch, or full-scan on indexed column?
- [ ] If yes — is the win **significant**? → include minimal change; grep callers if SQL changes.
- [ ] If win is only **slight** → stick to minimal correctness fix + query ladder step 1.

## Tie-in

- `cursor-bundle/memory/feedback_query_reuse_vs_performance.md` — ladder + slight vs significant
- `cursor-bundle/memory/feedback_minimal_fix_impact_gate.md` — don’t let perf work balloon past minimal fix
- `.cursor/skills/reuse-queries-java-filter/SKILL.md`
- `.cursor/rules/minimal-fix-impact-gate.mdc`
