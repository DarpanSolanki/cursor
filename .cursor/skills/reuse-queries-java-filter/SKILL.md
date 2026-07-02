---
name: reuse-queries-java-filter
description: >-
  MANDATORY before repository edits: (1) reuse + Java, (2) extend existing if no perf
  degrade, (3) new @Query last. Triggers on *Repository.java, *DAOService.java.
triggers:
  - Repository.java
  - DAOService.java
  - new query
  - @Query
requires: []
reads:
  - cursor-bundle/memory/feedback_keep_code_simple.md
  - cursor-bundle/memory/feedback_query_reuse_vs_performance.md
writes: []
---

# Reuse queries — Java filter (MANDATORY)

**Hard gate:** Follow the **3-step ladder** before any repository change. Read `.cursor/rules/reuse-queries-java-filter.mdc`.

## Ladder

| Step | Do | Stop when |
|------|-----|-----------|
| **1** | Existing `findAllBy*` / `findOneBy*` + Java filter / early return | Question answered — **default** |
| **2** | Extend existing `@Query` (optional param, extra column) | Step 1 insufficient **and** all callers keep same or better perf |
| **3** | New `@Query` / method | Steps 1–2 cannot work |

## Workflow

1. `rg` table name in `**/*Repository.java` and `**/*DAOService.java`.
2. Try **step 1** — including multiple calls to the same existing method on cold paths.
3. If step 1 fails — grep **all callers** of the candidate query; only then consider **step 2** with perf gate.
4. **Step 3** only with written reason why 1–2 failed.
5. PR/commit note: which step used (e.g. *"Step 1: reused `findAllByLoanAccountNumbersAndStatus` ×2; no SQL change."*).

## Step 2 perf gate (quick)

- Additive / backward-compatible for existing callers
- No broader scan, no index-unfriendly `OR`, no dropped predicates on hot/batch paths
- If risky → step 1 (extra call) or step 3 (new narrow method), not a breaking widen of the hot query

## Precedents

- **Foreclosure expiry (SDCP-10400):** step 1 — `findAllByLoanAccountNumbersAndStatus` for PENDING + APPROVED; dedupe in Java.
- **Duplicate pending guard (SDCP-10255):** step 1 — same query ×2 with early return; **not** step 2 `IN (task_status)`, **not** step 3 new method.
- **DPI:** step 1 for per-loan sums; keep SQL aggregates only on batch hot loops.

## Anti-patterns

- New query duplicating existing `WHERE` (step 3 without trying step 1)
- “Performant” merge to step 2/3 on per-loan cold paths when step 1 already works
- Editing a batch-hot query for a one-off API need without caller impact analysis

## Tie-in

- `.cursor/rules/minimal-fix-impact-gate.mdc`
- `cursor-bundle/memory/feedback_query_reuse_vs_performance.md`
