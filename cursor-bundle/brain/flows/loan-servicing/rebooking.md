# Loan servicing — Rebooking

> Re-issue a cancelled loan. After `loanDisbursementCancellation`, the loan is in `DISB_CNCL` status. Rebooking re-creates the agreement, regenerates the schedule, posts a fresh disbursement, and re-activates. **Different from restructuring** (which keeps the existing loan_account; rebooking effectively re-disburses).

## Variants

| Request | XML | Use |
|---|---|---|
| `loanAccountRebooking` | `loans_orc.xml` | Generic entry — routes to individual or group |
| `individualLoanAccountRebooking` | `loans_orc.xml` | Individual loan |
| `groupLoanAccountRebooking` | `loans_orc.xml` | SHG/JLG (parent + per-child events) |
| `childLoanRebooking` | `group_mfi_orc.xml:620` | Per-child (replayed from `REBK` events) |
| `childLoanRebookingAdjustmentTransaction` | `group_mfi_orc.xml:628` | The actual `postTransaction` leg of a rebooking |
| `getLoanAccountRebookingDetails` | `loans_orc.xml` | Read history |

## Maker-checker

Standard DEFAULT / APPROVE / REJECT.

## Required input

- `loan_account_number` (the cancelled loan being rebooked)
- New disbursement amount, term, repayment frequency, etc. (often same as original; can differ)
- `reason` masterdata
- Adjustment details: how to handle any prior charges/refunds

## Maker-side chain

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `validateLoanAccountForRebookingProcessor` — must be in `DISB_CNCL` status
3. `populateRebookingDataProcessor`
4. `createOrUpdateLoanAccountRebookingDetailsProcessor` — INSERT into `loan_account_rebooking_details` (status=PENDING)
5. `<API id="…submitApplication">` → approval draft
6. `loan_account.loan_status` → `LOAN_REBKG_FREEZE`
7. `<API id="createOrUpdateTask">` → checker task

## Checker (APPROVE) chain

For `childLoanRebooking` (group_mfi_orc.xml:620):
1. `childLoanRebookingSaveAdjustmentDetailsProcessor` — record adjustment data (refunds, off-sets)
2. `childLoanRestructuringProcessor` — re-schedule with new terms
3. `childLoanRebookingAdjustmentTxnProcessor` — fires the adjustment transaction

For `childLoanRebookingAdjustmentTransaction` (group_mfi_orc.xml:628):
- Multiple `populateAdditionalAmountDetailsProcessor` calls (per-component)
- `populateTransactionAccountDetailsProcessor`
- `<API id="postTransaction">` (txn_catalogue=`LOAN_REBOOKING` or similar):
  ```
  Adjustment legs depend on prior cancellation refund:
    DR  CUSTOMER_AC                     ₹new_disbursed_amount
    CR  LOAN_PRIN_AC                    ₹new_principal
    CR  CHARGES_RECEIVABLE_*            ₹new_charges
    (offsets vs cancellation refund pool)
  ```

For individual:
- Similar pattern but no fan-out events
- `loan_account` updated with new terms (term, EMI, ROI)
- New `loan_installment_details` + `loan_due_details` created
- New `loan_repayment_schedule_details`
- `loan_account.loan_status` → `ACTIVE`, `disbursement_status` → `COMPLETED`

For `groupLoanAccountRebooking`:
- Same parent-side as individual
- Plus enqueues `REBK` events in `loan_account_events_queue` for each child

## DB writes

| Table | Action |
|---|---|
| `loan_account_rebooking_details` | INSERT (PENDING) → UPDATE (APPROVED) |
| `loan_account_rebooking_details__document` | INSERT (if rebooking docs) |
| `loan_account` | UPDATE — `loan_status`, possibly `term`, `loan_amount`, etc.; `disbursement_status` → `COMPLETED` |
| `loan_installment_details` | INSERT new |
| `loan_due_details` | INSERT new |
| `loan_repayment_schedule_details` | INSERT new |
| `transaction_master`, `transaction_partition_details`, `transaction_details` | INSERT (rebooking adjustment txn) |
| `loan_account_payments_details` | INSERT (if cash adjustment) |
| `loan_account.past_due_days`, `asset_*`, `npa_*` | UPDATE (recompute from fresh schedule) |
| `loan_account_events_queue` | INSERT (`REBK`, group rebooking) |
| `mfi_approval.application` + `mfi_task.task` | maker-checker rows |

## Status transitions

```
DISB_CNCL ──maker──► LOAN_REBKG_FREEZE ──APPROVE──► ACTIVE (with new schedule + posted)
                                       ╲
                                        ╲──REJECT──► DISB_CNCL (no change)
```

## Code anchors

- **Orchestration**: `loans_orc.xml::loanAccountRebooking`, `individualLoanAccountRebooking`, `groupLoanAccountRebooking`; `group_mfi_orc.xml:620,628`
- **Code root**: [`loan/rebooking/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/rebooking/) (with `group/` and `individual/` subpackages)
- **Group variant**: [`loan/grouploan/rebooking/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/rebooking/)
- **Group event generator**: [`ChildLoanRebookingEventGenerationProcessor.java`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/rebooking/processor/ChildLoanRebookingEventGenerationProcessor.java)
- **Tables**: `loan_account_rebooking_details`, `loan_account_rebooking_details__document`

## Cross-references

- [Disbursement cancellation](disbursement-cancellation.md) — the precondition (loan must be DISB_CNCL)
- [Disbursement end-to-end](../disbursement-end-to-end.md) — what's being re-done
- [Restructuring](restructuring.md) — adjacent concept; restructuring keeps the loan, rebooking re-issues
