# Flow — NPA classification + provisioning

## Mental model

Per loan, every EOD: recompute DPD → look up the asset criteria slab → set the asset classification → derive provisioning. A repayment can also reverse-promote a loan out of NPA (the "NPA reverse movement" check).

## Services involved

- accounting (sole owner) + batch service (scheduler) + reporting (extracts)

## The daily chain (inside `runEODJobs`)

```
1. loanAccountDpdCalcJob
   ─ For every active loan, recompute past_due_days based on current loan_due_details
   ─ UPDATE loan_account.past_due_days

2. loanAccountAssetCriteriaJob
   ─ For each loan, walk asset_criteria_slabs for the loan's asset_criteria_master
     (bound via loan_product_asset_criteria for the loan's product)
   ─ Pick the slab whose DPD range contains the loan's DPD
     example: DPD 0-30 → STD slab, 31-60 → SMA-1, 61-90 → SMA-2, 91+ → SUBSTANDARD
   ─ UPDATE loan_account.asset_criteria_slabs_id + asset_criteria_group_id

3. loanAccountAssetClassificationJob
   ─ Map slab → asset_classification (master in asset_classification_master /
     _slabs)
   ─ Write the dated record (for reporting)
   ─ UPDATE loan_account_derived_fields.asset_classification

4. updateLoanAccountDerivedFieldsJob
   ─ Refresh denorm: outstanding, npa_ageing_start_date, last DPD movement, etc.
```

## NPA reverse movement (inside repayment path)

Inside `loanRepayment` (and `childLoanRepayment`), after appropriation:

```
checkNPAReverseMovementRequiredProcessor
  ─ if total outstanding cleared enough to drop below NPA threshold
       and continuous-good-conduct rules satisfied:
       UPDATE loan_account.npa_ageing_start_date = NULL
       UPDATE loan_account.asset_criteria_slabs_id to non-NPA slab
       suspense GL drained back to interest income (via separate posting)
```

The exact "good conduct" rule is in `checkNPAReverseMovementRequiredProcessor`. RBI's framework requires that NPA loans only step down after sustained good payment behaviour.

## Provisioning

After classification, `loan_provisioning_details` records the per-loan provisioning amount based on slab × outstanding × provisioning rate. The provisioning posting (`loanProvisioningPosting`) hits the GL:

```
DR  PROVISIONING_EXPENSE_AC   ₹provision_amount
CR  PROVISIONING_LIABILITY_AC ₹provision_amount
```

## Manual override / vendor feed

- `bulkFileToSGAssetCriteriaGroupUpdateJob` allows ops to upload a CSV that overrides slab assignment.
- `bulkSGToSecNpaReverseFeedFileJob` ingests RBI/SCB secondary-NPA reverse-feed files.
- `bulkOutboundSecNpaReverseFeedFileJob` produces the outbound submission.

## SHG/JLG specifics

- Each child has its own DPD; child slab/classification computed independently.
- Parent's DPD = max across children (denorm via `updateLoanAccountDerivedFieldsJob`).
- A single bad member can pull the parent into a worse bucket while siblings are STD.

## Tables

| Table | Role |
|---|---|
| `asset_classification_master`, `asset_classification_slabs` | Master classifications (e.g. STD / SMA-0/1/2 / SUBSTANDARD / DOUBTFUL / LOSS) |
| `asset_criteria_master`, `asset_criteria_slabs` | DPD ranges → classification slabs |
| `asset_criteria_group` | Grouping for sharing across products |
| `loan_product_asset_criteria` | Per-product binding + appropriation precedence + liquidation order |
| `loan_account.past_due_days`, `asset_criteria_slabs_id`, `asset_criteria_group_id`, `npa_ageing_start_date` | Per-loan current state |
| `loan_account_derived_fields.asset_classification` | Per-loan dated denorm |
| `loan_provisioning_details` | Per-loan provisioning records |

## Failure modes → runbook

See [`../runbooks/npa-classification-incorrect.md`](../runbooks/npa-classification-incorrect.md). Quick triage:

| Symptom | First check |
|---|---|
| DPD looks right but slab wrong | `asset_criteria_slabs` ranges configuration |
| DPD outdated | `loanAccountDpdCalcJob` last successful run |
| NPA didn't reverse after payment | `checkNPAReverseMovementRequiredProcessor` decision; outstanding may still cross threshold |
| Reverse-feed file not applied | `bulkSGToSecNpaReverseFeedFileJob` log; `file_staging_sec_npa_reverse_feed_file` row state |

## Where to dig deeper

- Lifecycle (NPA-related statuses): [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md)
- Asset criteria + appropriation interplay: [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md) §7
- EOD pipeline: [`eod-bod-cycle.md`](eod-bod-cycle.md)
