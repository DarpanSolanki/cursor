# Loan servicing — Disbursement Cancellation

> The loan was disbursed (or partially disbursed) but should be reversed in full. Customer never accepted, or operator error, or fraud-flagged. Cancels disbursement, reverses GL hits, refunds any collected charges, sets `loan_status=DISB_CNCL`. For SHG/JLG, cancellation of one child triggers a parent-side reschedule.

## Variants

| Request | XML | Use |
|---|---|---|
| `loanDisbursementCancellation` | `loans_orc.xml` | Individual loan |
| `childLoanDisbursementCancellation` | `group_mfi_orc.xml:469` | Per-child (replayed from `CANCL` events) |
| `childLoanDisbursementCancellationParentRescheduling` | `group_mfi_orc.xml:528` (`explicitTxnMgmt="true"`) | After child cancel, recompute parent's schedule |
| `getDisbursementCancellationDetails` | `loans_orc.xml` | Read history |
| `fetchDisbursementCancellationSimulationDetails` | `loans_orc.xml` | Preview impact before commit |
| `bulkSGToDisbursementCancellationJob` | `mfi_batch.batch_job` | Bulk cancellation |

Plus insurance side: `outboundDisbursementCancellation*InsuranceJob` family for HDFC Life / Ergo, Bajaj Ergo (per provider).

## Maker-checker matrix

Standard DEFAULT / APPROVE / REJECT. `run_mode = TRIAL` simulates; `REAL` commits.

## Required input

- `loan_account_number`
- `cancellation_reason` (masterdata `REASONS/DISB_CNCL`)
- `cancellation_date` (epoch ms)
- `notes`
- Refund details (where to send the refund if customer paid charges up-front)

## Maker-side chain

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `valdiateLoanAccountNumberAndStatusProcessor` — must be ACTIVE (post-disbursement)
3. `validateTransactionForLoanAccountProcessor` (current_transaction_name=`DISBURSEMENT_CANCELLATION`)
4. `populateDisbursementCancellationDataProcessor`
5. `createOrUpdateLoanDisbursementCancellationProcessor` — INSERT into `loan_disbursement_cancellation_details` (status=PENDING)
6. `<API id="…submitApplication">` → approval draft
7. `loan_account.loan_status` → `DISB_CNCL_FREEZE`
8. `<API id="createOrUpdateTask">` → checker task

## Checker (APPROVE) chain

(Per `group_mfi_orc.xml:469-525` for `childLoanDisbursementCancellation` — pattern similar for individual)

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `populateChildLoanDisbursementCancellationDataProcessor` (or individual variant)
3. `checkLoanAccountInterestAccrualCalculationProcessor` — book any pending accrual first (so it shows in dues)
4. `checkLoanAccountInterestAccrualBookingProcessor` — book the accruals
5. `populateAdditionalAmountAndAccountDetailsForCancellationProcessor` — compute the reversal amounts (principal + any interest accrued + charges)
6. `populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails`
7. `<API id="postTransaction">` (txn_catalogue=`DISBURSEMENT_CANCELLATION`):
   ```
   The disbursement is reversed:
     DR  LOAN_PRIN_AC                ₹principal_disbursed   (was credited at disbursement; now debited)
     DR  INT_RECEIVABLE_AC           ₹any_accrued_interest
     DR  CHARGES_RECV_AC             ₹any_charges_collected
     CR  CUSTOMER_AC                 ₹net_refund_amount
     CR  BANK_DISB_AC                ₹principal_refunded_to_bank
     (charges may also be refunded to customer or written off, depending on cancellation_type)
   ```
8. `createLoanAccountPaymentsDetailsProcessor` — INSERT a "negative payment" row tagged as cancellation
9. `updateLoanDueDetailsDataProcessor` — DELETE/zero future dues, refund settled dues
10. `updateLoanBPIDataProcessor` — handle BPI reversal if applicable
11. `updateLoanInstallmentDataProcessor` — DELETE/zero future installments
12. `updateLoanAccountStatusProcessor` (loan_status=`DISB_CNCL`)
13. `updateLoanDisbursementCancellationProcessor` — mark APPROVED
14. Insurance side-effects (parallel — see "Insurance reversal" below)
15. Update task → CLOSED, delete approval draft, notification

## Insurance reversal

If insurance was bound at disbursement, cancellation must reverse the insurance too. Per provider:

1. **Outbound** (`outboundDisbursementCancellation<Provider>InsuranceJob`):
   - Stages cancellation request in `disbursement_cancellation_insurance_staging_details`
   - Builds outbound file, sends to provider
2. **Inbound** (`inboundDisbursementCancellation<Provider>InsuranceJob`):
   - Provider returns confirmation of insurance refund
   - Updates staging row + `loan_account_insurance_details`
   - Posts insurance-refund txn (insurer pays back premium → customer)

## SHG/JLG: parent rescheduling

After a single child is cancelled (via `childLoanDisbursementCancellation`), the parent loan still exists with the original total amount allocated across N children. With one fewer child, the parent's per-EMI math is now wrong.

`childLoanDisbursementCancellationParentRescheduling` (group_mfi_orc.xml:528, `explicitTxnMgmt="true"`) fixes this:

1. `populateDisbursementCancellationParentAccountDetailsProcessor` — pull parent + remaining children
2. Rebuild charges + tax basis
3. `<API id="postTransaction">` — adjust parent-side GL for the cancelled portion
4. `createLoanAccountPaymentsDetailsProcessor` — record adjustment
5. `customCallRepaymentScheduleGenerateProcessor` — regenerate parent schedule with reduced child set
6. `createCustomRepaymentScheduleDetailsProcessor` — write new `loan_repayment_schedule_details`
7. `updateLoanDueDetailsDataProcessor` — refresh parent's due_details
8. `updateLoanInstallmentDataProcessor` — refresh parent's installments
9. `createCustomInstallmentAndDueDetailsProcessor` — INSERT new rows

While this runs, parent transitions through `DISB_CNCL_FREEZE_RSCH` → `ACTIVE` (with adjusted schedule).

## DB writes

| Table | Action |
|---|---|
| **— maker —** | |
| `loan_disbursement_cancellation_details` | INSERT (PENDING) |
| `loan_disbursement_cancellation_charge_details` | INSERT (charge refund details) |
| `loan_disbursement_cancellation_details__document` | INSERT (if docs) |
| `loan_account.loan_status` | UPDATE → `DISB_CNCL_FREEZE` |
| `mfi_approval.application` + `mfi_task.task` | INSERT |
| **— checker APPROVE —** | |
| `interest_accrual_details` | UPDATE (book non-posted) |
| `transaction_master`, `transaction_partition_details`, `transaction_details` | INSERT (cancellation txn) |
| `account_balance` | UPDATE |
| `loan_due_details`, `loan_installment_details`, `loan_repayment_schedule_details` | DELETE/zero future rows |
| `loan_account.loan_status` | UPDATE → `DISB_CNCL` |
| `loan_account.cancelled_on` | UPDATE = current date |
| `loan_account.disbursement_status` | UPDATE → cancellation-specific value |
| `loan_account_payments_details` | INSERT (cancellation/refund record) |
| `loan_disbursement_cancellation_details` | UPDATE → APPROVED |
| `disbursement_cancellation_insurance_staging_details` | INSERT (per insurance provider, if applicable) |
| `loan_account_events_queue` | INSERT (`CANCL`, SHG/JLG only) |
| `mfi_task.task` | UPDATE → CLOSED |
| `mfi_approval.draft_application` | DELETE |

For parent-rescheduling (SHG/JLG):
| Table | Action |
|---|---|
| `loan_account.loan_status` (parent) | UPDATE → `DISB_CNCL_FREEZE_RSCH` → `ACTIVE` |
| Parent's `loan_due_details`, `loan_installment_details`, `loan_repayment_schedule_details` | REPLACE with new schedule |
| Parent's `transaction_master`/_details_ | INSERT (parent-side adjustment) |

## Status transitions

```
ACTIVE ──maker──► DISB_CNCL_FREEZE ──APPROVE──► DISB_CNCL (terminal — but rebooking can re-issue)
                                  ╲
                                   ╲──REJECT──► ACTIVE (no change)

For SHG/JLG parent (after one child cancels):
ACTIVE (parent) ──child cancellation→ DISB_CNCL_FREEZE_RSCH ──parent reschedule done→ ACTIVE
```

## Failure modes

| Symptom | Cause | Triage |
|---|---|---|
| Loan stuck in `DISB_CNCL_FREEZE` | Checker not actioned | Push operator |
| SHG/JLG parent stuck `DISB_CNCL_FREEZE_RSCH` | `childLoanDisbursementCancellationParentRescheduling` failed | Inspect orchestration log; re-fire |
| Insurance not refunded | Outbound insurance job didn't fire OR provider didn't respond | Check `disbursement_cancellation_insurance_staging_details.status` |
| Bank refund not made | `accountingBankServiceRetryJob` retrying | Check `bank_service_call_retry` |

## Code anchors

- **Orchestration**: `loans_orc.xml::loanDisbursementCancellation`, `group_mfi_orc.xml:469,528`
- **Code root**: [`loan/cancellation/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/cancellation/)
- **Group variant**: [`loan/grouploan/cancellation/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/cancellation/)
  - Includes `PopulateChildLoanDisbursementCancellationDataProcessor`, `UpdateChildLoanAccountStatusProcessor`, `ChildLoanCancellationEventGenerationProcessor`
- **Insurance integration**: [`loan/insurance/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/insurance/), `loans_insurance_orc.xml::outbound/inboundDisbursementCancellation*InsuranceJob`
- **Tables**: `loan_disbursement_cancellation_details`, `loan_disbursement_cancellation_charge_details`, `loan_disbursement_cancellation_details__document`, `disbursement_cancellation_insurance_staging_details`

## Cross-references

- [Disbursement end-to-end](../disbursement-end-to-end.md) — what's being cancelled
- [Rebooking](rebooking.md) — how to re-issue after cancellation
- [Lifecycle](../../accounting/07-loan-account-lifecycle.md) — `DISB_CNCL_FREEZE`, `DISB_CNCL`, `DISB_CNCL_FREEZE_RSCH`
