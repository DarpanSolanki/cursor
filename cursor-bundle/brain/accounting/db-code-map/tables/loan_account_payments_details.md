# `mfi_accounting.loan_account_payments_details`

> The payment-event ledger. One row per `loanRepayment` / `childLoanRepayment` / prepayment / foreclosure call. Holds the **excess_amount carried forward**.

## Purpose

Audit trail of every payment received. Each row captures: total received, per-component breakdown, excess (paid over due), payment mode, source, repayment_mode, etc. Joined with `loan_due_details` via `loan_due_details__loan_account_payments_details` for "which dues did this payment settle".

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` | PK |
| `loan_account_id` | FK |
| `payment_amount` | Total received |
| `principal_amount`, `interest_amount`, `penalty_amount`, `fee_amount` | Per-component (after appropriation) |
| `excess_amount` | Carried forward; auto-applied to next due via `loanAdvanceRepayment` |
| `suspense_amount` | Set when loan in NPA — interest portion that goes to suspense GL |
| `repayment_mode`, `payment_mode`, `payment_ref` | How and where |
| `value_date`, `created_on`, `created_by` | |
| `transaction_master_id` | FK link to the GL posting that this payment caused |

## Writers

- `createLoanAccountPaymentsDetailsProcessor` — INSERT after every successful repayment / prepayment / foreclosure
- `updateExcessAmountForPrepaymentProcessor` — adjusts excess on prepayment

## Readers

- 360 views, customer statement
- `loanAdvanceRepayment` — reads excess and applies to next due
- Refund flow — reads excess_amount

## Related Requests

- `loanRepayment`, `childLoanRepayment`, `loanAdvanceRepayment` — primary writer
- `loanForeclosure`, `individualChildLoanForeclosure`, `loanAccountPartPrepayment`, `childLoanPartPrepayment` — also write
- `loanAccountExcessAmountRefund` — reads + creates a refund payment
- `loanAccountTransactionReversal` — reverses a payment

## Related flows

- [Repayment end-to-end](../../../flows/repayment-end-to-end.md)
- [Foreclosure & closure](../../../flows/foreclosure-and-closure.md)

## Common queries

```sql
-- Recent payments for a loan
SELECT created_on, payment_amount, principal_amount, interest_amount, excess_amount, repayment_mode
  FROM mfi_accounting.loan_account_payments_details
 WHERE loan_account_id = ?
 ORDER BY created_on DESC LIMIT 20;

-- Payments with excess (could be refundable)
SELECT loan_account_id, created_on, payment_amount, excess_amount
  FROM mfi_accounting.loan_account_payments_details
 WHERE excess_amount > 0
 ORDER BY created_on DESC LIMIT 50;
```

## Gotchas

1. **`suspense_amount` populated only for NPA loans** — interest is shunted to suspense GL instead of credited to interest income.
2. **`excess_amount` is the running excess pool** — auto-applied to next due by `loanAdvanceRepayment` batch.
3. **Per-call snapshot** — the per-component split is what the appropriation algorithm decided at that point in time; recomputing now might give different answers.
