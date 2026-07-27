# `mfi_accounting.transaction_master`

> The transaction header. Every `postTransaction` call writes one row here, then N partition rows in `transaction_partition_details` (one DR + one CR per leg), then per-account rows in `transaction_details`.

## Purpose

Top-level row for any GL-affecting transaction (disbursement, repayment, accrual posting, foreclosure, manual JE, refund, reversal).

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` | PK |
| `transaction_ref_no` | Server-generated unique ref; surfaced to caller for tracking |
| `client_reference_number` | Caller-supplied idempotency key (rejected if duplicate) |
| `transaction_catalogue_id` | FK → `transaction_catalogue.id` (which named transaction this is) |
| `total_amount` | Sum of leg amounts on one side |
| `currency`, `office_id`, `originating_office_id` | Tenant/office context |
| `run_mode` | `TRIAL` (no DB persist) or `REAL` |
| `status` | Posting status |
| `created_on`, `created_by` | Audit |

(Run `tools/inspect-table.sh transaction_master` for full schema.)

## JPA entity

[`transaction/entity/TransactionMasterEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/entity/TransactionMasterEntity.java) (path inferred — verify with grep)

## Writers

| Processor | Action | Triggered by |
|---|---|---|
| [`CreateTransactionMasterProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/processor/CreateTransactionMasterProcessor.java) | INSERT | `postTransaction` REAL mode |
| [`ReverseTransactionProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/reverse/processor/ReverseTransactionProcessor.java) | INSERT (mirror txn) | `reverseTransaction` |
| [`DoGLTransferProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/portfoliotransfer/processor/DoGLTransferProcessor.java) | INSERT | `doGLTransfer` (portfolio transfer) |

## Readers

- `clientReferenceNumberDedupProcessor` — dedup check before INSERT
- `getTransactionPartitionDetailsProcessor` — for `getTransactionPartitionDetails` Request
- `getAccountStatementProcessor` — joins transaction + partition_details + transaction_details
- Audit / reporting reads

## Related Requests

- `postTransaction` (product_transaction_orc.xml:3) — primary writer (always called via `<API>` from other Requests)
- `reverseTransaction` — reversal writer
- `getAccountStatement`, `getLoanAccountStatement` — readers
- `postManualJournalEntry` — calls `postTransaction` internally
- `doGLTransfer` — direct writer

Indirect writers (anything that calls `<API id="postTransaction">`):
- `disburseLoan` (PARENT_SUCCESS stage)
- `loanRepayment`, `childLoanRepayment`
- `interestAccrualPosting`, `penalInterestAccrualBooking` (per accrual row)
- `loanForeclosure`, `loanPrepayment`, `individualChildLoanForeclosure`
- `loanAccountPartPrepayment`, `childLoanRebookingAdjustmentTransaction`
- `loanDisbursementCancellation`, `childLoanDisbursementCancellation`
- `loanAccountTransactionReversal`, `childLoanTransactionReversal`
- `loanAccountExcessAmountRefund`, `childLoanAccountExcessAmountRefund`

## Related flows

- [Money flow — rupee journey](../../../system/04-money-flow-rupee-journey.md)
- [GL posting engine](../../08-gl-posting-engine.md)
- [Repayment end-to-end](../../../flows/repayment-end-to-end.md)

## Common queries

```sql
-- A txn header
SELECT * FROM mfi_accounting.transaction_master WHERE transaction_ref_no = ?;

-- Recent txns for one loan
SELECT tm.transaction_ref_no, tm.transaction_catalogue_id, tm.total_amount, tm.created_on
  FROM mfi_accounting.transaction_master tm
  JOIN mfi_accounting.transaction_partition_details tpd ON tpd.transaction_master_id = tm.id
  WHERE tpd.entity_id = (SELECT account_id FROM mfi_accounting.loan_account la JOIN mfi_accounting.account a ON a.id=la.account_id WHERE a.account_number = ?)
  GROUP BY tm.id, tm.transaction_ref_no, tm.transaction_catalogue_id, tm.total_amount, tm.created_on
  ORDER BY tm.created_on DESC LIMIT 50;
```

## Gotchas

1. **Dedup on `client_reference_number`** — caller must use the same value to retry; using a fresh value will double-post.
2. **`run_mode=TRIAL`** doesn't INSERT here — no row exists for trial calls.
3. **Reversal creates a NEW row**, doesn't modify the original. The link is in `transaction_reversal_details` / `transaction_reversal__document`.
