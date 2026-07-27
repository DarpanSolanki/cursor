# Loan servicing — Transaction Reversal

> Reverse a previously-posted transaction (most often a wrong repayment, mis-tagged collection, or operator error). Single-loan + bulk-file paths. Maker-checker. Replays a mirror txn via `reverseTransaction` to flip every leg's DR/CR.

## Variants

| Request | XML | Use |
|---|---|---|
| `loanAccountTransactionReversal` | `loans_orc.xml` | Single-loan, single-txn reversal |
| `childLoanTransactionReversal` | `group_mfi_orc.xml:377` | Per-child variant (replayed from `TXNREV` events) |
| `bulkFileToSGTransactionReversalJob` | `loans_orc.xml` | Ingest a CSV of reversal requests |
| `bulkSGToTransactionReversalJob` | `loans_orc.xml` | Apply staged reversal rows |
| `viewBulkTransactionReversalFileStatus`, `downloadTransactionReversalUploadedFile` | `loans_orc.xml` | Bulk-upload UI |
| `reverseTransaction` | `product_transaction_orc.xml` | Low-level reversal of a `transaction_master` row (called by all of the above) |
| `proactiveReverseTransaction` | `ServiceOrchestrationXML.xml` | Auto-reverse for proactive refund flows |

## Function code matrix (loanAccountTransactionReversal)

| `function_code` | Branch |
|---|---|
| `DEFAULT` | Maker submit — creates task |
| `APPROVE` | Checker approves — executes the reversal |
| `REJECT` | Checker rejects — closes task without action |

`run_mode = TRIAL` validates only; `REAL` commits.

## Required input

- `transaction_ref_no` — the original txn to reverse (links to `transaction_master.transaction_ref_no`)
- `account_number` — the loan account
- `transaction_reversal_date` (epoch ms)
- `transaction_value_date` (epoch ms) — backdate effective date
- `channel_code`
- `transaction_amount` (must match original)
- `client_reference_number` — idempotency key
- `reason` — masterdata `REASONS/TRNS_REVL`
- Per-component breakdowns: `excess_amount`, `principal_amount`, `interest_amount`, `fee_amount`, `penalty_amount`

## Maker-side chain (function_code=DEFAULT, run_mode=REAL)

(Per `loans_orc.xml::loanAccountTransactionReversal`)

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. **Flag controls** — `dummyProcessor` sets `create_task=true, validate_task=true`
3. `validatePendingTxnReversalTaskProcessor` — refuse if a reversal for the same txn is already pending (reversal_process=true scope)
4. `validateTransactionForLoanAccountProcessor` (current_transaction_name=`TXN_REVERSAL`) — guard against inactive loans
5. `validateTransactionExcessAmountProcessor` — sanity-check the per-component split sums to the transaction_amount
6. **Validate the original txn exists + reversible**:
   - Fetch `transaction_master` by `transaction_ref_no`
   - Confirm it hasn't already been reversed (no row in `transaction_reversal_details` for this txn)
   - Confirm enough excess/balance to cover the reversal
7. `createTaskWorkFlowHelpingProcessor` — INSERT into `mfi_task.task` (workflow_master_code=`TXN_REVERSAL`)
8. `<API id="…submitApplication">` → approval draft
9. Notification + response_code=30003

## Checker-side (APPROVE) chain — the heavy work

1. `populateUserDetails`, `setCommonAttributesProcessor`, flag controls (`approve_task=true`)
2. **Re-validate** — same guards as maker (defense in depth)
3. `populateLoanAccountPaymentDetailsDataProcessor` — pull the original payment row (if reversal is on a repayment)
4. `executeTransactionReversalProcessor` — orchestrates the reversal
5. `<API id="reverseTransaction">` (product_transaction_orc.xml::reverseTransaction):
   - Reads original `transaction_master` + all `transaction_partition_details` legs
   - INSERTS new `transaction_master` row with `transaction_ref_no` like `<original>_REV` (or unique pattern)
   - INSERTS new `transaction_partition_details` rows — **same accounts, same amounts, FLIPPED `cr_dr_indicator`** (D↔C)
   - INSERTS new `transaction_details` per affected account
   - UPDATES `account_balance` accordingly
   - INSERTS into `transaction_reversal_details` linking original → reversal
   - INSERTS into `transaction_reversal__document` if reversal-supporting docs uploaded
6. `populateEODJobDataAfterReversalProcessor` — flags loan for next EOD recompute (DPD/asset criteria)
7. `convertTransactionValueDateProcessor` — adjust value-date semantics
8. `createLoanAccountPaymentsDetailsProcessor` — INSERT a payment row tagged as reversal
9. **Recompute loan state**:
   - `loanAccountDpdCalcProcessor` — DPD likely increases (reversed payment no longer counted)
   - `loanAccountAssetCriteriaProcessor` + `loanAccountAssetClassificationProcessor` — slab + classification refresh
   - `bookingNonPostedPenalProcessor` — book any penal that should now apply (since DPD jumped)
10. `loan_account.loan_status` — typically stays `ACTIVE` unless the reversed txn was the foreclosure (then back to `ACTIVE` from `CLOSED` if applicable)
11. Update task → CLOSED, delete approval draft

## SHG/JLG variant (`childLoanTransactionReversal`, group_mfi_orc.xml:377)

```
executeTransactionReversalProcessor
populateEODJobDataAfterReversalProcessor
populateLoanAccountPaymentDetailsDataProcessor
reverseTransactionProcessor   ← per child
convertTransactionValueDateProcessor
createLoanAccountPaymentsDetailsProcessor
loanAccountDpdCalcProcessor
loanAccountAssetCriteriaProcessor
loanAccountAssetClassificationProcessor
```

Triggered from parent flow via `TXNREV` event in `loan_account_events_queue`. `is_child_account=true` ensures CG-prefixed GLs.

## Bulk reversal flow

```
1. Operator uploads CSV via webapp
   ↓
2. bulkUploadBatch → INSERT file_staging_transaction_reversal rows
   ↓
3. bulkFileToSGTransactionReversalJob — validate per-row, mark BAD/READY
   ↓
4. bulkSGToTransactionReversalJob (scheduled) — for each READY row:
     ↓
   ValidateBulkTransactionReversalBusinessCasesService — per-row business validation
   ↓
   Calls loanAccountTransactionReversal Request internally with function_code=DEFAULT then APPROVE
     (skipping maker-checker UI since it's bulk-approved by ops sign-off)
   ↓
   Updates file_staging_transaction_reversal.status to PROCESSED / FAILED + error_message
```

## DB writes (in order, single reversal)

| Table | Action | Trigger |
|---|---|---|
| **— maker —** | | |
| `mfi_task.task` | INSERT | maker submit |
| `mfi_approval.application` | INSERT (draft) | maker submit |
| **— checker APPROVE —** | | |
| `transaction_master` | INSERT (mirror txn) | `reverseTransaction` |
| `transaction_partition_details` | INSERT N legs (DR/CR flipped) | same |
| `transaction_metadata` | INSERT | same |
| `transaction_details` + `account_balance` | per-account UPDATE | same |
| `transaction_reversal_details` | INSERT (original_txn_id ↔ reversal_txn_id, reason, reversal_date, value_date) | `executeTransactionReversalProcessor` |
| `transaction_reversal__document` | INSERT (if docs) | document chain |
| `loan_account_payments_details` | INSERT (negative-payment row tagged reversal) | `createLoanAccountPaymentsDetailsProcessor` |
| `loan_due_details` | UPDATE — `paid_amount` decremented (the reversed amount goes back into pending) | (inside executeTransactionReversalProcessor) |
| `loan_installment_details` | UPDATE — installment_status restored | same |
| `loan_account.past_due_days`, `asset_*`, `npa_*` | UPDATE (recompute) | DPD/criteria/classification |
| `loan_account.loan_status` | UPDATE (rare — only if reversed a closure → re-open) | `updateLoanAccountStatusProcessor` |
| `mfi_task.task` | UPDATE → CLOSED | task close |
| `mfi_approval.draft_application` | DELETE | `deleteDraftProcessor` |
| `loan_account_events_queue` | INSERT (`TXNREV`, SHG/JLG only) | `ChildLoanTxnReversalEventGenerationProcessor` |

## GL impact

The mirror txn IS the GL impact — every leg has its `cr_dr_indicator` flipped. Net effect on TB: zero (original txn + reversal txn cancel each other out in `trial_balance` aggregations).

Example for reversing a ₹5000 repayment:

```
Original txn:                          Reversal txn:
  DR  CUSTOMER_AC          5000          DR  LOAN_PRIN_AC          3000
  CR  LOAN_PRIN_AC         3000          DR  INT_INCOME_AC          2000
  CR  INT_INCOME_AC        2000          CR  CUSTOMER_AC           5000
```

## Idempotency + concurrency

- **`client_reference_number`** on the reversal request — prevents duplicate reversal requests
- **`validatePendingTxnReversalTaskProcessor`** — refuses if the same txn already has a pending reversal task
- **Original txn cannot be reversed twice** — checked via `transaction_reversal_details` lookup
- **Per-loan exclusive** — reversal task creation locks against concurrent reversals on the same loan via task uniqueness

## Failure modes

| Symptom | Cause | Triage |
|---|---|---|
| "Already reversed" error | Reversal_details row exists for the txn | Cannot reverse twice; if reversal needs reversing, do another reverse on the reversal txn |
| Trial balance off after reversal | Original txn legs and reversal legs don't perfectly mirror | See [trial-balance-imbalance runbook](../../runbooks/trial-balance-imbalance.md) — reversal symmetry is engine-enforced; bug indicates corrupt original |
| DPD wrong after reversal | `loanAccountDpdCalcProcessor` ran but value-date adjustment off | Verify `transaction_value_date` was correctly back-dated |
| Bulk reversal row stays BAD | Per-row validation failed | Check `file_staging_transaction_reversal.error_message` |
| SHG/JLG: child not reversed | `TXNREV` event stuck at `P` | See [shg-jlg-children-missing runbook](../../runbooks/shg-jlg-children-missing.md) |

## Code anchors

- **Orchestration**: `loans_orc.xml::loanAccountTransactionReversal`, `group_mfi_orc.xml:377` (`childLoanTransactionReversal`), `product_transaction_orc.xml::reverseTransaction`
- **Engine**: [`transaction/reverse/processor/ReverseTransactionProcessor.java`](../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/reverse/processor/ReverseTransactionProcessor.java)
- **Loan-side**: [`loan/transactionreversal/processor/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/transactionreversal/processor/) — `ExecuteTransactionReversalProcessor`, `ValidateTransactionReversalDataProcessor`
- **Bulk service**: [`loan/transactionreversal/service/ValidateBulkTransactionReversalBusinessCasesService.java`](../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/transactionreversal/service/ValidateBulkTransactionReversalBusinessCasesService.java)
- **Bulk job**: [`batchnew/bulktransactionreversal/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/bulktransactionreversal/)
- **Group event generator**: [`loan/grouploan/txnreversal/processor/ChildLoanTxnReversalEventGenerationProcessor.java`](../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/txnreversal/processor/ChildLoanTxnReversalEventGenerationProcessor.java)
- **Tables**: `transaction_reversal_details`, `transaction_reversal__document`, `file_staging_transaction_reversal`. Plus the `transaction_*` family (see [tables/](../../accounting/db-code-map/tables/transaction_master.md))

## Cross-references

- [Money flow §reversal](../../system/04-money-flow-rupee-journey.md)
- [Reopening](reopening.md) — special case: reversing a closure transaction re-opens the loan
- [Excess amount refund](excess-amount-refund.md) — sometimes the right answer instead of reversal
- [Maker-checker](../maker-checker.md)
