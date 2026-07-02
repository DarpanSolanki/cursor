# `mfi_accounting.loan_account_excess_amount_refund_details`

> One row per refund event of `loan_account.excess_amount` to customer. 24 cols. Standard (maker-checker) and proactive (auto-batch) flows both write here.

## Schema (live, 24 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `refund_effective_date` | When refund is recognised |
| `refund_mode` | NEFT / UPI / CASH / BANK_TRANSFER |
| `payment_mode` | Channel-specific |
| `total_refund_amount` | Money refunded |
| `reason`, `notes` | |
| `casa_account_number`, `bank_name`, `beneficiary_name`, `account_type`, `routing_type`, `routing_value` | Beneficiary details |
| `utr_number` | Bank ref after success |
| `status` | PENDING / APPROVED / PROCESSED / FAILED / REVERSED |
| `task_id`, `task_status` | Maker-checker (NULL for proactive) |
| `approved_on`, `approved_by`, `created_*`, `updated_*` | Audit |

## Writers

- `createOrUpdateLoanAccountExcessAmountRefundProcessor` — INSERT (PENDING) → UPDATE
- `populateChildLoanAccountExcessAmountRefundDataProcessor` (SHG/JLG)
- Proactive batch: `proactiveExcessAmountRefund` Request

## Readers

- `getLoanAccountExcessAmountRefundDetails`, `getLoanAccountExcessAmountRefundList` Requests
- Vendor inbound reverse-feed (if refund fails, reads to find the row to reverse)

## Related flows

- [Excess amount refund](../../../flows/loan-servicing/excess-amount-refund.md)

## Common queries

```sql
-- Refunds in flight
SELECT a.account_number, eard.total_refund_amount, eard.status, eard.refund_mode, eard.created_on
  FROM mfi_accounting.loan_account_excess_amount_refund_details eard
  JOIN mfi_accounting.loan_account la ON la.account_id = eard.loan_account_id
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE eard.status IN ('PENDING','APPROVED')
 ORDER BY eard.created_on;
```
