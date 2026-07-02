# `mfi_accounting.loan_account_closure_details`

> One row per loan-closure event (foreclosure / write-off / auto-closure / death-foreclosure). 11 cols. Holds the closure txn ref + reversal linkage (for reopening).

## Schema (live, 11 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `transaction_reference_number` | The closure `transaction_master.transaction_ref_no` |
| `identifier_type`, `identifier_value` | Source event type + id (e.g. `FORECLOSURE` + `prepayment_details.id`) |
| `reversal_transaction_reference_number` | Set when reopening reverses the closure |
| `is_reversed` | Boolean — true when reopened |
| `client_reference_number` | Idempotency key |
| `excess_amount` | Money left over at closure (auto-refund candidate) |
| `paid_by_customer`, `paid_by_insurance_company` | Money source breakdown (for death-fc) |

## Writers

- `createLoanAccountClosureDetailsProcessor` — INSERT at closure
- `pushLoanAccountClosureDetailsProcessor` — same
- Reopening flow — UPDATE `is_reversed=true`, set `reversal_transaction_reference_number`

## Readers

- `loanAccountReopening` flow — reads to know what to reverse
- 360 view, customer statement
- `loanAccountClosure` batch — picks up FORECLOSED-but-not-CLOSED loans for auto-closure retry
- Reporting (closure type analysis)

## Related Requests

- `loanForeclosure`, `loanAccountAutoClosure`, `loanAccountClosure` (batch), `loanWriteoff`, `loanDeathForeclosure` — writers
- `loanAccountReopening` — UPDATE reverser

## Related flows

- [Foreclosure & closure](../../../flows/foreclosure-and-closure.md)
- [Reopening](../../../flows/loan-servicing/reopening.md)
- [Write-off](../../../flows/loan-servicing/write-off.md)
- [Death foreclosure](../../../flows/loan-servicing/death-foreclosure.md)

## Common queries

```sql
-- Recent closures + their type
SELECT a.account_number, lcd.identifier_type, lcd.transaction_reference_number,
       lcd.excess_amount, lcd.is_reversed, la.loan_status, la.cancelled_on
  FROM mfi_accounting.loan_account_closure_details lcd
  JOIN mfi_accounting.loan_account la ON la.account_id = lcd.loan_account_id
  JOIN mfi_accounting.account a ON a.id = la.account_id
 ORDER BY lcd.id DESC LIMIT 20;
```

## Gotchas

1. **Single row per closure event** — re-closing after reopen creates a NEW row.
2. **`is_reversed=true`** indicates the loan went through a reopening at some point.
3. **`excess_amount`** here is a snapshot; `loan_account.excess_amount` may change after subsequent ops.
