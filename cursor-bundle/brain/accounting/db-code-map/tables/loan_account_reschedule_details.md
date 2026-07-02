# `mfi_accounting.loan_account_reschedule_details`

> Internal scratch table for the reschedule batch. 16 cols. Created during part-prepayment / restructuring; processed by `loanAccountRescheduleBatchProcessor`. Holds the proposed new schedule until it's applied.

## Schema (live, 16 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `identifier_type`, `identifier_id` | Source event link (e.g. `PART_PREPAYMENT` + `loan_account_part_prepayment_details.id`) |
| `start_date`, `maturity_date` | New start + new end |
| `rescheduling_handling_type` | How dues are recomputed |
| `emi_amount`, `number_of_installments`, `interest_rate` | New schedule parameters |
| `batch_status` | PENDING / RUNNING / COMPLETED / FAILED |
| `batch_report` | Free-form result summary (TEXT) |
| `created_*`, `updated_*` | Audit |

## Writers

- `registerLoanAccountRescheduleEventProcessor` — INSERT (PENDING)
- `loanAccountRescheduleBatchProcessor` — UPDATE batch_status as it processes
- `rescheduleLoanAccountRescheduleBatch` Request — also picks up pending rows

## Readers

- `loanAccountRescheduleBatchProcessor` (the processor itself)

## Related Requests

- `registerLoanAccountRescheduleEvent`, `rescheduleLoanAccountRescheduleBatch`
- Triggered by `loanAccountPartPrepayment`, `loanAccountRestructuring` (and child variants)

## Related flows

- [Part-prepayment](../../../flows/loan-servicing/part-prepayment.md), [Restructuring](../../../flows/loan-servicing/restructuring.md)

## Gotchas

1. **Internal queue, not user-facing** — operators don't see this directly.
2. **`batch_status='FAILED'`** = reschedule didn't apply; need to re-run via `rescheduleLoanAccountRescheduleBatch`.
