# NPA classification → tables touched

Flow narrative: [`../../../flows/npa-and-provisioning.md`](../../../flows/npa-and-provisioning.md)

NPA classification is a 3-step chain inside `runEODJobs` (steps 6-8 in [eod-bod.md](eod-bod.md)). Plus inline `checkNPAReverseMovementRequiredProcessor` in repayment.

## Daily classification chain

| Step | Job (Request) | Tables written | Tables read |
|---|---|---|---|
| 1 | `loanAccountDpdCalcJob` | `loan_account.past_due_days` (UPDATE) | `loan_due_details` (oldest unpaid `due_date`) |
| 2 | `loanAccountAssetCriteriaJob` | `loan_account.asset_criteria_group_id`, `asset_criteria_slabs_id` (UPDATE) | `loan_product_asset_criteria` (binding by product), `asset_criteria_slabs` (DPD bands) |
| 3 | `loanAccountAssetClassificationJob` | `loan_account.asset_classification_slabs_id`, `npa_ageing_start_date`, `npa_ageing_days`, `npa_tagging_date` (UPDATE) | `asset_classification_master`, `asset_classification_slabs` |
| 4 | `updateLoanAccountDerivedFieldsJob` | `loan_account_derived_fields.asset_classification`, `is_npa`, `provisioning_amount` (INSERT per loan per day) | all of the above |
| 5 | `loanProvisioningPosting` | `loan_provisioning_details` (INSERT) + `transaction_master` + `transaction_partition_details` (provisioning GL hit: DR provisioning_expense / CR provisioning_liability) | `asset_classification_master.provisioning_rate` × outstanding |

## NPA reverse-movement (inline, during repayment)

Inside `loanRepayment` / `childLoanRepayment`, after `RepaymentApproppriationProcessor` runs:

| Step | Action |
|---|---|
| `checkNPAReverseMovementRequiredProcessor` | Decides if loan can step down NPA (sustained good conduct rule) |
| If yes → `loan_account.npa_ageing_start_date = NULL` and inline asset_criteria + classification re-run | UPDATE |
| Suspense GL → interest income GL movement (separate posting) | new `transaction_master` row |

## Vendor / manual override

| Source | Tables written |
|---|---|
| `bulkSGToSecNpaReverseFeedFileJob` (RBI vendor reverse-feed) | `loan_account.is_sec_npa`, `sec_npa_*` columns; staging in `file_staging_sec_npa_reverse_feed_file` |
| `bulkFileToSGAssetCriteriaGroupUpdateJob` (ops CSV override) | `loan_account.asset_criteria_group_id`; staging in `file_staging_asset_criteria_group_update` |

## Diagnostic queries

```sql
-- Current NPA distribution
SELECT loan_status, asset_classification_slabs_id, COUNT(*)
  FROM mfi_accounting.loan_account
 WHERE is_deleted=false
 GROUP BY 1, 2 ORDER BY 1, 2;

-- Loans in NPA (npa_ageing_start_date != NULL)
SELECT a.account_number, la.past_due_days, la.npa_ageing_days, la.npa_ageing_start_date
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE la.npa_ageing_start_date IS NOT NULL
 ORDER BY la.past_due_days DESC LIMIT 50;
```

## Cross-references

- [`tables/asset_criteria_master.md`](../tables/asset_criteria_master.md), [`tables/asset_criteria_slabs.md`](../tables/asset_criteria_slabs.md), [`tables/asset_classification_master.md`](../tables/asset_classification_master.md), [`tables/loan_product_asset_criteria.md`](../tables/loan_product_asset_criteria.md)
- Runbook: [`../../../runbooks/npa-classification-incorrect.md`](../../../runbooks/npa-classification-incorrect.md)
- EOD chain: [eod-bod.md](eod-bod.md)
