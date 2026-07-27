# Flow — Repayment, end-to-end

## Mental model

Customer pays → entry point either webapp/payments/NACH → accounting `loanRepayment` (or `childLoanRepayment` for SHG/JLG members) → appropriation algorithm splits the amount across due rows → `postTransaction` hits the GL → DPD/NPA recompute → optional auto-closure if loan is paid up.

## Services involved

| Service | Role |
|---|---|
| webapp / android | Operator-driven repayment capture |
| payments (LCS) | Field/branch/digital collections — posts to accounting via `collectionLoanRepayment` |
| accounting | The actual ledger update + appropriation + GL posting |
| approval | Optional maker-checker per tenant config |
| notifications | Receipt SMS/email |
| audit | Framework-emitted |

## Step-by-step (sync HTTP path)

```
1. Operator captures repayment in webapp / payments collects in field
   ▼
2. payments:doMfiCollections (or webapp direct → accounting)
   ▼
3. payments → product_accounting.xml::collectionLoanRepayment ─HTTP─▶ accounting:loanRepayment
   (mfi_orc.xml line 2661, explicitTxnMgmt="true")
   ▼
4. accounting:loanRepayment processors:
   ┌─────────────────────────────────────────────────────────────┐
   │ accounting_getUserDetails (actor)                            │
   │ getUserDetailsPostProcessor                                  │
   │ loanRepayment_getLoanAccountDetails (self)                   │
   │ checkData…Repayment validators (allocation rules,            │
   │                                  not-write-off,              │
   │                                  not-foreclosure-ineligible) │
   │ if maker_checker_enabled=1:                                  │
   │   loanRepayment_submitApplication (approval) → return 30003  │
   │ else / on APPROVE:                                           │
   │   getOfficeIdFromAccountNumberProcessor                      │
   │   checkEligibleForRepaymentAppropriationProcessor            │
   │      ▼ (skip if loan inactive: WRITOFF / DISB_CNCL etc.)     │
   │   RepaymentApproppriationProcessor                           │
   │      ─ look up loan_product_asset_criteria                   │
   │      ─ sort loan_due_details by liquidationOrder             │
   │           (LIQ_INSTL / LIQ_COMP / LIQ_INSTL_CHRG_COMP)       │
   │      ─ walk + deduct → fills:                                │
   │           principal_amount, interest_amount,                  │
   │           penalty_amount, fee_amount,                        │
   │           excess_amount, suspense_amount                     │
   │           total_settled_amount                               │
   │   populateAmountForExcessRepaymentModeProcessor              │
   │   populateAdditionalAmountDetailsProcessor (×N per component)│
   │   populateTransactionAccountDetailsProcessor                 │
   │   updateLoanDueDetailsProcessor (paid_amount += current)     │
   │   updateLoanInstallmentDetailsProcessor                      │
   │   updateLoanAccountForExcessAmountProcessor                  │
   │   <API id="postTransaction">                                 │
   │     (txn_catalogue: LOAN_REPAYMENT)                          │
   │     legs (per rules):                                        │
   │       DR  CUSTOMER / BANK_RECV_AC   ₹total                   │
   │       CR  LOAN_PRIN_AC              ₹principal               │
   │       CR  INT_INCOME_AC (or SUSPENSE if NPA)  ₹interest      │
   │       CR  PENAL_INC_AC              ₹penalty                 │
   │       CR  FEE_INCOME_AC             ₹fee                     │
   │   createLoanAccountPaymentsDetailsProcessor (audit + excess) │
   │   checkNPAReverseMovementRequiredProcessor                   │
   │   checkAccountAutoClosureEligibilityProcessor                │
   │     if eligible:                                             │
   │       populateLoanAutoClosureReqProcessor                    │
   │       loanAccountDpdCalcProcessor (recompute final DPD)      │
   │       loanAccountAssetCriteriaProcessor                      │
   │       loanAccountAssetClassificationProcessor                │
   │       loanAccountAutoClosureProcessor                        │
   │         loan_status = CLOSED                                 │
   │       createLoanAccountClosureDetailsProcessor               │
   └─────────────────────────────────────────────────────────────┘
   ▼
5. notification + delete maker-checker draft
```

## Step-by-step (SHG/JLG)

For a child member's repayment, the entry is `childLoanRepayment` (group_mfi_orc.xml:33). Same mechanics with `is_child_account=true` set by `populateChildLoanAccountDataProcessor`, so the GL hit goes to `child_general_ledger` (gl_code prefixed `CG`).

If a parent-level repayment is captured (rare; usually it's per-member), the parent flow may queue REP events for siblings via `loan_account_events_queue`, replayed by `childLoanEventProcessingBatchJob`.

## DB writes summary

| Table | Change |
|---|---|
| `loan_due_details` | `paid_amount += current_paid_amount` per row touched; `current_paid_amount` cleared on next transaction |
| `loan_installment_details` | per-installment paid totals |
| `loan_account_payments_details` | new row per `loanRepayment` call (with `excess_amount`) |
| `loan_account.outstanding` (denorm) | refreshed via subsequent EOD `updateLoanAccountDerivedFieldsJob` |
| `loan_account.past_due_days` | recomputed inline if auto-closure eligible |
| `loan_account.asset_criteria_slabs_id` | recomputed if NPA reverse-movement eligible |
| `loan_account.loan_status` | `CLOSED` if auto-closure fired |
| `transaction_master` | new txn row |
| `transaction_partition_details` | DR/CR rows per accounting rule |
| `transaction_details` | per-account ledger rows |
| `account_balance` | balances updated |
| `audit_log` | framework auto |

## NPA + suspense

If the loan has `npa_ageing_start_date != null`, the appropriation processor sets `suspense_amount = interest_amount` ([`RepaymentApproppriationProcessor.java:113-115`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java#L113-L115)). Downstream, the GL leg credits a **suspense GL** instead of interest income. When the loan exits NPA, a separate flow moves accumulated suspense back to interest income.

## Failure modes → runbook

See [`../runbooks/repayment-mismatch.md`](../runbooks/repayment-mismatch.md). Most common:

| Symptom | Cause | First check |
|---|---|---|
| Wrong principal/interest split | `loan_product_asset_criteria` precedence wrong, or wrong `asset_criteria_slabs_id` | the row that drove appropriation |
| Repayment rejected with "not eligible" | Loan is in `InactiveLoanStatus` (WRITOFF / DISB_CNCL / FREEZE etc.) | `loan_account.loan_status` |
| GL net non-zero post-repayment | Rule binding wrong (placeholder → wrong internal_account) | `transaction_partition_details` for the txn ref |
| Repayment posted twice | Same `client_reference_number` not generating dedup | `clientReferenceNumberDedupProcessor` failed; check input |
| Auto-closure didn't fire | `checkAccountAutoClosureEligibilityProcessor` returned false | residual `loan_due_details` rows; or `loan_account.outstanding > 0` |

## Code anchors

- Top-of-flow: `mfi_orc.xml:2661` (`loanRepayment` Request)
- Group variant: `group_mfi_orc.xml:33` (`childLoanRepayment` Request)
- Appropriation: [`RepaymentApproppriationProcessor.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java)
- Posting engine: [`ExecuteTransactionRulesProcessor.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java)
- Component types: [`AccountingConstants.java:42-45`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/common/AccountingConstants.java#L42-L45)

## Where to dig deeper

- [`../accounting/05-flows.md`](../accounting/05-flows.md) §2
- [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md) §7 (appropriation)
- [`../engines/repayment-engine.md`](../engines/repayment-engine.md) (older deep narrative)
