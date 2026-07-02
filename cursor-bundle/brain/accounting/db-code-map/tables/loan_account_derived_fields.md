# `mfi_accounting.loan_account_derived_fields`

> Per-loan, per-day denormalised snapshot for fast reporting. Refreshed by EOD `updateLoanAccountDerivedFieldsJob`. Sister table `loan_account_derived_fields_monthly` for slower-moving fields.

## Purpose

Reading the live `loan_account` + `loan_due_details` + accruals + asset criteria for every reporting query is expensive. This table is the daily denorm — outstanding, DPD, NPA bucket, classification, provisioning info.

## Schema (representative)

| Column | Meaning |
|---|---|
| `loan_account_id` | FK |
| `business_date` | Snapshot date |
| `outstanding_principal`, `outstanding_interest`, `outstanding_total` | Live outstanding |
| `dpd_count` | DPD that day |
| `asset_classification` | The bucket (STD / SMA-* / Substandard / etc.) |
| `provisioning_amount` | Per-day provisioning |
| `is_npa` | Boolean |
| audit cols | |

## Writers

- EOD `updateLoanAccountDerivedFieldsJob` — INSERT one row per loan per day

## Readers

- Reporting service (RBI ADF, MIS extracts)
- 360 views
- LCS / collections aggregations

## Sister tables

- `loan_account_derived_fields_monthly` — slower fields, monthly cadence
- `loan_account_derived_fields_run_history` — audit of EOD runs

## Related Requests

- `updateLoanAccountDerivedFieldsJob`, `updateLoanAccountDerivedFieldsMonthlyJob`
- All reporting `generate*` Requests in trustt-platform-reporting

## Related flows

- [EOD/BOD cycle](../../../flows/eod-bod-cycle.md)
- [NPA & provisioning](../../../flows/npa-and-provisioning.md)

## Gotchas

1. **Stale = EOD didn't run for this loan** — if `MAX(business_date)` is yesterday or older, EOD missed it.
2. **Used by reporting** — drift here = wrong RBI ADF.
