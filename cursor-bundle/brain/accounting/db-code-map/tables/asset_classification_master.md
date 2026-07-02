# `mfi_accounting.asset_classification_master`

> Master — named asset classifications (e.g. STD, SMA-0, SMA-1, SMA-2, Substandard, Doubtful, Loss). The RBI categorisation that NPA jobs assign.

## Schema (live, 11 cols)

`id`, `code`, `name`, `description`, `category`, `provisioning_rate`, status/audit.

## JPA entity

[`assetclassificationmaster/`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/assetclassificationmaster/)

## Writers

- `createOrUpdateAssetClassificationMaster` flow

## Readers

- `loanAccountAssetClassificationProcessor` — final NPA tag derivation

## Related

- See [`asset_classification_slabs`](#) (sister table — bands within each classification)
- [NPA flow](../../../flows/npa-and-provisioning.md)
- Provisioning derivation reads this for rates
