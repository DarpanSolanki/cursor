# Runbook — Repayment posted wrong amount/component

## Symptoms

- Customer disputes how a repayment was allocated (e.g. paid ₹5000 → expected ₹3000 principal + ₹2000 interest, but got ₹4000 P + ₹1000 I).
- Or repayment posted but `loan_account.outstanding` didn't update as expected.
- Or repayment rejected with "not eligible".

## First SQL

```sql
-- Latest payment record
SELECT * FROM mfi_accounting.loan_account_payments_details
 WHERE loan_account_id = ? ORDER BY id DESC LIMIT 5;

-- Per-component due rows at the time of payment (read these in payment-time order)
SELECT due_date, component_type, due_amount, paid_amount, waived_amount, current_paid_amount
  FROM mfi_accounting.loan_due_details
 WHERE loan_account_id = ? ORDER BY due_date, component_type;

-- The product's appropriation rule
SELECT lpac.*
  FROM mfi_accounting.loan_product_asset_criteria lpac
  JOIN mfi_accounting.loan_account la
    ON la.loan_product_id = lpac.product_id
   AND la.asset_criteria_slabs_id = lpac.asset_criteria_slabs_id
 WHERE la.id = (
   SELECT id FROM mfi_accounting.loan_account
    WHERE account_id = (SELECT id FROM mfi_accounting.account WHERE account_number = ?)
 );

-- Loan status at the time of payment
SELECT loan_status, asset_criteria_slabs_id, npa_ageing_start_date
  FROM mfi_accounting.loan_account
 WHERE id = ?;
```

## Decision tree

### A. Repayment rejected with "not eligible"

`checkEligibleForRepaymentAppropriationProcessor` rejects when loan is in any `InactiveLoanStatus`:
`FORECLOSURE_FREEZE`, `DISB_CNCL_FREEZE`, `LOAN_RESTR_FREEZE`, `LOAN_REBKG_FREEZE`, `DEATH_FORECLOSURE_FREEZE`, `PART_PREPAYMENT_FREEZE`, `CLOSED`, `DISB_CNCL`, `WRITOFF`.

Read [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md) for the full state list. Resolve the underlying state first (foreclose stuck? part-prepayment pending?).

### B. Wrong principal/interest split

The `loan_product_asset_criteria` row for the loan's (product, slab) defines:
- 4 component slots: `comp1`–`comp4` (each is one of `APP_LOGIC_PRIN`, `APP_LOGIC_INT`, `APP_LOGIC_PNLT`, `APP_LOGIC_FEES`)
- `liquidation_order`: `LIQ_INSTL` / `LIQ_COMP` / `LIQ_INSTL_CHRG_COMP`

Walk [`RepaymentApproppriationProcessor.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java) by hand against the due rows. If actual splits don't match what the algorithm would produce, the bug is one of:

1. **Master data wrong** — `loan_product_asset_criteria` row has the wrong precedence or liquidation order.
2. **Slab assignment wrong** — `loan_account.asset_criteria_slabs_id` points to the wrong slab. Check NPA jobs (last EOD).
3. **Stale due row** — a billing job didn't run, so an INT row was missing → engine over-paid PRIN.
4. **NPA suspense shunt** — `loan_account.npa_ageing_start_date != null` causes interest to be reported as `suspense_amount` instead of credited to interest income. Customer-facing report may show this as "INT 0, suspense 1500".

### C. Repayment posted twice (same amount)

`clientReferenceNumberDedupProcessor` should reject duplicates. Check:
1. The two `transaction_master` rows — do they have different `client_reference_number`?
2. If different: the caller (payments / webapp) generated two distinct refs → caller bug.
3. If same: dedup didn't fire → check that `clientReferenceNumberDedupProcessor` is enabled in the orchestration for the call path.

### D. GL net non-zero post-repayment

Cross-link to [`trial-balance-imbalance.md`](trial-balance-imbalance.md). Pull the txn ref's `transaction_partition_details` rows and verify legs sum to zero by GL.

### E. Auto-closure didn't fire on a fully-paid loan

`checkAccountAutoClosureEligibilityProcessor` returned false. Check:
1. `loan_due_details` — are any rows still showing `due_amount - paid_amount - waived_amount > 0`?
2. `loan_account.outstanding` denorm (refreshed by EOD `updateLoanAccountDerivedFieldsJob`).
3. If everything reads "paid up", manual `loanAccountClosure` batch can pick it up — verify scheduled.

### F. SHG/JLG — child repayment not splitting to siblings

Child repayment is **per-child only**. Sibling effects (e.g. group-level NPA recompute, parent-level closure check) happen on `loan_account_events_queue` events fanned out by `childLoanEventProcessingBatchJob`. See [`shg-jlg-children-missing.md`](shg-jlg-children-missing.md) §A.

## Code anchors

- Eligibility check: [`CheckEligibleForRepaymentAppropriationProcessor.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/CheckEligibleForRepaymentAppropriationProcessor.java)
- Appropriation: [`RepaymentApproppriationProcessor.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java)
- Component constants: [`AccountingConstants.java:37-45`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/common/AccountingConstants.java#L37-L45)
- Posting engine: [`ExecuteTransactionRulesProcessor.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java)

## Related

- Repayment flow: [`../flows/repayment-end-to-end.md`](../flows/repayment-end-to-end.md)
- Posting engine: [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md)
- Lifecycle: [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md)
