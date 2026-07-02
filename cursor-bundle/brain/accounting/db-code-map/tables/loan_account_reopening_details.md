# `mfi_accounting.loan_account_reopening_details`

> One row per reopening event. 14 cols. Used to reverse a closure (CLOSED/FORECLOSED/WRITOFF → ACTIVE).

## Schema (live, 14 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `reason`, `notes` | |
| `status` | PENDING / APPROVED / REJECTED |
| `reopening_effective_date` | When reopen takes effect |
| `task_id`, `task_status` | Maker-checker |
| `approved_on`, `approved_by`, `created_*`, `updated_*` | Audit |

Sister: `loan_account_reopening__document` — supporting docs.

## Writers

- `createOrUpdateLoanAccountReopeningDetailsProcessor`

## Readers

- `getLoanAccountReopeningDetails` Request

## Related flows

- [Reopening flow](../../../flows/loan-servicing/reopening.md)
