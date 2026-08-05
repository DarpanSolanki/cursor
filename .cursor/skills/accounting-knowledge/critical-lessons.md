<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.md only routes here. -->

## Critical lessons (from production incidents)

- **Job-owned tables — never hand-mutate** (TDPQA-72): `interest_accrual_details` (and peer job staging) must only change via accrual **jobs** / forceful **booking** processor / catalogue BILLING — never writer `setTotalAccruedAmount` “Accrued≤Original” hacks. Map: `job-owned-tables.md`.
- **paid_amount vs waived_amount**: NEVER mix. "Extra interest paid" = actual paid only. Waived = loss bucket.
- **Future INT dues**: do NOT use future due rows' paid_amount to infer "extra interest". Use deterministic as-of-date calc.
- **Reject/recreate**: earlier attempts can mutate due rows. Always compute from stable inputs (dates + rates), not mutable DB state.
- **balance_claim_amount**: independent of GL posting (sum_assured - outstanding). Correct even if posting is wrong.
- **loanAccountBilling only picks ACTIVE loans**: `LoanAccountBillingBatchService` partitions using `WHERE la.loan_status = 'ACTIVE'`, so only `ACTIVE` loans are selected for billing.

