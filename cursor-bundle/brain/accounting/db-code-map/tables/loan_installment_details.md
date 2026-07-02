# `mfi_accounting.loan_installment_details`

> The installment-level row. One row per installment (EMI). Holds the breakdown summary; per-component rows live in `loan_due_details`.

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `loan_account_id` | FK |
| `installment_number` | 1-based |
| `due_date` | When the EMI is due |
| `total_amount` | EMI total |
| `principal_amount`, `interest_amount`, `penal_amount`, `fee_amount` | per-component breakdown |
| `paid_amount`, `waived_amount` | cumulative settled |
| `installment_status` | OPEN / PARTIALLY_PAID / FULLY_PAID / WAIVED / etc. |
| audit cols | |

## Writers

- `CreateInstallmentAndDueDetailsProcessor` — INSERT during disbursement
- `UpdateLoanInstallmentDetailsProcessor` — UPDATE after each repayment / waiver / part-prepayment
- `UpdateLoanInstallmentDataProcessor` — UPDATE during disbursement cancellation
- Restructure / reschedule processors — REPLACE

## Readers

- `RepaymentApproppriationProcessor` (indirectly — via `loan_due_details` joined back)
- 360 view, statement generators
- EOD billing job

## Related Requests

- `disburseLoan` — initial INSERT
- `loanRepayment`, `childLoanRepayment` — UPDATE
- `loanForeclosure`, `loanPrepayment`, `*PartPrepayment` — UPDATE
- `LoanAccountRestructuring`, `loanAccountReopening` — REPLACE
- `loanDisbursementCancellation` — DELETE/UPDATE

## Related flows

- [Disbursement end-to-end](../../../flows/disbursement-end-to-end.md)
- [Repayment end-to-end](../../../flows/repayment-end-to-end.md)

## Common queries

```sql
-- All installments for a loan
SELECT installment_number, due_date, total_amount, paid_amount, installment_status
  FROM mfi_accounting.loan_installment_details
 WHERE loan_account_id = ?
 ORDER BY installment_number;
```

## Gotchas

1. **Two levels of granularity** — `loan_installment_details` is the EMI summary; `loan_due_details` has per-component (PRIN/INT/PINT/FEE) rows. Both must stay in sync.
2. **`installment_status`** is denormalised from due_details (engine sets to FULLY_PAID when all sibling due_details are settled).
