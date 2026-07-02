# `mfi_accounting.loan_account_restructuring_details`

> One row per restructuring event. 31 cols. Captures old/new EMI, tenure, ROI; reason; maker-checker audit.

## Schema (live, 31 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `restructuring_impact` | masterdata `RESTRCTRN_IMPACT/LOAN_RESTRCTRN`: `UPDATE_EMI` / `UPDATE_TENURE` / etc. |
| `rescheduling_effective_date` | When new terms apply |
| `old_emi`, `new_emi` | If UPDATE_EMI |
| `old_tenure`, `new_tenure` | If UPDATE_TENURE (months, 2-120) |
| `is_roi_changed`, `old_roi`, `new_roi` | ROI change |
| `excess_amount`, `bpi_amount`, `overdue_amount`, `due_amount`, `penal_amount`, `fee_amount` | Money at restructure time |
| `reason` | masterdata `REASONS/LOAN_RESTRCTRN` |
| `notes`, `reject_reason`, `reject_notes` | Free-form |
| `restructuring_status` | PENDING / APPROVED / REJECTED |
| `task_id`, `task_status` | Maker-checker |
| `approved_on`, `approved_by`, `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- `createOrUpdateLoanAccountRestructuringDetailsProcessor` — INSERT (PENDING) → UPDATE (APPROVED)
- `executeRestructureProcessor` — applies the new schedule (uses this row's data)

## Readers

- `getLoanAccountRestructuringList`, `getLoanAccountRestructuringDetails` Requests
- `validatePendingLoanAccountRestructuringProcessor` — only one in flight per loan

## Related flows

- [Restructuring flow](../../../flows/loan-servicing/restructuring.md)
