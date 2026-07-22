# Reuse-query machine gate (fail closed)

**Date:** 2026-07-17
**Trigger:** A repository SQL change (`LoanAccountBillingDetailsRepository.findByLoanInstallmentDetailsId`
gained `ORDER BY id DESC LIMIT 1` in TDPQA-72) shipped before the reuse-queries ladder was
proven on record. Soft rule `10-quality-gates.mdc` was skipped — no exit code.

## Permanent fix

`scripts/lib/reuse_query_gate.py`, wired into `scripts/lib/ship_discipline_gate.py`:

- Triggers when a pending ship file basename ends `Repository.java` / `DAOService.java`
  **and** its diff changes query semantics (`@Query`, native SQL, `ORDER BY`, `LIMIT`,
  `WHERE`, `SELECT`/`JOIN`/`GROUP BY`, or a finder-method signature).
- Requires a `reuse_query` block in `.cursor/.ship-discipline.json`:
  `reuse_queries_step` (1|2|3), `existing_methods_checked` (non-empty),
  `callers_checked` (non-empty), `performance_impact` (non-empty), and
  `new_query_justification` (required when step 3).
- Fails closed inside the existing discipline gate — no new JSON, no new hook.

Write via `ship-discipline.sh write … --reuse-step N --reuse-existing … --reuse-caller …
--reuse-perf … [--reuse-justification …]`. Tests: `scripts/lib/test_reuse_query_gate.py`.

## Re-verification outcome (do not re-litigate)

The `ORDER BY id DESC LIMIT 1` on `findByLoanInstallmentDetailsId` is **step 2 (extend
existing query)**, not a new query, and must **not** be reverted:

- No `List<LoanAccountBillingDetailsEntity>` finder exists on `loan_account_billing_details`
  (only two singular finders + `saveAll`). So step 1 (reuse + Java filter) has nothing to
  filter over without a full-table `findAll()` — not viable.
- TDPQA-72's `persistForceBillBillingDetails` intentionally INSERTs a dedicated force-bill
  labd alongside an existing EMI labd → multi-row per `loan_installment_details_id`. The
  plain singular native finder would throw `IncorrectResultSizeDataAccessException`.
- `ORDER BY id DESC LIMIT 1` returns the latest row, which is **required** for force-bill
  insert idempotency (replay must find our row by ref, else it duplicates the insert).
- All 4 callers verified safe with latest-row semantics (2× DFC writer checks, DFC reconcile,
  batch billing idempotency).

Darpan's belief "use existing queries + Java filtering" is false **for this table** — there
is no bounded-set finder to filter over.
