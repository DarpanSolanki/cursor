<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.mdc only routes here. -->

## Booking vs billing vs posting vs accrual

- **Billing** (BILLING/NORMAL_BILLING): generates installment dues (PRIN+INT) when due date arrives. EOD nightly.
- **Accrual booking** (INTEREST/NORMAL_ACCRUAL): posts accrued interest to GL. EOD or forceful in DCF flow.
- **Posting** (any postTransaction call): creates GL entries (debit/credit legs) for any transaction type.
- **Forceful booking**: skips date/condition checks (isAccrualPostingDate), posts all unposted accrual for the loan.

**Hard rule:** do not hand-edit `interest_accrual_details` / other job staging to fake summary Accrued. See `job-owned-tables.md`.

