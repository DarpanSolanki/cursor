# Loan servicing — Write-off

> Accounting recognition that the loan is uncollectible. Customer disappears, dies without insurance, or formally settled at a loss. Posts a write-off transaction (DR write-off expense, CR principal/interest receivable). Loan transitions to `WRITOFF` status. Distinct from waiver (waiver = forgive a charge; write-off = give up on the whole loan).

## Variants

| Request | XML | Use |
|---|---|---|
| `loanWriteoff` | `loans_orc.xml` | Individual write-off |

(No SHG/JLG-specific child write-off — write-off is per-loan; for a group, each child loan can be written off individually. No event-queue fan-out for write-off in `EVENT_TYPE_ORC_API_MAP`.)

## Maker-checker matrix

Standard DEFAULT / APPROVE / REJECT.

## Required input

- `loan_account_number`
- `writeoff_reason` (masterdata)
- `writeoff_date` (epoch ms — back-datable for compliance)
- `notes` — typically with case ID / settlement reference
- (Optional) `settlement_amount` if customer paid a partial settlement before write-off

## Maker-side chain

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `valdiateLoanAccountNumberAndStatusProcessor` — must be ACTIVE or NPA-tagged (rare to write-off STD)
3. `validateTransactionForLoanAccountProcessor` (current_transaction_name=`WRITEOFF`)
4. `populateWriteoffDataProcessor`
5. `createOrUpdateLoanWriteoffProcessor` — INSERT into write-off detail table (status=PENDING)
6. `<API id="…submitApplication">` → approval draft
7. `<API id="createOrUpdateTask">` → checker task
8. (no FREEZE state — loan stays ACTIVE until APPROVE; write-off requires senior sign-off)

## Checker (APPROVE) chain

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. Re-validate
3. `bookingNonPostedPenalProcessor` — book pending penal first (so it's recognised, then written off)
4. `<API id="postTransaction">` (txn_catalogue=`LOAN_WRITEOFF`):
   ```
   DR  WRITEOFF_EXPENSE_AC          ₹total_outstanding (principal + interest + penal + fees)
   CR  LOAN_PRIN_AC                 ₹principal due
   CR  INT_RECEIVABLE_AC            ₹interest due
   CR  PINT_INC_AC                  ₹penal due
   CR  FEE_RECEIVABLE_AC            ₹fee due
   ```
   For NPA loans: interest portion may already be in suspense → moved from suspense to write-off:
   ```
   DR  WRITEOFF_EXPENSE_AC          ₹interest_in_suspense
   CR  INT_SUSPENSE_AC              ₹interest_in_suspense
   ```
   If `settlement_amount` given (customer paid partial before write-off):
   ```
   DR  CUSTOMER_AC                  ₹settlement_amount
   CR  WRITEOFF_RECOVERY_AC         ₹settlement_amount  (or against various dues)
   ```
5. `loan_account.loan_status` → `WRITOFF`
6. Fully zero out `loan_due_details` (paid_amount + waived_amount = due_amount equivalent)
7. `loan_account.outstanding`, `excess_amount` → 0
8. `loan_account.npa_*` columns → finalise per RBI rules (asset_classification = LOSS)
9. `loan_account_closure_details` — INSERT (closure_type=WRITEOFF)
10. `loan_provisioning_details` — UPDATE / INSERT — provisioning at LOSS rate (typically 100%)
11. NOC — typically NOT issued on write-off; depends on tenant policy
12. Update task → CLOSED, delete draft, notification

## DB writes

| Table | Action |
|---|---|
| `loan_account_closure_details` (or dedicated write-off table — check live schema) | INSERT (closure_type=WRITEOFF) |
| `loan_account.loan_status` | UPDATE → `WRITOFF` |
| `loan_account.cancelled_on` | UPDATE = writeoff_date |
| `loan_account.outstanding`, `excess_amount`, `interest_suspense_amount` | UPDATE → 0 |
| `loan_account.asset_classification_slabs_id` | UPDATE → LOSS slab |
| `loan_account.npa_*` | UPDATE — finalised |
| `loan_due_details` | UPDATE — written-off rows zeroed (typically via paid_amount or waived_amount, depending on convention) |
| `loan_installment_details` | UPDATE — status WRITTEN_OFF |
| `interest_accrual_details` | stop further accrual |
| `transaction_master`, `transaction_partition_details`, `transaction_details` | INSERT (write-off txn) |
| `loan_provisioning_details` | UPDATE/INSERT (100% provisioned) |
| `mfi_approval.application` + `mfi_task.task` | maker-checker |

## Status transitions

```
ACTIVE / NPA ──maker──► (no FREEZE — stays ACTIVE) ──APPROVE──► WRITOFF (terminal — but reopening can reverse)
                                              ╲
                                               ╲──REJECT──► ACTIVE (no change)
```

`closing_date` is set; loan is excluded from EOD accrual + DPD calc going forward.

## GL impact

The write-off recognises the full loss in P&L. The asset (loan principal + accrued income) is removed from the balance sheet via the credits to receivable accounts.

```
Before write-off (BS):
  ASSET: LOAN_PRIN_AC = +₹50,000 (the principal owed)
  ASSET: INT_RECEIVABLE_AC = +₹3,500
  
After write-off (BS):
  ASSET: LOAN_PRIN_AC = ₹0
  ASSET: INT_RECEIVABLE_AC = ₹0
  
P&L impact:
  EXPENSE: WRITEOFF_EXPENSE_AC = ₹53,500 (loss recognised)
```

## Recovery (post write-off)

If the customer eventually pays after a write-off:
- Operator runs `loanRepayment` against the (now WRITOFF) loan — refused due to `InactiveLoanStatus`
- Workaround: `loanAccountReopening` first (reverses write-off → loan back to ACTIVE) → repayment → re-close if appropriate
- Or: a dedicated "write-off recovery" txn (DR cash, CR `WRITEOFF_RECOVERY_INC_AC`) without re-opening — depends on tenant policy

## Idempotency + concurrency

- Maker-checker provides exclusivity — only one write-off task per loan
- Once `loan_status=WRITOFF`, subsequent write-off attempts refuse via `valdiateLoanAccountNumberAndStatusProcessor`

## Failure modes

| Symptom | Cause | Triage |
|---|---|---|
| Loan written off but TB shows residual receivable | Some leg in the write-off rule didn't fire (`condition_expression` evaluated to 0) | See [trial-balance-imbalance runbook](../../runbooks/trial-balance-imbalance.md) |
| Provisioning not at 100% | `loan_provisioning_details` not refreshed after status change | Re-run provisioning batch for this loan |
| Customer paid after write-off | Repayment refused | Use `loanAccountReopening` to re-open, then `loanRepayment` |

## Code anchors

- **Orchestration**: `loans_orc.xml::loanWriteoff`
- **Code root**: [`loan/writeoff/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/writeoff/)
- **Closure linkage**: [`loan/closure/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/closure/) — write-off shares the closure-details table
- **Tables**: `loan_account_closure_details` (closure_type='WRITEOFF'), `loan_provisioning_details`

## Cross-references

- [Foreclosure & closure](../foreclosure-and-closure.md) — adjacent (foreclosure = customer pays in full early; write-off = customer doesn't pay at all)
- [NPA & provisioning](../npa-and-provisioning.md) — write-off is typically the terminal state of a long-NPA loan
- [Death foreclosure](death-foreclosure.md) — FTNR outcome often leads to write-off
- [Reopening](reopening.md) — only way to reverse a write-off
