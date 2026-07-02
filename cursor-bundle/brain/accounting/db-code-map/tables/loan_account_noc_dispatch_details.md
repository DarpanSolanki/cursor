# `mfi_accounting.loan_account_noc_dispatch_details`

> Courier-tracking row for an issued NOC. 14 cols. One row per dispatch attempt.

## Schema

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `courier_name`, `pod_number` | Courier + tracking |
| `dispatch_date`, `delivery_date` | When |
| `remarks` | Free-form |
| `approved_*`, `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- `bulkSGToDispatchDetailsJob` — bulk dispatch records from courier API/file
- `createOrUpdateDocDispatchTask` (LOS-side, but NOC dispatch can come from accounting)

## Related Requests

- `bulkFileToSGDispatchDetailsJob`, `bulkSGToDispatchDetailsJob`, `viewBulkDispatchDetailsFileStatus`, `downloadDispatchDetailsUploadedFile`

## Related flows

- [Foreclosure & closure](../../../flows/foreclosure-and-closure.md) §NOC issuance
