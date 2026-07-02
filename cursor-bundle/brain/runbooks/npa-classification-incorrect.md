# Runbook — NPA / DPD classification incorrect

## Symptoms

- A clearly-overdue loan is marked STD; or a paid-up loan is still SMA-1 / Substandard.
- DPD reading on `loan_account.past_due_days` doesn't match calendar reality.
- Customer / RBI auditor flags wrong asset classification.

## First SQL

```sql
SELECT la.past_due_days, la.asset_criteria_slabs_id, la.asset_criteria_group_id,
       la.npa_ageing_start_date, la.updated_on
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE a.account_number = ?;

-- When was the loan's derived field last refreshed?
SELECT MAX(business_date) AS last_refresh
  FROM mfi_accounting.loan_account_derived_fields
 WHERE loan_account_id = ?;

-- Slab boundaries the loan is currently in
SELECT acs.*
  FROM mfi_accounting.asset_criteria_slabs acs
  JOIN mfi_accounting.loan_account la ON la.asset_criteria_slabs_id = acs.id
 WHERE la.id = ?;

-- All slabs in the master so you can see what range it should fall into
SELECT acs.id, acs.asset_criteria_master_id,
       acs.dpd_min, acs.dpd_max, acs.asset_classification_slab_id
  FROM mfi_accounting.asset_criteria_slabs acs
 WHERE acs.asset_criteria_master_id = (
   SELECT lpac.asset_criteria_master_id
     FROM mfi_accounting.loan_product_asset_criteria lpac
     JOIN mfi_accounting.loan_account la ON la.loan_product_id = lpac.product_id
    WHERE la.id = ?
    LIMIT 1
 )
 ORDER BY acs.dpd_min;
```

## Decision tree

### A. `updated_on` is yesterday or older

`loanAccountDpdCalcJob` / `loanAccountAssetCriteriaJob` / `loanAccountAssetClassificationJob` did not run for this loan. Likely a batch failure — see [`eod-failed.md`](eod-failed.md).

### B. DPD looks right, slab is wrong

The slab's range doesn't match. Two sub-cases:

1. **Master data wrong** — `asset_criteria_slabs.dpd_min` / `dpd_max` configured incorrectly (likely after a recent slab update). Verify with the slab table query above. Fix master data + run `loanAccountAssetCriteriaJob` again.

2. **Wrong asset_criteria_master bound to product** — `loan_product_asset_criteria` rows missing or pointing to a wrong criteria master. Check the binding for the loan's product.

### C. NPA didn't reverse after a payment

When a customer pays enough to clear NPA threshold, `checkNPAReverseMovementRequiredProcessor` should reverse the classification. If it didn't:

1. Outstanding may *still* be above threshold — verify total `loan_due_details` outstanding.
2. Continuous-good-conduct rule not satisfied (RBI requires sustained behaviour). Check the processor's logic for the loan's history.
3. The processor ran but the slab demote happened only on next EOD — wait for next-day refresh.

### D. Reverse-feed file not applied (sec NPA)

Vendor-fed corrections come via `bulkSGToSecNpaReverseFeedFileJob`:

```sql
SELECT * FROM mfi_accounting.file_staging_sec_npa_reverse_feed_file
 WHERE loan_account_no = ? ORDER BY id DESC;
```

If staging has the row but it's `PENDING` / `FAILED`, the apply job didn't run or threw. Re-trigger `bulkSGToSecNpaReverseFeedFileJob`.

### E. Manual override via CSV

Operations can upload a CSV via `bulkFileToSGAssetCriteriaGroupUpdateJob`. If a recent override is wrong, find the row in the staging table and re-upload corrected data.

### F. SHG/JLG — child correct, parent wrong

Parent's DPD = max across children. If a parent shows the wrong DPD:
1. Verify each child's DPD individually.
2. `updateLoanAccountDerivedFieldsJob` should have aggregated to parent — check last run.
3. If a child event is stuck (`loan_account_events_queue`), a recent child payment may not have been reflected in parent's view. See [`shg-jlg-children-missing.md`](shg-jlg-children-missing.md).

## Root cause classes

| Class | Symptom |
|---|---|
| Batch didn't run | `updated_on` stale, EOD failure |
| Master data wrong | Slab ranges or product-criteria binding |
| Reverse movement gating | Continuous-conduct rule not met |
| Vendor feed pipeline | `file_staging_sec_npa_reverse_feed_file` rows in PENDING/FAILED |
| Cross-tenant misroute | Tenant resolution wrong (rare) |

## Code anchors

- DPD calc: `batchnew/derivedfields/*` and per-flow inline `loanAccountDpdCalcProcessor`
- NPA reverse check: `checkNPAReverseMovementRequiredProcessor` (in repayment + childLoanRepayment)
- Per-flow processors: `loanAccountAssetCriteriaProcessor`, `loanAccountAssetClassificationProcessor`

## Related

- NPA + provisioning flow: [`../flows/npa-and-provisioning.md`](../flows/npa-and-provisioning.md)
- EOD / BOD: [`../flows/eod-bod-cycle.md`](../flows/eod-bod-cycle.md)
- Lifecycle: [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md)
