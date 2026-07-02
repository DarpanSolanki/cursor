# Loan servicing — Waiver

> Forgive a charge or part of a charge that was billed but won't be collected. Updates `loan_due_details.waived_amount` and posts an offsetting GL leg. Maker-checker.

## Variants

| Request | XML | Use |
|---|---|---|
| `waiveLoanAccountCharges` | `loans_orc.xml` | Individual — waive one or more charges |
| `childWaiveLoanAccountCharges` | `group_mfi_orc.xml:180` | Per-child (replayed from `WAIVER` events) |

## Maker-checker matrix

Standard DEFAULT / APPROVE / REJECT.

## Required input

- `loan_account_number`
- `waiver_charges` array — list of `{component_type, due_date, amount, reason}` rows to waive
- `notes`

## Maker-side chain

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `validateTransactionForLoanAccountProcessor` (current_transaction_name=`WAIVER`)
3. `populateChildLoanWaiverDataProcessor` (or individual variant) — pull existing dues
4. `validateWaiverAmountsProcessor` — refuse if waiver amount > pending
5. `createOrUpdateWaiverDetailsProcessor` — INSERT into `waiver_details` (status=PENDING)
6. `<API id="…submitApplication">` → approval draft
7. `<API id="createOrUpdateTask">` → checker task

(No FREEZE state — waiver doesn't gate the loan)

## Checker (APPROVE) chain

(Per `group_mfi_orc.xml:180-188` for `childWaiveLoanAccountCharges`)

1. `populateChildLoanWaiverDataProcessor` (or individual variant) — re-pull live dues
2. `updateLoanDueDetailsForWaiverProcessor` — UPDATE `loan_due_details.waived_amount` for each waived row
3. `updateWaiverLoanDueDetailsProcessor` — INSERT into `waiver__loan_due_details` linking waiver_details ↔ each affected loan_due row

For individual variant additionally:
4. `<API id="postTransaction">` (txn_catalogue=`WAIVER` or per-component variant):
   ```
   For each waived row:
     DR  WAIVER_EXPENSE_AC          ₹waived_amount   (recognises the loss)
     CR  PINT_INC_AC / FEE_INC_AC   ₹waived_amount   (reverses the income recognition)
   ```
   For interest waiver:
   ```
   DR  WAIVER_EXPENSE_AC            ₹waived_interest
   CR  INT_INCOME_AC                ₹waived_interest
   ```
5. `loanAccountDpdCalcProcessor` — recompute (DPD often improves since waived ≠ overdue)
6. `loanAccountAssetCriteriaProcessor` + `loanAccountAssetClassificationProcessor`
7. `checkAccountAutoClosureEligibilityProcessor` — if waiver fully clears all dues
8. (if eligible) `loanAccountAutoClosureProcessor` — `loan_status=CLOSED`, `loan_account_closure_details` row
9. Update task → CLOSED, delete approval draft, notification

## DB writes

| Table | Action |
|---|---|
| `waiver_details` | INSERT (PENDING) → UPDATE (APPROVED) |
| `waiver__loan_due_details` | INSERT N rows linking waiver ↔ each waived loan_due_details row |
| `waiver__document` | INSERT (if supporting docs) |
| `loan_due_details` | UPDATE `waived_amount += amount` for each row |
| `loan_installment_details` | UPDATE installment_status (may flip to FULLY_PAID/WAIVED if waiver clears all components) |
| `transaction_master`, `transaction_partition_details` | INSERT (waiver expense GL hit) |
| `loan_account.past_due_days`, `asset_*`, `npa_*` | UPDATE (recompute) |
| `loan_account.loan_status` | UPDATE → `CLOSED` (only if waiver clears entire loan) |
| `loan_account_closure_details` | INSERT (only if auto-closure fires) |
| `mfi_approval.application` + `mfi_task.task` | maker-checker |
| `loan_account_events_queue` | INSERT (`WAIVER`, SHG/JLG only) |

## Status transitions

```
ACTIVE ──maker waiver──► ACTIVE (no FREEZE) ──APPROVE──► ACTIVE (with reduced overdue)
                                                    ╲
                                                     ╲(if waiver fully clears)──► CLOSED
```

## GL impact

Always recognises the waived amount as an expense (DR `WAIVER_EXPENSE_AC`) and reverses the original income (CR the relevant income GL). Net P&L impact: the waiver amount is moved from "income earned" to "expense incurred" — usually shown as separate line in management reports.

## Idempotency + concurrency

- A specific (loan, due_date, component_type) row can have its `waived_amount` increased multiple times via separate waiver_details rows
- Validation refuses waiver beyond the pending amount: `waiver_amount + paid_amount + waived_amount <= due_amount`

## Failure modes

| Symptom | Cause | Triage |
|---|---|---|
| Waiver approved but `waived_amount` not updated | `updateLoanDueDetailsForWaiverProcessor` failed mid-chain | Check app log; verify `waiver__loan_due_details` linkage |
| Loan auto-closed unexpectedly | Waiver covered remaining principal too — auto-closure fired | Expected if all components cleared; verify `loan_account_closure_details.closure_type` says WAIVER |
| Wrong GL hit | `transaction_accounting_rule` for txn_catalogue=`WAIVER_*` mis-bound | See [`08-gl-posting-engine.md §9`](../../accounting/08-gl-posting-engine.md#9-things-that-go-wrong-and-where-the-bug-lives) |

## Code anchors

- **Orchestration**: `loans_orc.xml::waiveLoanAccountCharges`, `group_mfi_orc.xml:180` (`childWaiveLoanAccountCharges`)
- **Code root**: [`loan/waiver/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/waiver/)
- **Group variant**: [`loan/grouploan/waiver/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/waiver/)
- **Tables**: `waiver_details`, `waiver__loan_due_details`, `waiver__document`

## Cross-references

- [Repayment](../repayment-end-to-end.md) — appropriation engine reads `waived_amount` as already-settled
- [Foreclosure](../foreclosure-and-closure.md) — sometimes a waiver+foreclosure combo to fully close
