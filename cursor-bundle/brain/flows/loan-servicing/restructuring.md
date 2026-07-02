# Loan servicing — Restructuring

> Re-issue the loan's terms while keeping the same `loan_account` row. Three impact options: **UPDATE_EMI**, **UPDATE_TENURE**, **ROI change** (or combo). Heavier than part-prepayment because the contract itself is renegotiated. Maker-checker.

## Variants

| Request | XML | Use |
|---|---|---|
| `loanAccountRestructuring` | `loans_orc.xml` | Individual loan |
| `childLoanRestructuring` | `group_mfi_orc.xml:189` | Per-child (replayed from `RSTCRE` events) |
| `fetchRestructuringRepaymentSchedule` | `loans_orc.xml` | Preview new schedule before commit |
| `getLoanAccountRestructuringList`, `getLoanAccountRestructuringDetails` | `loans_orc.xml` | Read history |

## Function code matrix

| `function_code` | Branch |
|---|---|
| `DEFAULT` | Maker submit |
| `APPROVE` | Checker approves |
| `REJECT` | Checker rejects |

`run_mode = TRIAL` previews; `REAL` commits.

## Required input

(from `<Validators>` in `loans_orc.xml::loanAccountRestructuring`)

- `loan_account_number`
- `rescheduling_effective_date` (epoch ms)
- `restructuring_impact` — masterdata `RESTRCTRN_IMPACT/LOAN_RESTRCTRN`: `UPDATE_EMI` / `UPDATE_TENURE` / `UPDATE_ROI` (others)
- `is_roi_changed` — boolean (true|false)
- `bpi_amount`, `overdue_amount`, `due_amount`, `penal_due_amount`, `fee_due_amount`
- `reason` — masterdata `REASONS/LOAN_RESTRCTRN`
- `notes` — free-form (3-250 chars, alphanumeric pattern)

Conditionally:

- `restructuring_impact=UPDATE_EMI`: `old_emi`, `new_emi` mandatory
- `restructuring_impact=UPDATE_TENURE`: `old_tenure`, `new_tenure` mandatory (2-120 months)
- `is_roi_changed=true`: `existing_roi`, `new_roi` mandatory

## Maker-side chain (function_code=DEFAULT, run_mode=REAL)

(per `loans_orc.xml::loanAccountRestructuring` processor block)

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. **Flag controls** — `validate_task=true, create_task=true`
3. `validatePendingLoanAccountRestructuringProcessor` — refuse if a prior restructure is in progress
4. `validateTransactionForLoanAccountProcessor` (current_transaction_name=`LOAN_RESTRUCTURING`) — guard
5. `populateRestructuringSimulationDataProcessor` — assemble proposed schedule
6. `executeRestructureSimulationProcessor` — runs the rescheduling math:
   - For UPDATE_TENURE: keep EMI, change `number_of_installments` and `maturity_date`
   - For UPDATE_EMI: keep tenor, recompute principal/interest split per installment
   - For ROI change: re-amortise from `rescheduling_effective_date` with new rate
   - BPI handling if applicable
7. `createOrUpdateLoanAccountRestructuringDetailsProcessor` — INSERT into `loan_account_restructuring_details` (status=PENDING) with proposed schedule diff
8. `<API id="…submitApplication">` → approval draft
9. `loan_account.loan_status` → `LOAN_RESTR_FREEZE`
10. `<API id="createOrUpdateTask">` → checker task
11. Notification + 30003

## Checker (APPROVE) chain — the heavy work

1. `populateUserDetails`, `setCommonAttributesProcessor`, flag `approve_task=true`
2. **Re-validate** (defense in depth)
3. `fetchSuperDataForRestructuringProcessor` — re-fetch live state
4. `bookingNonPostedPenalProcessor` — book pending penal first (so it appears in current dues)
5. `executeRestructureProcessor` — applies the new schedule:
   - Inserts new `loan_installment_details` rows (REPLACE future installments)
   - Inserts new `loan_due_details` rows (REPLACE future dues)
   - Updates `loan_repayment_schedule_details` (immutable snapshot — replaced)
   - Updates `loan_account.term`, `term_unit`, `number_of_installments`, `maturity_date`, etc.
6. **Handle current dues**:
   - If `overdue_amount` settled as part of restructure: `<API id="postTransaction">` for the cleared amount
   - If `bpi_amount` UPFRONT: post BPI receivable
7. `createOrUpdateLoanAccountRestructuringDetailsProcessor` — UPDATE status=APPROVED with checker info, applied_schedule
8. `loanAccountDpdCalcProcessor`, `loanAccountAssetCriteriaProcessor`, `loanAccountAssetClassificationProcessor` — recompute
9. `checkNPAReverseMovementRequiredProcessor` — restructured loans often step down NPA per RBI rules
10. `loan_account.loan_status` → `ACTIVE` (clear `LOAN_RESTR_FREEZE`)
11. Update task, delete draft, notification

## SHG/JLG variant (`childLoanRestructuring`, group_mfi_orc.xml:189)

1. `childLoanRestructuringProcessor` — runs the math per child
2. `createChildLoanAccountRestructuringDetailsProcessor` — INSERT child restructuring record
3. (optional) `loanAdvanceRepaymentProcessor` — apply child's pool of excess to next due

Triggered from parent flow via `RSTCRE` event in `loan_account_events_queue`.

## DB writes (in order)

| Table | Action |
|---|---|
| **— maker —** | |
| `loan_account_restructuring_details` | INSERT (PENDING) |
| `loan_account.loan_status` | UPDATE → `LOAN_RESTR_FREEZE` |
| `mfi_approval.application` | INSERT (draft) |
| `mfi_task.task` | INSERT (checker task) |
| **— checker APPROVE —** | |
| `interest_accrual_details` (penal) | UPDATE (book non-posted) |
| `loan_due_details` | DELETE/REPLACE future dues |
| `loan_installment_details` | DELETE/REPLACE future installments |
| `loan_repayment_schedule_details` | REPLACE |
| `loan_account` | UPDATE `term`, `number_of_installments`, `maturity_date`, possibly `interest_*`, `bpi_*` |
| `loan_account_restructuring_details` | UPDATE → APPROVED |
| `transaction_master`, `transaction_partition_details`, `transaction_details` | INSERT (if BPI/cleared dues posted) |
| `loan_account.past_due_days`, `asset_*`, `npa_*` | UPDATE (recompute) |
| `loan_account.loan_status` | UPDATE → `ACTIVE` |
| `mfi_task.task` | UPDATE → CLOSED |
| `mfi_approval.draft_application` | DELETE |
| `loan_account_events_queue` | INSERT (`RSTCRE`, SHG/JLG only) |

## Status transitions

```
ACTIVE ──maker──► LOAN_RESTR_FREEZE ──APPROVE──► ACTIVE (with new schedule)
                                    ╲
                                     ╲──REJECT──► ACTIVE (no change)
```

## GL impact

Restructuring itself doesn't usually post GL legs (the restructure changes future obligations, not past ones). But if `bpi_amount` is UPFRONT or `overdue_amount` is cleared as part of the restructure, those amounts post as a regular repayment txn.

## Idempotency + concurrency

- **`validatePendingLoanAccountRestructuringProcessor`** — only one restructure in flight per loan
- **`LOAN_RESTR_FREEZE` state** — the in-flight lock
- Standard maker-checker semantics

## Failure modes

| Symptom | Cause | Triage |
|---|---|---|
| Stuck in `LOAN_RESTR_FREEZE` | Checker not actioned | Push operator |
| New schedule wrong | `executeRestructureSimulationProcessor` math off — wrong `restructuring_impact` or wrong `new_emi`/`new_tenure` | Inspect `loan_account_restructuring_details` for proposed-vs-applied diff |
| ROI not applied | `is_roi_changed=true` but `existing_roi`/`new_roi` validation failed | Re-submit with both fields |
| Child loans not restructured (SHG/JLG) | `RSTCRE` event stuck | See [shg-jlg-children-missing runbook](../../runbooks/shg-jlg-children-missing.md) |
| TB off after restructure | If BPI/cleared-dues legs miscomputed | See [trial-balance-imbalance runbook](../../runbooks/trial-balance-imbalance.md) |

## Code anchors

- **Orchestration**: `loans_orc.xml::loanAccountRestructuring`, `group_mfi_orc.xml:189` (`childLoanRestructuring`)
- **Code root**: [`loan/restucturing/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/restucturing/) (note: typo'd dir name in source)
- **Reschedule helpers**: [`loan/rescheduling/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/rescheduling/)
- **Group variant**: [`loan/grouploan/restructuring/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/restructuring/)
- **Tables**: `loan_account_restructuring_details`, `loan_account_reschedule_details`, plus the standard `loan_due_details`, `loan_installment_details`, `loan_repayment_schedule_details`

## Cross-references

- [Part-prepayment](part-prepayment.md) — uses similar reschedule machinery
- [Reopening](reopening.md) — restructure-then-reopen if loan was closed
- [Lifecycle](../../accounting/07-loan-account-lifecycle.md) — `LOAN_RESTR_FREEZE`
