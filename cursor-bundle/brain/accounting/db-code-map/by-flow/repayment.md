# Repayment → tables touched

Flow narrative: [`../../../flows/repayment-end-to-end.md`](../../../flows/repayment-end-to-end.md)

`loanRepayment` (mfi_orc.xml:2661) — sync HTTP. `childLoanRepayment` (group_mfi_orc.xml:33) — variant for SHG/JLG members.

## Pre-appropriation reads

| Step | Table | Source |
|---|---|---|
| 1 | `account` + `loan_account` (current state) | `loanRepayment_getLoanAccountDetails`, `valdiateLoanAccountNumberAndStatusProcessor` |
| 2 | `loan_due_details` (sorted per liquidation order) | `GetLoanDueDetailsProcessor` |
| 3 | `loan_product_asset_criteria` (4 component slots + liquidation_order) | `RepaymentApproppriationProcessor` |

## Appropriation (in-memory, no writes yet)

The `RepaymentApproppriationProcessor` walks `loan_due_details` and decides per-component splits. Sets EC keys: `principal_amount`, `interest_amount`, `penalty_amount`, `fee_amount`, `excess_amount`, `suspense_amount`, `total_settled_amount`.

## Writes (in order)

| Step | Table | Action | Processor |
|---|---|---|---|
| 4 | `loan_due_details` | UPDATE `paid_amount += current_paid_amount` (per component touched) | `UpdateLoanDueDetailsProcessor` |
| 5 | `loan_installment_details` | UPDATE per-installment paid totals + `installment_status` | `UpdateLoanInstallmentDetailsProcessor` |
| 6 | `loan_account` | UPDATE `excess_amount`, `excess_interest_amount` | `updateLoanAccountForExcessAmountProcessor` |
| 7 | `transaction_master` | INSERT (txn header — via `<API id="postTransaction">` with txn_catalogue=LOAN_REPAYMENT) | `CreateTransactionMasterProcessor` |
| 8 | `transaction_metadata` | INSERT | `CreateTransactionMetadataProcessor` |
| 9 | `transaction_partition_details` | INSERT N legs (DR customer / CR principal+interest+penal+fee — or suspense GL if NPA) | `CreateTransactionPartitionDetailsProcessor` |
| 10 | `transaction_details` | INSERT (per affected account) | `CreateTransactionDetailsProcessor` |
| 11 | `account_balance` | UPDATE | (inside step 10) |
| 12 | `loan_account_payments_details` | INSERT (one row per call; with excess_amount carried forward) | `createLoanAccountPaymentsDetailsProcessor` |
| 13 | `loan_due_details__loan_account_payments_details` | INSERT (links payment ↔ dues it settled) | (inside step 12) |
| 14 | `loan_account.past_due_days` | UPDATE (recompute) | `loanAccountDpdCalcProcessor` (if auto-closure check) |
| 15 | `loan_account.asset_criteria_*`, `npa_*` | UPDATE (NPA reverse-movement check) | `checkNPAReverseMovementRequiredProcessor` + `loanAccountAssetCriteriaProcessor` + `loanAccountAssetClassificationProcessor` |
| 16 (if loan paid up) | `loan_account.loan_status = CLOSED`, `cancelled_on` | UPDATE | `loanAccountAutoClosureProcessor` |
| 17 (if closed) | `loan_account_closure_details` | INSERT | `createLoanAccountClosureDetailsProcessor` |

## SHG/JLG variant (childLoanRepayment)

Same as above but with `is_child_account=true` set in EC by `populateChildLoanAccountDataProcessor`. Effect: GL legs (step 9) get `gl_code` prefixed with `CG`.

## Maker-checker variant

If `${maker_checker_enabled}=1`:
- First call (function_code=DEFAULT): `loanRepayment_submitApplication` writes a draft in `mfi_approval.application` instead of any of the above.
- Second call (function_code=APPROVE) executes the chain above.

## NPA suspense routing (gotcha)

If `loan_account.npa_ageing_start_date IS NOT NULL`:
- Step 4 still updates `loan_due_details`
- BUT in step 9, the interest leg credits the **suspense GL** (via fallback_credit_placeholder on the rule), and `loan_account_payments_details.suspense_amount` is set instead of crediting interest income GL

## Cross-references

- Per-table details: [`../tables/loan_due_details.md`](../tables/loan_due_details.md), [`../tables/loan_account_payments_details.md`](../tables/loan_account_payments_details.md), [`../tables/transaction_partition_details.md`](../tables/transaction_partition_details.md), [`../tables/loan_product_asset_criteria.md`](../tables/loan_product_asset_criteria.md)
- Posting engine: [`../../08-gl-posting-engine.md §7`](../../08-gl-posting-engine.md#7-the-repayment-appropriation-step-preceeds-posting)
- Runbook: [`../../../runbooks/repayment-mismatch.md`](../../../runbooks/repayment-mismatch.md)
