# Loan servicing — Reopening

> Reverse a closed loan (CLOSED, FORECLOSED, WRITOFF) back to ACTIVE. Used when a closure was wrong, or a customer disputes after closure. Calls `reverseTransaction` on the closure txn + restores due_details from the closure snapshot. Maker-checker.

## Variants

| Request | XML | Use |
|---|---|---|
| `loanAccountReopening` | `loans_orc.xml` | Individual |
| `childLoanReopening` | `group_mfi_orc.xml:204` | Per-child (replayed from `REOPN` events) |
| `getLoanAccountReopeningDetails` | `loans_orc.xml` | Read history |

## Maker-checker matrix — same as foreclosure (DEFAULT / APPROVE / REJECT)

## Required input

- `loan_account_number`
- `reopening_reason` (masterdata `REASONS/LOAN_REOPENING`)
- `reversal_transaction_ref_no` — the closure txn to reverse
- `notes`

## Maker-side chain

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `valdiateLoanAccountNumberAndStatusProcessor` — must be CLOSED/FORECLOSED/WRITOFF
3. `validateTransactionForLoanAccountProcessor` (current_transaction_name=`LOAN_REOPENING`)
4. `populateReopeningDataProcessor`
5. `createOrUpdateLoanAccountReopeningDetailsProcessor` — INSERT into `loan_account_reopening_details` (status=PENDING)
6. `<API id="…submitApplication">` → approval draft
7. (no FREEZE state — loan stays CLOSED until APPROVE; less risk because already closed)
8. `<API id="createOrUpdateTask">` → checker task

## Checker (APPROVE) chain — the heavy work

(Per `group_mfi_orc.xml:204` for `childLoanReopening` — pattern identical for individual)

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `populateChildLoanReopeningAccountDataProcessor` (or individual variant)
3. `initiateClosureReversalProcessor` — orchestrates the reversal
4. `<API id="reverseTransaction">` — flips the closure txn legs (DR ↔ CR). See [transaction-reversal.md](transaction-reversal.md) for engine details
5. `updateLoanAccountClosureDetailsProcessor` — UPDATE `loan_account_closure_details` (status=REVERSED)
6. `updateLoanAccountStatusProcessor` (loan_status=`ACTIVE`) — back to active
7. `populateCurrentDateProcessor`
8. `populateEODJobDataAfterReversalProcessor` — flag for next EOD recompute
9. `checkLoanAccountInterestAndPenalAccrualProcessor` — restore accrual rows from snapshot
10. `checkLoanAccountInterestAccrualBookingProcessor` — book any accrual that should now apply (since loan is ACTIVE again)
11. `loanAccountDpdCalcProcessor` — recompute DPD (from oldest unpaid due_date, now restored)
12. `loanAccountAssetCriteriaProcessor`, `loanAccountAssetClassificationProcessor` — refresh slab/classification
13. `bookingNonPostedPenalProcessor` — book penal that should apply now

**Important:** `loan_due_details` rows that were settled by the closure are **restored** to their pre-closure state (paid_amount reverted) by the reverseTransaction's per-account write-back.

## DB writes

| Table | Action |
|---|---|
| `loan_account_reopening_details` | INSERT (PENDING) → UPDATE (APPROVED) |
| `loan_account_reopening__document` | INSERT (if reopening docs) |
| `mfi_approval.application` | INSERT (draft) → APPROVED/DELETED |
| `mfi_task.task` | INSERT → CLOSED |
| `transaction_master` (mirror) | INSERT (reversal txn) |
| `transaction_partition_details` (mirror) | INSERT N legs flipped |
| `transaction_reversal_details` | INSERT (links closure_txn ↔ reopening_txn) |
| `loan_account.loan_status` | UPDATE → `ACTIVE` (was CLOSED/FORECLOSED/WRITOFF) |
| **NB**: `loan_account.closing_date` is NOT cleared — preserved as historical record |
| `loan_account_closure_details.status` | UPDATE → REVERSED |
| `loan_due_details` | UPDATE (paid_amount/waived_amount restored to pre-closure values via reverseTransaction's write-back) |
| `loan_installment_details` | UPDATE (status restored) |
| `interest_accrual_details` | restore (re-enable accrual) |
| `loan_account.past_due_days`, `asset_*`, `npa_*` | UPDATE (recompute) |
| `loan_account_events_queue` | INSERT (`REOPN`, SHG/JLG only) |

## Status transitions

```
CLOSED / FORECLOSED / WRITOFF ──maker──► (no FREEZE; stays CLOSED) ──APPROVE──► ACTIVE

closing_date stays set (historical record)
```

## SHG/JLG variant

`childLoanReopening` (group_mfi_orc.xml:204) — same chain, plus `is_child_account=true` for the reversal txn (CG-prefixed). Triggered via `REOPN` events from parent flow.

## GL impact

The reversal txn restores the GL state to pre-closure. Net TB effect = zero (closure + reopen-reversal cancel).

## Idempotency + concurrency

- A loan in CLOSED already (no further repayments possible) → only one reopening can be in flight (validated by approval check)
- The reversal txn's idempotency comes from `transaction_reversal_details` (cannot reverse same txn twice)

## Failure modes

| Symptom | Cause | Triage |
|---|---|---|
| Reopen approved but loan stays CLOSED | `updateLoanAccountStatusProcessor` chain failed mid-execution | Check app log around timestamp; may need manual `loanAccountClosure` reversal |
| DPD wrong after reopen | Restore of `loan_due_details.paid_amount` partial | Inspect `transaction_reversal_details` for the closure txn — confirm all legs reversed |
| Accruals not restored | `checkLoanAccountInterestAccrualProcessor` skipped | Verify `interest_accrual_details` for the loan after reopen |
| SHG/JLG: child not reopened | `REOPN` event stuck at P | See [shg-jlg-children-missing runbook](../../runbooks/shg-jlg-children-missing.md) |

## Code anchors

- **Orchestration**: `loans_orc.xml::loanAccountReopening`, `group_mfi_orc.xml:204` (`childLoanReopening`)
- **Code root**: [`loan/reopening/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/reopening/)
- **Group variant**: [`loan/grouploan/reopening/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/reopening/)
- **Tables**: `loan_account_reopening_details`, `loan_account_reopening__document`

## Cross-references

- [Foreclosure & closure](../foreclosure-and-closure.md) — what's being reversed
- [Transaction reversal](transaction-reversal.md) — the underlying mechanism
- [Lifecycle](../../accounting/07-loan-account-lifecycle.md)
