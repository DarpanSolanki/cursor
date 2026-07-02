# Loan servicing — Part Prepayment

> Customer pays an extra lump sum on top of regular EMIs. Two impact options: **REDUCE_TENOR** (keep EMI, finish earlier) or **REDUCE_EMI** (keep tenor, lower EMI). Optional broken-period-interest (BPI) handling. Maker-checker.

## Variants

| Request | XML | Use |
|---|---|---|
| `loanAccountPartPrepayment` | `loans_orc.xml` | Individual loan |
| `parentLoanAccountPartPrepayment` | `group_mfi_orc.xml:429` | SHG/JLG parent — initiates + queues per-child events |
| `childLoanPartPrepayment` | `group_mfi_orc.xml:409` | Per-child, replayed by `childLoanEventProcessingBatchJob` from `PRTPRE` events |
| `fetchPartPrepaymentRepaymentSchedule` | `loans_orc.xml` | Preview the new schedule before committing |
| `getLoanAccountPartPrepaymentDetails` | `loans_orc.xml` | Read history |
| `getPartPrepaymentBPIAmount` | `loans_orc.xml` | Compute BPI amount for a target date |

## Function code / sub-code matrix (loanAccountPartPrepayment)

| `function_code` | `function_sub_code` | Branch |
|---|---|---|
| `DEFAULT` | `DEFAULT` | maker submit (creates draft + task) |
| `APPROVE` | `DEFAULT` | checker approves → real prepayment |
| `RESUBMIT` | `DEFAULT` | maker re-submits after clarification |
| `REJECT` | `DEFAULT` | checker rejects |
| any | `COLLECTED` | LCS-driven path: a collection has been received and tagged as part-prepayment; no maker step |

`run_mode = TRIAL` previews the new schedule without DB writes; `REAL` commits.

## Required input fields

(from `<Validators>` block)

- `loan_account_number`, `rescheduling_effective_date` (epoch ms), `gross_amount`, `overdue_amount`, `overdue_fee_charges`
- `part_prepayment_impact`: one of `REDUCE_TENOR` / `REDUCE_EMI`
- `broken_period_interest_handling`: `UPFRONT` / `NO`
- `bpi_amount` (if BPI handling = UPFRONT)
- For REAL mode: `charges`, `net_amount`, `instrument_type`, `paid_by`
- For RESUBMIT: `application_id`

Master-data validations: `part_prepayment_impact` (RESCHEDILING/PART_PREPAYMENT_IMPACT), `broken_period_interest_handling` (RESCHEDILING/BROKEN_PERIOD_INTEREST_HANDLING), `instrument_type` (RESCHEDILING/INSTRUMENT_TYPE), `paid_by` (PAID_BY/PART_PRE_PYMT_WEB).

## Maker-side processor chain (function_code=DEFAULT, run_mode=REAL)

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `validatePendingLoanAccountPartPrepaymentProcessor` — refuses if a prior part-prepayment is in progress (loan in `PART_PREPAYMENT_FREEZE`)
3. `validateTransactionForLoanAccountProcessor` (current_transaction_name=`PART_PREPAYMENT`) — generic guard (loan in `InactiveLoanStatus` → reject)
4. (SHG/JLG only) Routes to `childLoanRestructuringProcessor` if needed
5. `setCommonAttributesProcessor`
6. `createOrUpdateLoanAccountPartPrepaymentProcessor` — INSERT into `loan_account_part_prepayment_details` (status=PENDING, with proposed schedule diff)
7. `createPartPrepaymentTaxDetailsProcessor` — tax on charges
8. `populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails`
9. `<API id="…submitApplication">` → approval service draft
10. `loan_account.loan_status` → `PART_PREPAYMENT_FREEZE`
11. `<API id="createOrUpdateTask">` → task service for checker pickup
12. Notification + response_code=30003

## Checker-side (APPROVE) chain — the heavy work

For individual loans:

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `fetchBulkUniqueMasterData` (friendly labels)
3. `fetchSuperDataForForeclosureProcessor` (re-fetch live state — loan_account, due_details, schedule)
4. `createOrUpdateLoanAccountPartPrepaymentProcessor` — UPDATE status=APPROVED with checker info
5. `getOfficeIdFromAccountNumberProcessor`
6. `populateLoanAccountPartPrepaymentDetailsProcessor` — pull amounts (gross, overdue, charges, BPI)
7. `populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails`
8. `bookingNonPostedPenalProcessor` — book pending penal accruals first (so they appear in current dues)
9. `registerLoanAccountRescheduleEventProcessor` — INSERT into `loan_account_reschedule_details` (status=PENDING)
10. `loanAccountRescheduleBatchProcessor` — applies the reschedule **inline**:
    - Recompute new `loan_installment_details` rows based on `part_prepayment_impact`
    - Recompute `loan_due_details` (delete future, insert new)
    - Update `loan_repayment_schedule_details` (immutable schedule snapshot)
    - Apply BPI if `broken_period_interest_handling = UPFRONT`
11. `<API id="postTransaction">` (txn_catalogue=`PART_PREPAYMENT` or similar):
    ```
    DR  CUSTOMER_AC / BANK_RECV_AC   ₹gross_amount
    CR  LOAN_PRIN_AC                  ₹principal_portion
    CR  INT_RECEIVABLE_AC             ₹interest_portion (if any overdue)
    CR  PINT_INC_AC                   ₹penal_portion (if any overdue)
    CR  PRE_PAYMENT_CHARGE_INC_AC     ₹charges
    CR  TAX_GST_PAYABLE_AC            ₹tax
    DR  BPI_RECEIVABLE_AC             ₹bpi_amount (if UPFRONT)   ← inverted: customer pays BPI
    ```
12. `createLoanAccountPaymentsDetailsProcessor` — INSERT row in `loan_account_payments_details`
13. `loanAccountDpdCalcProcessor` — recompute DPD (typically 0 after part-prepayment if all overdue cleared)
14. `loanAccountAssetCriteriaProcessor` + `loanAccountAssetClassificationProcessor` — recompute slab/classification
15. `checkNPAReverseMovementRequiredProcessor` — if loan was NPA and now eligible to step down
16. `loan_account.loan_status` → `ACTIVE` (clear `PART_PREPAYMENT_FREEZE`)
17. `updateLoanAccountPartPrepaymentTaskProcessor` — close task
18. `deleteDraftProcessor` — clear approval draft
19. `prepaymentSMSNotification`

## SHG/JLG parent flow (`parentLoanAccountPartPrepayment`)

(group_mfi_orc.xml:429-468)

1. `populateUserDetails`, `setCommonAttributesProcessor`, `fetchBulkUniqueMasterData`
2. `fetchSuperDataForForeclosureProcessor`
3. `createOrUpdateLoanAccountPartPrepaymentProcessor` (parent record)
4. `getOfficeIdFromAccountNumberProcessor`
5. `populateLoanAccountPartPrepaymentDetailsProcessor`
6. `populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails`
7. `bookingNonPostedPenalProcessor`
8. `registerLoanAccountRescheduleEventProcessor` — for parent
9. `loanAccountRescheduleBatchProcessor` — recomputes parent schedule
10. `updateLoanAccountPartPrepaymentTaskProcessor`

**Per-child fan-out** is not done inline — it's enqueued via `PRTPRE` events in `loan_account_events_queue` (one element per child in the JSON `data`). The batch job replays each as `childLoanPartPrepayment`.

### Per-child (`childLoanPartPrepayment`, group_mfi_orc.xml:409)

1. `childLoanRestructuringProcessor` — first restructures the child (split allocation)
2. `setCommonAttributesProcessor`
3. `createOrUpdateLoanAccountPartPrepaymentProcessor` (child record)
4. `createChildLoanPartPrepaymentInstallmentProcessor` — INSERT new child `loan_installment_details` + `loan_due_details`
5. `createPartPrepaymentTaxDetailsProcessor`
6. `populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails`
7. `childPostPartPrepaymentTransactionProcessor` — calls `postTransaction` per child with `is_child_account=true` (CG-prefixed GLs)
8. `updateLoanAccountPartPrepaymentTaskProcessor`

## DB writes (in order)

| Table | Action | Trigger |
|---|---|---|
| `loan_account_part_prepayment_details` | INSERT (status=PENDING) | maker |
| `loan_account.loan_status` | UPDATE → `PART_PREPAYMENT_FREEZE` | maker |
| `loan_account_charge_details` | INSERT (prepayment charge) | maker |
| `loan_account_tax_details` | INSERT (tax) | maker |
| `mfi_approval.application` | INSERT (draft) | maker |
| `mfi_task.task` | INSERT (checker task) | maker |
| **— checker —** | | |
| `loan_account_part_prepayment_details` | UPDATE → APPROVED, checker info | checker |
| `interest_accrual_details` (penal) | UPDATE / new accrual rows | `bookingNonPostedPenalProcessor` |
| `loan_account_reschedule_details` | INSERT (PENDING) | `registerLoanAccountRescheduleEventProcessor` |
| `loan_installment_details` | DELETE/REPLACE (future installments) | `loanAccountRescheduleBatchProcessor` |
| `loan_due_details` | DELETE/REPLACE (future dues) | same |
| `loan_repayment_schedule_details` | REPLACE (new immutable snapshot) | same |
| `transaction_master` | INSERT | `postTransaction` |
| `transaction_partition_details` | INSERT N legs | same |
| `transaction_details` + `account_balance` | per-account | same |
| `loan_account_payments_details` | INSERT (payment row) | `createLoanAccountPaymentsDetailsProcessor` |
| `loan_account.past_due_days`, `asset_*`, `npa_*` | UPDATE | DPD/criteria/classification processors |
| `loan_account.loan_status` | UPDATE → `ACTIVE` | `UpdateLoanAccountStatusProcessor` |
| `mfi_task.task` | UPDATE → CLOSED | `updateLoanAccountPartPrepaymentTaskProcessor` |
| `mfi_approval.draft_application` | DELETE | `deleteDraftProcessor` |
| `loan_account_events_queue` | INSERT (`PRTPRE`, SHG/JLG only) | `ChildLoanPartPrepaymentEventGenerationProcessor` |

## Status transitions

```
ACTIVE ──maker submit──► PART_PREPAYMENT_FREEZE ──checker APPROVE──► ACTIVE (with new schedule)
                                              ╲
                                               ╲──checker REJECT──► ACTIVE (no change)
```

For SHG/JLG parent: parent stays `ACTIVE` after parent-side reschedule; children transition individually as their `PRTPRE` events replay.

## Idempotency + concurrency

- **`receiptNumberDedupProcessor`** is commented-out in current code; rely on maker-checker workflow + task uniqueness
- **`validatePendingLoanAccountPartPrepaymentProcessor`** prevents two part-prepayments running concurrently on the same loan
- **`postTransaction.client_reference_number`** dedups the GL hit
- The `PART_PREPAYMENT_FREEZE` state itself is the in-flight lock

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Loan stuck in `PART_PREPAYMENT_FREEZE` | Checker not actioned | Push operator (see [maker-checker-stuck runbook](../../runbooks/maker-checker-stuck.md)) |
| New schedule wrong | `restructuring_impact` mis-applied or BPI calc off | Inspect `loan_account_part_prepayment_details` row for the proposed-vs-applied schedule diff |
| Child loans not re-projected (SHG/JLG) | `PRTPRE` event stuck at `P` in `loan_account_events_queue` | See [shg-jlg-children-missing runbook](../../runbooks/shg-jlg-children-missing.md) |
| Trial balance off after part-prepayment | A leg's `condition_expression` evaluated to zero, asymmetric posting | See [trial-balance-imbalance runbook](../../runbooks/trial-balance-imbalance.md) |

## Code anchors

- **Orchestration**: `loans_orc.xml::loanAccountPartPrepayment`, `group_mfi_orc.xml:409` (`childLoanPartPrepayment`), `group_mfi_orc.xml:429` (`parentLoanAccountPartPrepayment`)
- **Inline reschedule**: `loanAccountRescheduleBatchProcessor` in `loan/rescheduling/processor/`
- **Per-child installment splitter**: [`loan/grouploan/partprepayment/processor/CreateChildLoanPartPrepaymentInstallmentProcessor.java`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/partprepayment/processor/CreateChildLoanPartPrepaymentInstallmentProcessor.java)
- **Per-child posting**: [`ChildPostPartPrepaymentTransactionProcessor.java`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/partprepayment/processor/ChildPostPartPrepaymentTransactionProcessor.java)
- **Event generator (SHG/JLG)**: [`ChildLoanPartPrepaymentEventGenerationProcessor.java`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/partprepayment/processor/ChildLoanPartPrepaymentEventGenerationProcessor.java)
- **Entity**: `LoanAccountPartPrepaymentDetailsEntity` (in `loan/partprepayment/entity/`)
- **DB tables**: [`loan_account_part_prepayment_details`](../../accounting/db-code-map/tables/_TEMPLATE.md) (Tier 2 — not yet curated; use `inspect-table.sh` for live schema)

## Cross-references

- [Foreclosure & closure](../foreclosure-and-closure.md) — similar maker-checker, but full close
- [Restructuring](restructuring.md) — same reschedule machinery, different trigger
- [Maker-checker meta-pattern](../maker-checker.md)
- [Loan account lifecycle](../../accounting/07-loan-account-lifecycle.md) — `PART_PREPAYMENT_FREEZE` state
