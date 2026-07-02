# Runbook — EOD failed or didn't run

## Symptoms

- Today's `interest_accrual_details` empty / no rows for date D.
- `loan_account_derived_fields.business_date` is yesterday's, not today's.
- TB report missing.
- Reporting service didn't generate today's RBI ADF / UAM extracts.

## First check — did the scheduler fire?

```sql
-- Schedule registry
SELECT name, cron_expression, last_run_on, next_run_on, last_completion_status
  FROM mfi_batch.batch_schedule
 WHERE name = 'runEODJobs';

-- All EOD-related schedules
SELECT name, cron_expression, last_run_on, last_completion_status
  FROM mfi_batch.batch_schedule
 WHERE name IN (
   'runEODJobs', 'runBODJobs', 'loanAccountBillingJob',
   'interestAccrualCalculation', 'interestAccrualPosting',
   'penalInterestAccrualCalculation', 'penalInterestAccrualBooking',
   'loanAccountDpdCalcJob', 'loanAccountAssetCriteriaJob',
   'loanAccountAssetClassificationJob', 'updateLoanAccountDerivedFieldsJob',
   'trialBalanceCalculation', 'trialBalanceZeroisationJob',
   'generatePostEODReports'
 )
 ORDER BY name;
```

If `last_run_on` is older than expected → scheduler didn't fire.

## Decision tree

### A. Scheduler didn't fire at all

1. **Batch service alive?** Check process / health endpoint.
2. **`AutoScheduler` initialised?** It runs `@PostConstruct` on the batch service startup ([`AutoScheduler.java:30-44`](../../novopay-platform-batch/src/main/java/in/novopay/batch/core/service/AutoScheduler.java#L30-L44)). Check startup logs for "Loading schedules for tenant…".
3. **Multi-instance race?** If two batch service instances are deployed, one may have suppressed the schedule (no leader election; documented in [`../platform/multinode-batch.md`](../platform/multinode-batch.md)). Fix: deploy one batch instance per tenant, or implement leader election.
4. **Tenant resolution failed?** `BatchExecutionContextHelper` populates tenant; if null, the job can't fire.

### B. Scheduler fired but call into accounting failed

1. **404?** Most common: `BatchJob.name` was renamed without the matching `<Request name>` rename in accounting. Check accounting service log for "no Request found".
2. **Validator rejected `function_sub_code = BATCH` / `op_code = RESTART`?** Some Requests have strict patternFieldValidator. Check accounting validator failures.

### C. `runEODJobs` ran but a child job failed

`runEODJobs` is itself an orchestration that fires per-step Requests in sequence. Reading the orchestration block in `mfi_orc.xml::runEODJobs` shows the order. The first failure aborts subsequent steps.

1. Identify the failed step from the application log (timestamp + Request name).
2. Per-row failures go to `batch_failure_audit` table:
   ```sql
   SELECT * FROM mfi_accounting.batch_failure_audit
    WHERE created_on >= ?
    ORDER BY id DESC LIMIT 50;
   ```
3. Check Spring Batch meta tables in accounting datasource for step-level status:
   ```sql
   SELECT je.JOB_INSTANCE_ID, je.STATUS, je.START_TIME, je.END_TIME, ji.JOB_NAME, je.EXIT_MESSAGE
     FROM BATCH_JOB_EXECUTION je
     JOIN BATCH_JOB_INSTANCE ji ON ji.JOB_INSTANCE_ID = je.JOB_INSTANCE_ID
    WHERE ji.JOB_NAME = ?
    ORDER BY je.START_TIME DESC LIMIT 5;
   ```
4. Re-run the failed step individually via the batch service: `getBatchJobStatus` → manual restart Request.
5. Re-run subsequent steps in order — `runEODJobs` doesn't auto-resume from failure.

### D. EOD finished but reporting didn't

`generatePostEODReports` is the last step. Check:
1. Did `generatePostEODReports` log success?
2. Is the reporting service alive?
3. Reporting service log around timestamp — which `generate*Job` failed?
4. DMS upload of report files — can fail on auth or storage backend.

### E. Children-only EOD issue (SHG/JLG)

EOD operates on whatever children exist at run time. If child events were stuck in `loan_account_events_queue` at EOD start, those children were *not* in EOD's data set. Cross-link [`shg-jlg-children-missing.md`](shg-jlg-children-missing.md).

## Recovery — re-running an EOD step

Each step is restartable. The pattern:
1. Verify the step's Spring Batch instance is in FAILED / ABANDONED status.
2. From the batch service: invoke `createOrUpdateBatchJob` (status update) or directly trigger via `DirectJobExecutor` re-fire.
3. The step picks up where it left off (chunk-commit semantics) — re-running is safe for idempotent steps (most accruals UPSERT).

## Code anchors

- EOD aggregator: `mfi_orc.xml::runEODJobs`
- BOD aggregator: `mfi_orc.xml::runBODJobs`
- Job package roots: `batchnew/*` in accounting
- Scheduler: [`AutoScheduler.java`](../../novopay-platform-batch/src/main/java/in/novopay/batch/core/service/AutoScheduler.java), [`SchedulingGroupProcessor.java`](../../novopay-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulingGroupProcessor.java)

## Related

- EOD/BOD flow: [`../flows/eod-bod-cycle.md`](../flows/eod-bod-cycle.md)
- Batch atlas: [`../system/07-batch-atlas.md`](../system/07-batch-atlas.md)
- Multinode race: [`../platform/multinode-batch.md`](../platform/multinode-batch.md)
- Batch service: [`../services/novopay-platform-batch.md`](../services/novopay-platform-batch.md)
