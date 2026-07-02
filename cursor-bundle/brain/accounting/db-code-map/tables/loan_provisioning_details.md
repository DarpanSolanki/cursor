# `mfi_accounting.loan_provisioning_details`

> Per-loan, per-provisioning-event row. 9 cols. Set by EOD `loanProvisioningPosting` after asset classification.

## Schema (live, 9 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `account_id` | |
| `base_amount` | Outstanding amount provision applies to |
| `provision_rate` | Rate from `asset_classification_master.provisioning_rate` |
| `provisioning_amount` | Computed (base × rate) |
| `asset_classification_slab_id` | FK |
| `transaction_client_reference_number` | Idempotency key for the provisioning GL hit |
| `transaction_date` | When provisioning was posted |
| `transaction_reversal_date` | Set if reversed (rare) |

## Writers

- `loanProvisioningPosting` Request — INSERT per provisioning posting
- Reversal flow if asset class downgrade → upgrade requires provision adjustment

## Readers

- RBI ADF reporting (provisioning extract)
- `loan_account_derived_fields.provisioning_amount` populated from this

## Related Requests

- `loanProvisioningPosting` — primary writer
- Triggered by `runEODJobs` after `loanAccountAssetClassificationJob`

## Related flows

- [NPA & provisioning](../../../flows/npa-and-provisioning.md) — primary

## GL impact

```
DR  PROVISIONING_EXPENSE_AC   ₹provisioning_amount
CR  PROVISIONING_LIABILITY_AC ₹provisioning_amount
```

## Gotchas

1. **Asset class change → provisioning recompute.** Each new classification can produce a new row here.
2. **`transaction_client_reference_number`** is what `postTransaction.client_reference_number` dedup matches.
