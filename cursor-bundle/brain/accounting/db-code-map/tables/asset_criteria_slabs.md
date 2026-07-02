# `mfi_accounting.asset_criteria_slabs`

> The DPD-range → asset-classification mapping. Each row = one DPD bucket (e.g. "31-60 days = SMA-1").

## Purpose

Per criteria-master, defines DPD ranges and the resulting asset classification. Read by EOD `loanAccountAssetCriteriaJob` to set `loan_account.asset_criteria_slabs_id` based on `past_due_days`.

## Schema (live, 16 cols)

Key columns: `id`, `asset_criteria_master_id`, `min_dpd`, `max_dpd`, `asset_classification_slab_id`, `penal_interest_rate`, `provisioning_rate`, status/audit.

## JPA entity

[`assetcriteriamaster/entity/AssetCriteriaSlabsEntity.java`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/assetcriteriamaster/)

## Writers

- Master CRUD via `createOrUpdateAssetCriteriaMaster` flow

## Readers

- [`loanAccountAssetCriteriaProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/) — looks up slab for a loan's DPD
- `loanProductAssetCriteriaDAOService.getAssetCriteriaSlabDetailsByProductAndAssetCriteriaSlabId` — used by `RepaymentApproppriationProcessor` to fetch appropriation precedence + liquidation order ([`RepaymentApproppriationProcessor.java:71-79`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java#L71-L79))

## Related Requests

- `loanAccountAssetCriteriaJob` (EOD)
- `loanRepayment`, `childLoanRepayment` (read for appropriation order)

## Related flows

- [NPA & provisioning](../../../flows/npa-and-provisioning.md)
- [Repayment end-to-end](../../../flows/repayment-end-to-end.md)
- [Posting engine §7](../../08-gl-posting-engine.md#7-the-repayment-appropriation-step-preceeds-posting)

## Common queries

```sql
-- All slabs in a criteria master
SELECT min_dpd, max_dpd, asset_classification_slab_id, penal_interest_rate, provisioning_rate
  FROM mfi_accounting.asset_criteria_slabs
 WHERE asset_criteria_master_id = ?
 ORDER BY min_dpd;
```

## Gotchas

1. **Wrong DPD ranges = wrong NPA bucket = wrong provisioning** — high-impact master data, change carefully.
2. **`penal_interest_rate`** here drives `penalInterestAccrualCalculation`.
