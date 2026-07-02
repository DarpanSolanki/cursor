# `mfi_accounting.transaction_reversal_details`

> One row per transaction-reversal request. 31 cols. The maker-checker workflow row + per-component breakdown of what's being reversed.

## Schema (live, 31 cols — selected)

### Identity + amounts
| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `transaction_ref_no` | The original txn being reversed |
| `transaction_date`, `transaction_value_date`, `transaction_reversal_date` | Dates |
| `transaction_amount` | Total |
| `transaction_type`, `transaction_sub_type`, `currency`, `description` | Categorisation |
| `channel_code`, `receipt_number` | External refs |
| `excess_amount`, `principal_amount`, `interest_amount`, `penalty_amount`, `fee_amount` | Per-component split (must sum to `transaction_amount`) |
| `reason`, `notes` | masterdata + free-form |

### Workflow + audit
| Column | Meaning |
|---|---|
| `reversal_status` | PENDING / APPROVED / REJECTED / PROCESSED |
| `task_id`, `task_status` | Maker-checker |
| `reject_reason` | If rejected |
| `approved_*`, `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- `executeTransactionReversalProcessor` — INSERT (PENDING) on maker; UPDATE on checker
- `validateTransactionReversalDataProcessor` — pre-validates

## Readers

- `validatePendingTxnReversalTaskProcessor` — refuses if same txn already has a pending reversal here
- 360 view

## Related flows

- [Transaction reversal](../../../flows/loan-servicing/transaction-reversal.md) — single + bulk

## Common queries

```sql
-- Pending reversals in flight
SELECT a.account_number, trd.transaction_ref_no, trd.transaction_amount,
       trd.reversal_status, trd.created_on
  FROM mfi_accounting.transaction_reversal_details trd
  JOIN mfi_accounting.loan_account la ON la.account_id = trd.loan_account_id
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE trd.reversal_status IN ('PENDING','APPROVED')
 ORDER BY trd.created_on;
```

## Gotchas

1. **The mirror txn itself lives in `transaction_master`** — this table is the workflow row; the GL hit is in `transaction_master` + `transaction_partition_details`.
2. **Per-component sum constraint** — `excess_amount + principal_amount + interest_amount + penalty_amount + fee_amount = transaction_amount` (validator enforces).
3. **`reversal_status='PROCESSED'`** = the mirror txn has been posted.
