# Runbook — Trial balance imbalance

## Symptoms

- `trialBalanceCalculation` for date D shows non-zero net on one or more GLs.
- Auditor or finance team flags an off-balance.

## First SQL

```sql
-- Top imbalanced GLs for the day
SELECT business_date, gl_code, debit_amount, credit_amount,
       (debit_amount - credit_amount) AS net
  FROM mfi_accounting.trial_balance
 WHERE business_date = ?
 ORDER BY ABS(debit_amount - credit_amount) DESC
 LIMIT 50;

-- Drill into one suspect GL — every txn that hit it
SELECT tm.transaction_ref_no, tm.transaction_catalogue_id,
       tpd.account_number, tpd.cr_dr_indicator, tpd.amount,
       tpd.gl_code, tm.created_on
  FROM mfi_accounting.transaction_partition_details tpd
  JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_master_id
 WHERE tpd.gl_code = ?
   AND tm.created_on::date = ?
 ORDER BY tm.created_on;
```

## Decision tree

Most imbalances are **per-transaction asymmetric legs**. Walk the smallest imbalance first.

### A. One leg posted, other didn't

Example: `transaction_master` has the row, `transaction_partition_details` shows only the DR side.

Cause: a rule in the catalogue evaluated to zero for the credit leg. Check the rule's `condition_expression` in `transaction_accounting_rule` — likely it referenced an ExecutionContext key that wasn't populated by an earlier processor.

`ExecuteTransactionRulesProcessor` skips legs where `calculatedAmount == 0` ([line 343](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java#L343)). The fix is upstream — find the processor that should have populated the missing key.

### B. Both legs posted but to the wrong GL

Both legs hit the same `internal_account` (or two accounts that happen to map to the same GL). Net on that GL is zero, but the other GL in the *intended* pair has imbalance.

Find the rule in `transaction_accounting_rule` for the catalogue. Resolve `(debit_account_placeholder, credit_account_placeholder)` against `product_transaction_catalogue_placeholder` for the loan's product → confirm both placeholders bind to the right `internal_account_definition_id` + `gl_code`. A swap or duplicate row is the bug.

### C. Child loan posted to parent GL (or vice versa)

If the txn was for a SHG/JLG child but `is_child_account` wasn't set in the ExecutionContext, the engine doesn't prefix the GL code with `CG`. Result: child txn lands in `general_ledger` instead of `child_general_ledger`, throwing the parent GL's TB off.

Check the calling processor's `populateAdditionalInformationProcessor` IParams — was `is_child_account` set?

### D. Reversal didn't reverse

A `reverseTransaction` should produce mirror legs (DR/CR flipped). Check `transaction_reversal_document` for the original txn ref → the reversal txn ref. If only the original side is in TB, the reversal Request didn't run (or ran but failed). Replay via the same Request with the original txn's metadata.

### E. Tax leg miscomputed

If `entry_type = 'TAX'`, the engine called `taxEngine.compute(...)`. Check `tax_component_slab` for matching slab against the source amount. If no slab matched → tax leg is zero → asymmetric.

Engine: [`TaxEngine.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/core/TaxEngine.java)

### F. Pricing leg miscomputed

`entry_type = 'PRICE'` calls `priceEngine.compute(...)` → walks `price_setup` slabs. Same pattern as tax.

Engine: [`PriceEngine.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/core/PriceEngine.java)

### G. EOD posting partial

If the imbalance is huge and matches the daily accrual amount, `interestAccrualPosting` (or `penalInterestAccrualBooking`) may have failed mid-batch. Check `batch_failure_audit` for the batch run.

## Cross-cutting checks

```sql
-- Per-day sanity: every txn should have legs that sum to zero
SELECT tm.transaction_ref_no,
       SUM(CASE WHEN tpd.cr_dr_indicator = 'D' THEN  tpd.amount ELSE 0 END) AS total_dr,
       SUM(CASE WHEN tpd.cr_dr_indicator = 'C' THEN -tpd.amount ELSE 0 END) AS total_cr,
       SUM(CASE WHEN tpd.cr_dr_indicator = 'D' THEN  tpd.amount ELSE -tpd.amount END) AS net
  FROM mfi_accounting.transaction_master tm
  JOIN mfi_accounting.transaction_partition_details tpd ON tpd.transaction_master_id = tm.id
 WHERE tm.created_on::date = ?
 GROUP BY tm.transaction_ref_no
HAVING SUM(CASE WHEN tpd.cr_dr_indicator = 'D' THEN tpd.amount ELSE -tpd.amount END) <> 0;
```

Any row returned = an asymmetric transaction.

## Code anchors

- Posting engine: [`ExecuteTransactionRulesProcessor.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java)
- TaxEngine / PriceEngine: same package
- Child GL prefix: [`ChildGeneralLedgerEntity.java:25`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/generalledger/entity/ChildGeneralLedgerEntity.java#L25)
- TB jobs: `batchnew/trialbalance/*`

## Related

- Posting engine: [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md)
- Money flow: [`../system/04-money-flow-rupee-journey.md`](../system/04-money-flow-rupee-journey.md)
- EOD pipeline: [`../flows/eod-bod-cycle.md`](../flows/eod-bod-cycle.md)
