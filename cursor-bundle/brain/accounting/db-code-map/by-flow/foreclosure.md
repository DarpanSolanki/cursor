# Foreclosure → tables touched

Flow narrative: [`../../../flows/foreclosure-and-closure.md`](../../../flows/foreclosure-and-closure.md)

`loanForeclosure` (loans_orc.xml / mfi_orc.xml) for individual loans; `childLoanForeclosure` → `individualChildLoanForeclosure` (group_mfi_orc.xml:256) for SHG/JLG members.

## Maker-side (function_code=DEFAULT)

| Step | Table | Action |
|---|---|---|
| 1 | `loan_account.loan_status` | UPDATE → `FORECLOSURE_FREEZE` |
| 2 | `prepayment_details` | INSERT (proposed prepayment) |
| 3 | `prepayment_charge_details` | INSERT (foreclosure charge + tax) |
| 4 | `mfi_approval.application` | INSERT (draft via `loanForeclosure_submitApplication`) |
| 5 | `mfi_task.task` | INSERT (checker task) |

## Checker-side (function_code=APPROVE) — the heavy chain

| Step | Table | Action | Processor |
|---|---|---|---|
| 6 | (pending interest) `interest_accrual_details` | UPDATE `last_accrual_posted_date` | `checkLoanAccountInterestAccrualBookingProcessor` |
| 7 | (pending penal) `penal_interest_accrual_details` + `loan_due_details` (PINT INSERT) | book non-posted | `bookingNonPostedPenalProcessor` |
| 8 | `loan_due_details` | UPDATE (mark fully paid) | `updateDueDetailsForPrepaymentProcessor` |
| 9 | `loan_account_charge_details` | INSERT (foreclosure charge entry) | charge processors |
| 10 | `loan_account_tax_details` | INSERT (tax on charge) | tax processors |
| 11 | `transaction_master` | INSERT (`<API id="postTransaction">` with txn_catalogue=LOAN_PREPAYMENT or FORECLOSE) | `CreateTransactionMasterProcessor` |
| 12 | `transaction_partition_details` | INSERT N legs (DR customer / CR principal + interest + fc charge + tax) | `CreateTransactionPartitionDetailsProcessor` |
| 13 | `transaction_details` + `account_balance` | per affected account | `CreateTransactionDetailsProcessor` |
| 14 | `loan_account.loan_status` | UPDATE → `FORECLOSED`; `cancelled_on` set | `updateLoanAccountStatusProcessor` |
| 15 | `loan_account_payments_details` | INSERT (foreclosure payment) | `createLoanAccountPaymentsDetailsProcessor` |
| 16 | `loan_installment_details` | UPDATE (all installments paid/closed) | `updateLoanInstallmentDetailsProcessor` |
| 17 | `loan_account.past_due_days`, asset criteria, classification | UPDATE (recompute) | DPD/criteria/classification processors |
| 18 | `loan_account_closure_details` | INSERT (closure record) | `createLoanAccountClosureDetailsProcessor` |
| 19 | `loan_account_excess_amount_refund_details` | INSERT if excess to refund | `updateExcessAmountForPrepaymentProcessor` |
| 20 | `loan_account.loan_status` | UPDATE → `CLOSED` (auto-closure) | `loanAccountAutoClosureProcessor` |
| 21 | `mfi_task.task` | UPDATE (close task) | `updatePrepaymentTaskDetailsProcessor` |
| 22 | `mfi_approval.draft_application` | DELETE | `deleteDraftProcessor` |
| 23 | (collection notify) | call to LCS | `updateCollectionForClosureProcessor` |
| 24 | `loan_due_details__loan_account_payments_details` | INSERT linkage | `createLoanDueDetailsLoanAccountPaymentsDetailsProcessor` |
| 25 | (notification) | `prepaymentSMSNotification` |

## NOC issuance (separate cycle)

| Step | Table |
|---|---|
| `loan_account_noc_details` | INSERT (status=PENDING) |
| `generateNocFileJob` (scheduled) → `loan_account_noc_dispatch_details` | INSERT (NOC file rendered + DMS upload) |
| `loan_account.noc_document_id` | UPDATE (FK to dms document) |

## SHG/JLG variants

- **`childLoanForeclosure`** (the dispatcher) iterates children and calls `individualChildLoanForeclosure` per child. Plus enqueues `FCL` event in `loan_account_events_queue` for sibling effects.
- **Parent-side reschedule** if one child forecloses: parent transitions to `FORECLOSURE_FREEZE_RSCH` until the parent's repayment schedule is recomputed.

## Reopening (reverse of closure)

`loanAccountReopening` / `childLoanReopening`:
- Reverses the foreclosure transaction (`reverseTransaction`)
- Restores `loan_due_details` from `loan_account_closure_details` snapshot
- Sets `loan_account.loan_status = ACTIVE` (closing_date kept as historical)
- Recomputes DPD + asset criteria + classification

## Cross-references

- [`tables/loan_account.md`](../tables/loan_account.md) lifecycle states
- [`tables/loan_account_payments_details.md`](../tables/loan_account_payments_details.md)
- Lifecycle deep: [`../../07-loan-account-lifecycle.md`](../../07-loan-account-lifecycle.md)
- Runbook: [`../../../runbooks/maker-checker-stuck.md`](../../../runbooks/maker-checker-stuck.md)
