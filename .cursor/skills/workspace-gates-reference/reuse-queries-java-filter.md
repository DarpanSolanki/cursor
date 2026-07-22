<!-- VERBATIM archive of former alwaysApply `.cursor/rules/reuse-queries-java-filter.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Reuse queries — Java for filtering (standing rule)

Aligns with `cursor-bundle/memory/feedback_keep_code_simple.md` **RULE 3** and `feedback_query_reuse_vs_performance.md`.

## Machine-enforced (fail closed)

Any pending ship touching a `*Repository.java` / `*DAOService.java` file whose diff changes query semantics (`@Query`, native SQL, `ORDER BY`, `LIMIT`, `WHERE`, `SELECT`/`JOIN`, or a finder-method signature) **blocks** ship-discipline until `.cursor/.ship-discipline.json` carries a `reuse_query` block. Write it:

```bash
bash scripts/bin/ship-discipline.sh write --minimal-fix "…" --read-path No \
  --hot-path PASS --verify-mode RUNTIME_VERIFIED --kg CASES --assumptions-none \
  --reuse-step 2 \
  --reuse-existing findByLoanInstallmentDetailsId --reuse-existing findOneByAccountId \
  --reuse-caller DeathForeclosureInsuranceWriter --reuse-caller LoanAccountBillingBatchService \
  --reuse-perf "loan_installment_details_id indexed; LIMIT 1 O(1)"
```

`--reuse-step 3` additionally requires `--reuse-justification` (why steps 1–2 cannot work). Gate: `scripts/lib/reuse_query_gate.py` (wired into `scripts/lib/ship_discipline_gate.py`).

## Decision ladder (strict order)

1. **Reuse existing query + Java** — grep `*Repository.java`, `*DAOService.java`, callers on the same table. Filter / pick-one / sum in Java when rows per call are bounded (per loan, per installment, API read). Multiple calls to the **same** existing method is OK on cold paths.
2. **Extend existing query** — only if step 1 cannot work **and** the change does **not degrade performance** for existing callers (grep all call sites; additive/optional; keep indexed predicates; no broader scan on batch hot paths).
3. **New `@Query` / repository method** — last resort when 1–2 cannot satisfy the need.

## Step 2 performance gate (before editing existing SQL)

- List every caller of the method being changed
- Extension must be backward-compatible for current call patterns
- Do not widen `WHERE` or drop index-friendly predicates for hot/batch callers
- If extension hurts any hot path → stay on step 1 (extra call + Java) or step 3 (new scoped method) — do not mutate the hot query

## Step 3 — when new SQL is justified

| Situation | Prefer |
|-----------|--------|
| Daily batch inner loop (per segment × thousands of loans) | SQL `SUM` / `MAX` — e.g. `getOverdueBaseAmount`, `findMaxEndDateByLoanAccountId` |
| Bulk `UPDATE` / `mark*Billed*` / soft-delete anchors | Keep native `@Modifying` |
| Loan 360 / cross-table aggregate in one API round-trip | Keep combined native query if replacing it multiplies DB calls |
| No existing read + extend would regress hot callers | New method with narrow signature |

## Step 1 is enough (say no to premature step 2/3)

- Per-loan API / create / approve / single LAN expiry — **2+ calls** to existing `findAllBy*` with different params
- Merging those calls into `IN (task_status)` on the existing query **or** a new query for “one round trip” on cold paths
- New repository method duplicating an existing `WHERE` clause

## DPI examples (verified)

- **Calc billing installment:** `getDueDetailsByDueDateAndComponenetTypes` + earliest unpaid INT in Java — step 1
- **Keep SQL (hot):** `getOverdueBaseAmount`, `findMaxEndDateByLoanAccountId`, bulk mark-billed — already the right layer
- **Moved to Java:** unbilled/unposted sums per loan via `findAllByLoanAccountId*` — step 1

## Code style

- No verbose comments explaining the rule inline
- No extra helpers unless reused twice in the same class
- Mirror sibling flow (interest accrual/billing) before inventing structure
