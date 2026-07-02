# `mfi_accounting.loan_account_noc_details`

> One row per NOC issued to the customer (or blocked). 11 cols. Created at loan closure.

## Schema (live, 11 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `reference_number` | NOC number (printed on the certificate) |
| `noc_status` | PENDING / GENERATED / DISPATCHED / DELIVERED / BLOCKED / UNBLOCKED |
| `approved_*`, `created_*`, `updated_*`, `is_deleted` | Audit |

Sister tables:

- `loan_account_noc_details_block_unblock_reason` — audit trail of block/unblock events
- `loan_account_noc_dispatch_details` (14 cols) — courier + POD + delivery dates

## Writers

- `createLoanAccountClosureDetailsProcessor` chain — INSERT (PENDING) at closure
- `generateNocFileJob` — UPDATE → GENERATED, sets `reference_number`
- `bulkSGToNocBlockUnblockJob` — UPDATE BLOCKED/UNBLOCKED

## Readers

- `getLoanAccountNocDetails` Request
- 360 view, customer statement
- `loan_account.noc_document_id` — points back to the DMS doc once generated

## Related Requests

- `loanForeclosure`, `loanAccountAutoClosure` — write at closure
- `generateNocFileJob` (scheduled) — generate the file
- `bulkFileToSGNocBlockUnblockJob`, `bulkSGToNocBlockUnblockJob` — bulk block/unblock
- `getLoanAccountNocDetails`, `viewBulkNocBlockUnblockFileStatus`, `downloadNocBlockUnblockUploadedFile` — UI

## Related flows

- [Foreclosure & closure](../../../flows/foreclosure-and-closure.md) — final NOC step
- [Death foreclosure](../../../flows/loan-servicing/death-foreclosure.md)

## Gotchas

1. **NOC generated only after `loan_status=CLOSED`** — not at FORECLOSED.
2. **Blocked NOCs** — typically due to ops dispute; cannot dispatch until unblocked.
