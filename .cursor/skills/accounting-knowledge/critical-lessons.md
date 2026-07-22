<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.mdc only routes here. -->

## Critical lessons (from production incidents)

- **paid_amount vs waived_amount**: NEVER mix. "Extra interest paid" = actual paid only. Waived = loss bucket.
- **Future INT dues**: do NOT use future due rows' paid_amount to infer "extra interest". Use deterministic as-of-date calc.
- **Reject/recreate**: earlier attempts can mutate due rows. Always compute from stable inputs (dates + rates), not mutable DB state.
- **balance_claim_amount**: independent of GL posting (sum_assured - outstanding). Correct even if posting is wrong.
- **loanAccountBilling only picks ACTIVE loans**: `LoanAccountBillingBatchService` partitions using `WHERE la.loan_status = 'ACTIVE'`, so only `ACTIVE` loans are selected for billing.

