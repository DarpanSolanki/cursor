# `mfi_accounting.waiver_details`

> One row per waiver event. 17 cols. Parent record; per-due breakdown lives in `waiver__loan_due_details`.

## Schema

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `loan_due_details_id` | (FK if single-due waiver) |
| `is_fully_waived`, `waiver_percentage`, `waiver_amount` | Waiver math |
| `ext_ref_number` | External ref |
| `waiver_status` | PENDING / APPROVED / REJECTED |
| `task_id`, `task_status` | Maker-checker |
| `transaction_ref_no` | Linked GL hit |
| `is_reversed` | Boolean — true if waiver itself was reversed |
| `notes` | |
| `created_*`, `updated_*` | Audit |

## Sister table

[`waiver__loan_due_details`](waiver__loan_due_details.md) — per-due breakdown (one waiver can clear N dues).

## Writers

- `createOrUpdateWaiverDetailsProcessor` — INSERT (PENDING) → UPDATE (APPROVED)

## Readers

- 360 view

## Related flows

- [Waiver](../../../flows/loan-servicing/waiver.md)
