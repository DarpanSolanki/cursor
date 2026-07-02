# `mfi_accounting.asset_criteria_master`

> Master — named DPD-criteria sets (e.g. "MFI standard rule"). Each has many slabs.

## Schema (live, 11 cols)

Includes `id`, `code`, `name`, `description`, `category`, `liquidation_order`, `delinquency_string_format`, status/audit cols.

## JPA entity

[`assetcriteriamaster/entity/AssetCriteriaMasterEntity.java`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/assetcriteriamaster/)

## Writers

- `createOrUpdateAssetCriteriaMaster` flow

## Readers

- `loanAccountAssetCriteriaProcessor` (joined via `loan_product_asset_criteria` to find the right criteria set per product)

## Related

- See [`asset_criteria_slabs.md`](asset_criteria_slabs.md) for the slab structure
- See [`loan_product_asset_criteria.md`](loan_product_asset_criteria.md) for product binding
- [NPA flow](../../../flows/npa-and-provisioning.md)
