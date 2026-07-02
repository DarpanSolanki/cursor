# `mfi_accounting.loan_account_rebooking_details`

> One row per rebooking event. 19 cols. Used after `loanDisbursementCancellation` to re-issue the loan with possibly new terms.

## Schema (live, 19 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `group_id` | For SHG/JLG |
| `existing_roi`, `new_roi` | ROI change (if any) |
| `rebooking_effective_date` | When new terms apply |
| `reason`, `notes`, `reject_reason`, `reject_notes` | Free-form + masterdata |
| `rebooking_status` | PENDING / APPROVED / REJECTED |
| `task_id`, `task_status` | Maker-checker |
| `approved_on`, `approved_by`, `created_*`, `updated_*` | Audit |

Sister table: `loan_account_rebooking_details__document` (5 cols) — supporting docs.

## Writers

- `createOrUpdateLoanAccountRebookingDetailsProcessor`, `childLoanRebookingSaveAdjustmentDetailsProcessor`

## Readers

- `getLoanAccountRebookingDetails` Request
- `validateLoanAccountForRebookingProcessor` (must be in `DISB_CNCL`)

## Related flows

- [Rebooking flow](../../../flows/loan-servicing/rebooking.md)
- [Disbursement cancellation](../../../flows/loan-servicing/disbursement-cancellation.md)
