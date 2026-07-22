---
name: feedback_query_reuse_vs_performance
description: "Query ladder: (1) reuse + Java, (2) extend existing if no perf degrade, (3) new @Query last. Two cold-path calls OK."
metadata:
  node_type: memory
  type: feedback
---

## Query decision ladder (user-approved — strict order)

| Step | Action | When |
|------|--------|------|
| **1** | **Reuse existing query + Java** | Default. Filter/pick/anyMatch/early-return in DAO or processor. **2+ calls** to the same existing method on per-loan/API paths is fine. |
| **2** | **Extend existing query** | Step 1 cannot work **and** extension does **not** degrade performance for **all existing callers**. |
| **3** | **New `@Query` / repository method** | Steps 1–2 cannot satisfy the need. |

Do not jump to step 2 or 3 for aesthetics (“one round trip”) on cold paths.

## Step 2 — extend existing (performance gate)

Before changing SQL on an existing repository method:

- [ ] `rg` every caller — batch jobs, APIs, consumers
- [ ] Change is **additive** (optional param, extra SELECT column, backward-compatible overload)
- [ ] **No** removal of indexed `WHERE` predicates for existing call patterns
- [ ] **No** broader row scan on hot paths (e.g. dropping `loan_account_id`, adding `OR` that blocks index)
- [ ] **No** slower plan for batch inner loops that already use this query

If extension would slow any hot caller → stay on **step 1** (extra Java-filtered call) or use **step 3** (new method scoped to the new need only) — never widen the hot query.

## Step 3 — new query

Document why step 1 failed (no existing read returns the rows) and why step 2 failed (extend would hurt callers, or semantics diverge too far). Typical valid cases: batch hot loop aggregate, bulk `@Modifying`, dedicated read that must not touch an existing hot signature.

## Overrides generic “performant fix”

Custom_rule / review suggestions to merge loops into `IN (...)` SQL **do not override step 1** on per-loan create/approve/expiry unless steps 1–2 are proven insufficient.

## Foreclosure prepayment (SDCP-10255 / SDCP-10400) — step 1 only

- `findAllByLoanAccountNumbersAndStatus` ×2 (PENDING / APPROVED `task_status`) — **correct**
- Step 2 not needed: extending with `IN (task_status)` saves one cold round-trip but adds churn + caller blast-radius risk for no real gain
- Step 3 not needed: existing query already returns the rows

## Agent checklist

1. Grep `*Repository.java` for the table — list existing reads
2. Can step 1 answer it? → **stop**
3. If not — can step 2 extend without perf regression on all callers? → document callers + plan impact
4. Else → minimal new query (step 3)

## Tie-in

- `cursor-bundle/memory/feedback_keep_code_simple.md` RULE 3
- `.cursor/skills/reuse-queries-java-filter/SKILL.md`
- `.cursor/rules/10-quality-gates.mdc`
