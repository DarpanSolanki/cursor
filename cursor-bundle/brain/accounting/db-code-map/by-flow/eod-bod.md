# EOD/BOD daily cycle → tables touched

Flow narrative: [`../../../flows/eod-bod-cycle.md`](../../../flows/eod-bod-cycle.md)

`runEODJobs` is an aggregator Request that fans out into per-step child Requests. Each step writes specific tables. Order matters.

## BOD (~04:00 IST) — `runBODJobs`

| Step | Table | Action |
|---|---|---|
| Server clock advance | (server_clock or similar) | UPDATE `business_date` |
| Holiday roll-forward | `holiday`, `holiday_office` | calendar adjustment |
| `generateEnachPresentationFile` | `enach_presentation_*` (3 tables) | INSERT outbound presentation rows |
| `expirePendingMandatesBatchJob` | mandate state tables | UPDATE state |

## EOD (~21:00 IST) — `runEODJobs`

Sequential. Each step is a separate Request, so per-step failures are isolated.

| Step # | Job (Request name) | Tables written | Tables read |
|---:|---|---|---|
| 1 | `loanAccountBillingJob` | `loan_account_billing_details` (one row per active loan, today's business_date) | `loan_account`, `loan_due_details`, `loan_installment_details` |
| 2 | `interestAccrualCalculation` | `interest_accrual_details` (UPSERT per loan-period) | `loan_account`, `interest_setup` + slabs, `base_interest_*`, holiday, working_days |
| 3 | `interestAccrualPosting` | `interest_accrual_details` (UPDATE `last_accrual_posted_date`, `total_accrual_posted_amount`) + `transaction_master` + `transaction_partition_details` + `transaction_details` (per accrual row's GL hit) | `interest_accrual_details` (unposted), `transaction_accounting_rule` (catalogue=INT_ACCRUAL_BOOK) |
| 4 | `penalInterestAccrualCalculation` | `penal_interest_accrual_details` | `loan_account.past_due_days`, `asset_criteria_slabs.penal_interest_rate` |
| 5 | `penalInterestAccrualBooking` | `penal_interest_accrual_details` (posted), `loan_due_details` (INSERT PINT rows), txn family | similar |
| 6 | `loanAccountDpdCalcJob` | `loan_account.past_due_days` (UPDATE) | `loan_due_details` (compute DPD from oldest unpaid due_date) |
| 7 | `loanAccountAssetCriteriaJob` | `loan_account.asset_criteria_group_id`, `asset_criteria_slabs_id` (UPDATE) | `loan_product_asset_criteria` (binding), `asset_criteria_slabs` (DPD bands) |
| 8 | `loanAccountAssetClassificationJob` | `loan_account.asset_classification_slabs_id`, `npa_*` (UPDATE) | `asset_classification_master`, `asset_classification_slabs` |
| 9 | `updateLoanAccountDerivedFieldsJob` | `loan_account_derived_fields` (INSERT per loan per business_date) + `loan_account_derived_fields_run_history` (audit) | all of the above |
| 10 | `trialBalanceCalculation` | `trial_balance` (INSERT per gl_code per business_date), `trial_balance_run_history` | `transaction_partition_details` (aggregate) |
| 11 | `trialBalanceZeroisationJob` | `trial_balance` (UPDATE closing → next-day opening) | `trial_balance` |
| 12 | `generateTBZeroisationReport` | report file in DMS | `trial_balance` |
| 13 | `extractCasaBalanceFor180/182ProductCode` | extract files | `account_balance`, `account` |
| 14 | `generatePostEODReports` | dispatches to reporting service (RBI ADF, MIS, etc.) | reporting reads everything |

## Why the order matters

- **Billing before accrual** — accrual reads today's billed dues
- **Accrual before DPD** — DPD reflects new interest that's now overdue
- **DPD before asset criteria** — slab choice driven by DPD
- **Asset criteria before classification** — classification depends on slab
- **All before derived fields refresh** — denorm reads finalised values
- **All before trial balance** — TB snapshots final GL state for the day
- **Zeroisation last** — closes the day, sets next-day opening

## Failure isolation

Each step is a separate Spring Batch job. Per-row failures go to `batch_failure_audit`. A failed step blocks subsequent ones for that day's `runEODJobs` execution.

## QA gotcha — clock-advance

In QA envs the business clock is advanced via `mfi_simulator`. So `last_accrual_posted_date` may exceed wall-clock today. See [`tables/interest_accrual_details.md`](../tables/interest_accrual_details.md) gotchas.

## Cross-references

- [`tables/interest_accrual_details.md`](../tables/interest_accrual_details.md)
- [`tables/penal_interest_accrual_details.md`](../tables/penal_interest_accrual_details.md)
- [`tables/loan_account_derived_fields.md`](../tables/loan_account_derived_fields.md)
- [`tables/trial_balance.md`](../tables/trial_balance.md)
- [`tables/loan_account_billing_details.md`](../tables/loan_account_billing_details.md)
- Runbook: [`../../../runbooks/eod-failed.md`](../../../runbooks/eod-failed.md)
