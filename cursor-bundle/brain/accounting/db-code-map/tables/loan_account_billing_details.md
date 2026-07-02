# `mfi_accounting.loan_account_billing_details`

> EOD billing snapshot. One row per (loan_account, business_date) describing what's billed/due that day. Read by collections (LCS) for dunning.

## Schema (key columns)

| Column | Meaning |
|---|---|
| `loan_account_id` | FK |
| `business_date` | The day this row represents |
| `billed_amount` | Today's billed total |
| `due_principal`, `due_interest`, `due_penal`, `due_fee` | Per-component breakdown |
| `outstanding_amount` | Cumulative outstanding |
| `dpd_count` | DPD as of this date |
| audit cols | |

(Run `tools/inspect-table.sh loan_account_billing_details` for live schema.)

## Writers

- EOD `loanAccountBillingJob` — INSERT one row per active loan, per business_date

## Readers

- LCS / collection service via Kafka (`bulk_collection_data_*` topic)
- 360 views
- Reporting

## Related Requests

- `loanAccountBillingJob` — primary writer (fired by `runEODJobs`)

## Related flows

- [EOD/BOD cycle](../../../flows/eod-bod-cycle.md)

## Gotchas

1. **Daily snapshot** — fresh row per business_date even if nothing changed.
2. **Source of truth for collections** — LCS reads this rather than computing from due_details.
