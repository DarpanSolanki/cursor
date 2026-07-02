# `mfi_accounting.loan_repayment_schedule_details`

> The **immutable** master repayment schedule — what was originally agreed at disbursement. Modified only by reschedule / restructure events. Distinct from the live, mutable `loan_installment_details`.

## Purpose

Snapshot of the schedule generated at disbursement. Kept as historical reference even as `loan_installment_details` evolves through repayments / part-prepayments / waivers. Used for the "original commitment" view in 360 + reporting.

## Writers

- `customCallRepaymentScheduleGenerateProcessor` — INSERT during `disburseLoan`
- `LoanAccountRestructuringProcessor` — REPLACE on restructure
- Reschedule processors — REPLACE on reschedule

## Readers

- 360 view (original schedule comparison)
- Reporting

## Related Requests

- `disburseLoan`, `LoanAccountRestructuring`, `loanAccountReopening`, reschedule batch

## Related flows

- [Disbursement end-to-end](../../../flows/disbursement-end-to-end.md)

## Gotchas

1. **NOT the live schedule** — reads here show the original/restructured agreement, not "what's owed now". Use `loan_due_details` for that.
2. **Replaced wholesale on restructure** — old rows are deleted (or marked deprecated).
