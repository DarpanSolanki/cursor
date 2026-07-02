# `mfi_accounting.loan_disbursement_mode_details`

> Per-loan, the disbursement target — where the money actually goes. 18 cols. NEFT/STP details.

## Schema

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `mode` | NEFT / RTGS / STP / IMPS / CASH / etc. |
| `account_type`, `account_number`, `account_holder_name` | Beneficiary |
| `routing_type`, `routing_value` | IFSC etc. |
| `bank_name`, `bank_customer_id` | |
| `utr_number` | Bank ref after success |
| `approved_*`, `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- Disbursement DEFAULT stage (`disburseLoan`)
- Bank callback handlers — UPDATE `utr_number` on success

## Readers

- Bank-call processors during disbursement, `accountingBankServiceRetryJob`
- 360 view

## Related flows

- [Disbursement end-to-end](../../../flows/disbursement-end-to-end.md)
- Sister: `loan_disbursement_transaction` for per-attempt records
