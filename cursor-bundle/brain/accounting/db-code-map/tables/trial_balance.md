# `mfi_accounting.trial_balance`

> Daily GL snapshot. One row per (business_date, gl_code). The daily ledger close + the input for regulatory reporting.

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `business_date` | The day this snapshot covers |
| `gl_code` | The GL code (matches `general_ledger.code`) |
| `debit_amount`, `credit_amount` | Aggregated DR / CR for the day |
| `opening_balance`, `closing_balance` | Day-start / day-end |
| `currency`, `office_id` | Scope |
| `created_on` | When the row was written |

## Writers

- [`TrialBalanceCalculation*` Spring Batch job](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/trialbalance/) — INSERT one row per (business_date, gl_code)
- `TrialBalanceZeroisationJob` — UPDATE closing_balance / carry forward

## Readers

- `generateTBZeroisationReport` — produces the human-readable summary
- Reporting service (RBI ADF)
- TB imbalance triage

## Related Requests

- `trialBalanceCalculation` (mfi_orc.xml) — primary writer
- `trialBalanceZeroisationJob` — closes/zeros for next day
- `generateTBZeroisationReport` — readable output
- All fired by `runEODJobs`

## Related flows

- [EOD/BOD cycle](../../../flows/eod-bod-cycle.md)
- [Money flow §Stage 5](../../../system/04-money-flow-rupee-journey.md)
- [TB imbalance runbook](../../../runbooks/trial-balance-imbalance.md)

## Common queries

```sql
-- Imbalanced GLs for a date
SELECT gl_code, debit_amount, credit_amount, (debit_amount - credit_amount) AS net
  FROM mfi_accounting.trial_balance
 WHERE business_date = ? AND debit_amount <> credit_amount
 ORDER BY ABS(debit_amount - credit_amount) DESC LIMIT 50;

-- Or use canned query: db-tools/canned-queries/05-trial-balance-imbalance.sql
```

## Gotchas

1. **Built from `transaction_partition_details`** — bugs upstream surface as imbalance here.
2. **`trial_balance_run_history`** records each run's status — useful for "did TB run?" triage.
3. **Zeroisation carries closing → next-day opening** — wrong opening = compounded daily error.
