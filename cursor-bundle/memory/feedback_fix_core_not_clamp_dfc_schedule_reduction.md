# Fix core formula — do not clamp in generic writers (SDCP-10199 lesson)

**Standing rule (2026-07-08):** When a money-path bug is a **wrong inputs / wrong formula**, fix at the **producer** (query + business rule), not with clamps in shared processors or downstream writers.

**Example — group parent DFC first-child RSCH:**
- Symptom: negative parent PRIN part-prepayment row (−3,710).
- Wrong approach: clamp `prepayAmount` in `GenerateRepaymentScheduleProcessor` or clamp `netAmount` in writer only.
- Root cause: `futurePrincipal (due >= death)` minus `allUnpaidBilled (no date filter)` — subtracts overdue billed already handled in appropriation.
- Core fix: `scheduleReduction = futurePrincipal − futureUnpaidBilledPrincipal` via `getUnpaidFutureBilledPrincipalForDeathForeClosure(accountId, deathDate)` (`due_date >= death` + billed EXISTS).

**Agent gate:** Before shipping a clamp/guard, ask: *why is the value negative?* If bucket mismatch → fix query/formula (L1). Clamp is L0 hotfix only when core fix cannot ship same train.
