# `mfi_accounting.loan_disbursement_transaction`

> Per-disbursement-attempt record. 13 cols. Links to the GL `transaction_master` and to the disbursement-mode details. Survives the 9-stage state machine.

## Schema

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `transaction_date`, `value_date` | Posting + effective dates |
| `amount` | Disbursement amount |
| `transaction_reference_number` | Server-generated |
| `client_reference_number` | Idempotency key (matches `transaction_master.client_reference_number`) |
| `loan_disbursement_details_id` | FK → `loan_disbursement_mode_details.id` |
| `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- Disbursement chain — INSERT at each disbursement attempt (initial + retries)

## Readers

- `getLoanAccountDisbursmentTransactions` Request
- 360 view, statement
- Bank-call retry job (reads to know what to retry)

## Related flows

- [Disbursement end-to-end](../../../flows/disbursement-end-to-end.md)
