# `mfi_accounting.interest_accrual_details`

> The EOD interest-accrual ledger. One row per (loan_account, accrual period). Verified live: 11 columns.

## Purpose

Holds the daily-or-periodic accrual records computed by `interestAccrualCalculation` and posted to GL by `interestAccrualPosting`. The EOD heartbeat — if `last_accrual_posted_date` is missing for today, EOD didn't run.

## Schema (verified live)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `account_id` | FK → `loan_account.account_id` |
| `base_amount` | Principal base for accrual |
| `start_date`, `end_date` | Accrual period (often *future-scheduled* — not "today") |
| `interest_rate` | Effective rate for the period |
| `total_accrued_amount` | Cumulative accrued |
| `carry_over_amount` | Residue from rounding |
| `total_accrual_posted_amount` | Cumulative posted to GL |
| `last_accrual_posted_date` | When the row was last posted (this is the "EOD heartbeat" column) |
| `loan_installment_details_id` | FK → installment row |

## JPA entity

[`loan/interest/normal/`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/interest/normal/) — entity in this package

## Writers

- [`InterestAccrualCalculationItemWriter`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/interest/interestaccrualcalculation/) — INSERT/UPSERT (during calc)
- `InterestAccrualBookingItemWriter` — UPDATE `last_accrual_posted_date`, `total_accrual_posted_amount` (during posting)

## Readers

- `InterestAccrualBookingItemReader` — pulls unposted rows for posting
- 360-view + reporting + EOD verification queries

## Related Requests

- `interestAccrualCalculation` (loans_orc.xml) — primary writer
- `interestAccrualPosting` — updates posted amount + posts to GL via `postTransaction`
- Both fired by `runEODJobs`

## Related flows

- [EOD/BOD cycle](../../../flows/eod-bod-cycle.md)
- [Money flow §Stage 2](../../../system/04-money-flow-rupee-journey.md)

## Common queries

```sql
-- EOD heartbeat (last 14 days)
SELECT DATE(last_accrual_posted_date) AS posted_day,
       COUNT(*), SUM(total_accrual_posted_amount)
  FROM mfi_accounting.interest_accrual_details
 WHERE last_accrual_posted_date >= CURRENT_DATE - INTERVAL '14 days'
 GROUP BY 1 ORDER BY 1 DESC;

-- Or use canned query: db-tools/canned-queries/04-todays-accruals.sql
```

## Gotchas

1. **`end_date` is *scheduled* accrual end — often months in the future.** DON'T use as EOD heartbeat. Use `last_accrual_posted_date`.
2. **In QA envs the business clock may be advanced** via `mfi_simulator` — `last_accrual_posted_date` may exceed wall-clock today.
3. **Idempotency**: keyed on `(account_id, accrual_period)`; UPSERT.
4. **`carry_over_amount`** captures rounding residue between periods.
