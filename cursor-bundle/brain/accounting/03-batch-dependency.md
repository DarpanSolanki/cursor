# 03 · Accounting ↔ Batch dependency

## TL;DR

- `novopay-platform-batch` does **not** contain accounting business logic. It is a **scheduler + bulk-upload registry**.
- It owns three master entities: `BatchSchedule`, `BatchGroup`, `BatchJob`. Each `BatchJob.name` is the **API name** of an orchestration `<Request>` in some other service — almost always accounting.
- When a schedule fires, `DirectJobExecutor` (or `DirectGroupJobExecutor`) makes a **synchronous internal HTTP call** via `NovopayInternalAPIClient.callInternalAPI(executionContext, jobName, version, jobName, …)`. The gateway routes the call to whichever service owns that Request name (accounting for the vast majority).
- Accounting therefore **doesn't import the batch service**. The dependency is one-way: `batch → accounting` (HTTP/gateway), and the contract is the orchestration Request name.

## Batch service surface (from `novopay-platform-batch/deploy/.../ServiceOrchestrationXML.xml`)

```
createOrUpdateBatchSchedule           getBatchScheduleDetails        getBatchScheduleList    deleteBatchSchedule
createOrUpdateBatchGroup              getBatchGroupDetails           getBatchGroupList       deleteBatchGroup
createOrUpdateBatchJob                getBatchJobDetails             getBatchJobList         deleteBatchJob
bulkUploadBatch                       updateFileUpload               getAllBulkBatchUploadTypes
viewBulkBatchUploadFileStatus         downloadBatchUploadedFile      bulkBatchSubmitApplication
getBulkBatchUploadTemplate
getBatchJobLastInstance               getBatchJobStatus              getBatchJobStatusByRefNo
```

That's it — **22 Requests**, all about job/schedule registry and bulk-upload status. No interest-accrual, no NPA, no billing logic lives here.

## Core service classes (under `in.novopay.batch.core.service`)

| Class | Role |
|-------|------|
| `JobService` | CRUD for `BatchJob`, fetches latest run, status |
| `AutoScheduler` | Scans `BatchSchedule`, schedules jobs onto a thread pool |
| `SchedulerCommonService` | Shared scheduling helpers (cron parsing, next-fire, blackout) |
| `ScheduleBatchGroupExecutor` | Picks a `BatchGroup`'s ordered jobs; for each, dispatches to `DirectJobExecutor` |
| `DirectGroupJobExecutor` | Group-level Runnable; fires the group's jobs sequentially |
| `DirectJobExecutor` | **The bridge.** A `Runnable` per job. See below. |
| `BatchExecutionContextHelper` | Populates the `ExecutionContext` with tenant, run-id, job parameters |
| `SchedulingGroupProcessor` | Orchestration processor used by `bulkBatchSubmitApplication` etc. |

### `DirectJobExecutor` — the actual call site

```java
public class DirectJobExecutor implements Runnable {
    private PlatformTenant   platformTenant;
    private BatchJob         job;
    private ExecutionContext executionContext;
    private NovopayInternalAPIClient novopayInternalAPIClient;
    private String connectionTimeout;
    private String socketTimeout;

    @Override public void run() {
        ThreadLocalContext.setTenant(platformTenant);
        MDC.put("tenant", platformTenant.getTenantCode());
        startNormalJob();
    }

    private void startNormalJob() {
        try {
            executionContext.put("function_sub_code", "BATCH");
            executionContext.put("op_code", "RESTART");

            novopayInternalAPIClient.callInternalAPI(
                executionContext,
                job.getName(),     // ← matches `<Request name="…">` in accounting
                job.getVersion(),
                job.getName(),
                Integer.parseInt(connectionTimeout),
                Integer.parseInt(socketTimeout),
                true);
        } catch (Exception ex) {
            LOGGER.error("Failed job {} {}", job, ex);
        } finally {
            MDC.clear();
        }
    }
}
```

The same call shape appears in `DirectGroupJobExecutor`. So the **job-name string is the integration contract** — rename a Request in `loans_orc.xml` and the matching `BatchJob.name` row in `mfi_batch.batch_job` must be updated in lock-step.

## Inventory of accounting Requests fired by the batch service

Grouped by `batchnew/*` package and orchestration source.

### Day-cycle aggregators (mfi_orc.xml)

| Request | Purpose |
|---------|---------|
| `runEODJobs` | **5-step DPD → asset criteria → asset classification → penal accrual calc → penal accrual booking pipeline only.** ⚠ NOT a full EOD aggregator — see correction note below. |
| `runBODJobs` | Beginning-of-day: clock advance, holiday roll-forward, mandate reset, eNACH presentation file |
| `generatePostEODReports` | Trigger reporting service to render EOD report set (independent cron) |

> **Correction (2026-05-08, verified on 3.3.1.0.1):** `runEODJobs` previously documented as a master EOD aggregator. The actual orchestration ([`MfiRunEODJobsProcessor.java:23–28`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/custom/mfi/jobs/processor/MfiRunEODJobsProcessor.java#L23)) only sequentially invokes 5 child Requests via `novopayInternalAPIClient.callInternalAPI(...)`:
> 1. `loanAccountDpdCalcJob`
> 2. `loanAccountAssetCriteriaJob`
> 3. `loanAccountAssetClassificationJob`
> 4. `penalInterestAccrualCalculation`
> 5. `penalInterestAccrualBooking`
>
> **Billing, interest accrual + posting, derived fields refresh, trial balance calc + zeroisation, post-EOD reports** all run on **independent `mfi_batch.batch_schedule` rows** with their own cron expressions (~18:00 / 19:00 / 20:00 / 21:00 / 22:00 IST). They do NOT cascade through `runEODJobs`.
>
> **Implication for ops:** "EOD didn't run" can mean one of several distinct failures. Check `last_completion_status` per individual job in `mfi_batch.batch_schedule`. Restarting `runEODJobs` will NOT re-trigger billing or interest accrual.

### Interest

| Request | Source XML |
|---------|------------|
| `interestAccrualCalculation` | loans_orc |
| `interestAccrualPosting` | loans_orc |
| `penalInterestAccrualCalculation` | loans_orc |
| `penalInterestAccrualBooking` | loans_orc |

### Loan lifecycle batch

| Request | Source |
|---------|--------|
| `loanAccountDpdCalcJob` | loans_orc — DPD recompute |
| `loanAccountAssetCriteriaJob` | loans_orc — apply asset-criteria slabs |
| `loanAccountAssetClassificationJob` | loans_orc — promote to NPA bucket |
| `loanAccountBillingJob` | loans_orc — generate due records |
| `loanAccountClosure` | loans_orc — close paid-off accounts |
| `loanAdvanceRepayment` | loans_orc — apply standing payments to next due |
| `loanRecurringPaymentBatchApi` | loans_orc — recurring debit job |
| `rescheduleLoanAccountRescheduleBatch` | loans_orc — pending reschedule events |
| `registerLoanAccountRescheduleEvent` | loans_orc |
| `updateCollectionBatchDetails` | loans_orc |
| `updateLoanAccountDerivedFieldsJob` | mfi_orc |
| `updateLoanAccountDerivedFieldsMonthlyJob` | mfi_orc |

### Trial balance

| Request | Source |
|---------|--------|
| `trialBalanceCalculation` | mfi_orc |
| `trialBalanceZeroisationJob` | mfi_orc |
| `generateTBZeroisationReport` | mfi_orc |

### Bulk upload jobs (file-staging pattern: `bulkFileToSG…` ingests, `bulkSGTo…` dispatches)

| Pair | Domain |
|------|--------|
| `bulkFileToSGFinsallRepaymentJob` / `bulkSGToFinsallRepaymentJob` | Finsall repayment file ingest |
| `bulkFileToSGManualJournalEntriesJob` / `bulkSGToManualJournalEntriesJob` | Manual JE bulk |
| `bulkFileToSGForeclosureChargeUpdateJob` / `bulkSGToForeclosureChargeUpdateJob` | Foreclosure charge bulk |
| `bulkFileToSGNocBlockUnblockJob` / `bulkSGToNocBlockUnblockJob` | NOC block/unblock |
| `bulkFileToSGDispatchDetailsJob` / `bulkSGToDispatchDetailsJob` | Dispatch details |
| `bulkFileToSGSecNpaReverseFeedFileJob` / `bulkSGToSecNpaReverseFeedFileJob` / `bulkOutboundSecNpaReverseFeedFileJob` | Secondary-NPA reverse-feed |
| `bulkFileToSGManualHoldRemovalJob` | Manual-hold removal (no SG-to side, file-only) |
| `bulkFileToSGTransactionReversalJob` | Bulk transaction reversal |
| `bulkFileToSGAssetCriteriaGroupUpdateJob` | Asset-criteria group update |
| `bulkSGToDisbursementCancellationJob` | Disbursement cancellation |
| `bulkSGToPostDisbursementInsuranceUpdateJob` | Post-disbursement insurance update |
| `bulkSGToRefundMarkingJob` | Refund marking |

The `bulkFileToSG…` half is normally invoked by the gateway (file upload → batch-service `bulkUploadBatch` → orchestration call into accounting). The `bulkSGTo…` half is scheduled by batch service via the `BatchJob`/`BatchSchedule` registry.

### NOC / dispatch / extracts

`generateNocFileJob`, `extractCasaBalanceFor180ProductCode`, `extractCasaBalanceFor182ProductCode`, `accountingBankServiceRetryJob` (retries failed NEFT calls), `doGenericSyncSTPBankNEFNeftCallBack`, `doGenericSyncSTPBankNEINeftCallBack`.

### eNACH

`generateEnachPresentationFile`, `generateEnachRepresentationFile`, `expirePendingMandatesBatchJob`.

### Insurance jobs (loans_insurance_orc.xml)

Outbound + inbound + run-trigger triplets per provider:

```
outboundDeathForeclosureInsuranceJob          inboundDeathForeclosureInsuranceJob          runInboundDeathForeclosureInsuranceJob          deathForeclosureInsuranceJob
outboundDisbursementBajajErgoHealthInsuranceJob   inboundDisbursementBajajErgoHealthInsuranceJob   runInboundDisbursementBajajErgoHealthInsuranceJob
outboundDisbursementHdfcLifeLifeInsuranceJob     inboundDisbursementHdfcLifeLifeInsuranceJob     runInboundDisbursementHdfcLifeLifeInsuranceJob
outboundDisbursementHdfcErgoHealthInsuranceJob   inboundDisbursementHdfcErgoHealthInsuranceJob   runInboundDisbursementHdfcErgoHealthInsuranceJob
outboundDisbursementCancellationBajajErgoHealthInsuranceJob   inboundDisbursementCancellationBajajErgoHealthInsuranceJob   runInboundDisbursementCancellationBajajErgoHealthInsuranceJob
outboundDisbursementCancellationHdfcLifeLifeInsuranceJob      inboundDisbursementCancellationHdfcLifeLifeInsuranceJob      runInboundDisbursementCancellationHdfcLifeLifeInsuranceJob
outboundDisbursementCancellationHdfcErgoHealthInsuranceJob    inboundDisbursementCancellationHdfcErgoHealthInsuranceJob    runInboundDisbursementCancellationHdfcErgoHealthInsuranceJob
```

### Child loan (group_mfi_orc.xml) batch

`childLoanEventProcessingBatchJob` — fans out child-loan events queued during parent-loan disbursement / restructuring.

## How a job actually runs end-to-end

1. **Configure once.** A `BatchJob` row exists in `mfi_batch.batch_job` with `name = "interestAccrualCalculation"` and `version = "v1"`. A `BatchSchedule` row references it (cron `0 0 23 * * ?` say).
2. **Scheduler.** `AutoScheduler` reads schedules at startup (and on schedule-CRUD events) and registers them with a Spring `ThreadPoolTaskScheduler`.
3. **Fire.** At the cron time, the scheduler hands a `BatchExecutionContextHelper`-built `ExecutionContext` to a new `DirectJobExecutor` instance.
4. **Internal call.** `DirectJobExecutor.startNormalJob()` calls `NovopayInternalAPIClient.callInternalAPI(ctx, "interestAccrualCalculation", "v1", …)`.
5. **Routing.** The internal API client uses the platform service registry to resolve `interestAccrualCalculation` → `novopay-platform-accounting-v2`. It posts to that service's gateway endpoint.
6. **Accounting orchestration.** `OrchestrationXMLParser.getRequestFromOrcXML(tenant, "interestAccrualCalculation")` returns the Request from `loans_orc.xml`. `ServiceOrchestrator.executeProcessors(...)` fires the processor list, which kicks the Spring Batch `Job`.
7. **Spring Batch.** `InterestAccrualCalculationBatchConfigService` builds a partitioned `Step` (grid 10) wired with the `ItemReader/Processor/Writer` from `batchnew/interest/interestaccrualcalculation/*`.
8. **Status feedback.** Job progress + last-run status are queryable via batch service Requests `getBatchJobStatus`, `getBatchJobLastInstance`, `getBatchJobStatusByRefNo`. The accounting side does not push status; the batch service polls `BATCH_JOB_INSTANCE`/`BATCH_JOB_EXECUTION` (Spring Batch's own meta tables, owned by accounting's data source).

## Gotchas

- **Job-name typos are silent.** A renamed Request without a matching `BatchJob.name` update means the schedule fires and the internal API client returns a 404 — `DirectJobExecutor` only logs and moves on.
- **Tenant is required.** `ThreadLocalContext.setTenant(platformTenant)` is set inside `run()`, but if the scheduler-side context is missing the job will run under a stale tenant.
- **`function_sub_code = BATCH` and `op_code = RESTART`** are forced by `DirectJobExecutor`. Orchestration validators that gate on these need to allow them.
- **Spring Batch meta-tables live in the accounting schema.** The `BatchJob` registry in `mfi_batch` is a different concept from Spring Batch's own `BATCH_JOB_INSTANCE`. Do not confuse them when writing migration/audit queries.
- **Re-entrance.** Several batch jobs (e.g. `loanAccountBillingJob`) are restartable but not idempotent in the SQL sense — the framework relies on Spring Batch's `chunk` commit + the failure-audit table to skip already-processed rows.

## Recovery-path coverage map (which job heals which orphan)

When an orchestration aborts mid-flight, recovery happens via one of three doors: the CRR retry job, the child-event queue job, or a manual re-trigger of the parent Request. **Each door scans a specific table with a specific filter** — and one event type (`CLMT`) is **deliberately excluded from every scheduled door**, so its orphan recovery requires re-firing `disburseLoan`.

### Scanners — who reads what

| Scheduled job | Source table | SQL filter | Effect |
|---|---|---|---|
| **`accountingBankServiceRetryJob`** ([reader file:25-27](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/bankservicecallretry/AccountingBankServiceRetryJobIReader.java#L25)) | `client_request_response_log` (CRR) | `status = 'FAIL' AND eligible_for_retry = TRUE AND uri IS NOT NULL` | Re-POSTs the original outbound HTTP request. **Does NOT touch `loan_account_events_queue`.** |
| **`childLoanEventProcessingBatchJob`** ([reader file:24](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/childloaneventprocessingbatchjob/ChildLoanEventProcessingItemReader.java#L24), [filter file:60](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/childloaneventprocessingbatchjob/ChildLoanEventProcessingItemProcessor.java#L60)) | `loan_account_events_queue` | `event_status = 'P' AND is_deleted = false` — then **filters out** `EVENT_TYPE_IGNORE_API_MAP` ⇒ `[CLMT]` | Re-fires the child-event Request mapped via `EVENT_TYPE_ORC_API_MAP`. |
| **`ChildLoanEventsProcessingProcessor`** ([orchestration-time, file:41](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java#L41)) | `loan_account_events_queue` | (caller-supplied parent_account_id) — **same** `EVENT_TYPE_IGNORE_API_MAP` skip ⇒ `[CLMT]` | Same effect as the batch job, just driven from a parent-loan orchestration. |

### Coverage by `event_type` (`loan_account_events_queue`)

[`LoanAccountEventsQueueEntity.java:50-67`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java#L50-L67) defines the only two maps that govern queue processing:

```java
public static final List<String>        EVENT_TYPE_IGNORE_API_MAP = [ CLMT ];
public static final Map<String, String> EVENT_TYPE_ORC_API_MAP    = {
    FCL    → childLoanForeclosure,
    REP    → childLoanRepayment,
    WAIVER → childWaiveLoanAccountCharges,
    RSTCRE → childLoanRestructuring,
    REOPN  → childLoanReopening,
    TXNREV → childLoanTransactionReversal,
    PRTPRE → childLoanPartPrepayment,
    REBK   → childLoanRebooking,
    CANCL  → childLoanDisbursementCancellation,
    LEAR   → childLoanAccountExcessAmountRefund,
    CLB    → childLoanDisbursement
};
```

| `event_type` | What it represents | Scheduled recovery job? | Recovery API |
|---|---|---|---|
| `CLB`    | Child-loan disbursement post-bank booking trigger | `childLoanEventProcessingBatchJob` | `childLoanDisbursement` |
| `FCL`    | Child foreclosure                                | `childLoanEventProcessingBatchJob` | `childLoanForeclosure` |
| `REP`    | Child repayment                                  | `childLoanEventProcessingBatchJob` | `childLoanRepayment` |
| `WAIVER` | Child waiver                                     | `childLoanEventProcessingBatchJob` | `childWaiveLoanAccountCharges` |
| `RSTCRE` | Child restructuring                              | `childLoanEventProcessingBatchJob` | `childLoanRestructuring` |
| `REOPN`  | Child reopening                                  | `childLoanEventProcessingBatchJob` | `childLoanReopening` |
| `TXNREV` | Child transaction reversal                       | `childLoanEventProcessingBatchJob` | `childLoanTransactionReversal` |
| `PRTPRE` | Child part-prepayment                            | `childLoanEventProcessingBatchJob` | `childLoanPartPrepayment` |
| `REBK`   | Child rebooking                                  | `childLoanEventProcessingBatchJob` | `childLoanRebooking` |
| `CANCL`  | Child disbursement cancellation                  | `childLoanEventProcessingBatchJob` | `childLoanDisbursementCancellation` |
| `LEAR`   | Child excess-amount refund                       | `childLoanEventProcessingBatchJob` | `childLoanAccountExcessAmountRefund` |
| **`CLMT`** | **Child-leg bank-call staging row** (created during disburseLoan, owns the outbound NEFT/MFT lifecycle) | **NONE — explicit `EVENT_TYPE_IGNORE_API_MAP` skip** | n/a — only `disburseLoan` re-trigger |

### The CLMT gap — what it means in practice

CLMT rows are state for an **in-flight bank call** (their lifecycle: `DTFC_SUCCESS` → `NEFT_STAGE_1_PENDING` → `NEFT_STAGE_1_SUCCESS` → `NEFT_STAGE_2_PENDING` → `COMPLETED`, or → `*_FAIL`). They are **deliberately excluded** from `childLoanEventProcessingBatchJob` because mid-state CLMT rows describe a bank conversation only `disburseLoan`'s child-bank-call processors and the bank's async callback handler know how to advance — a generic queue-walker would risk re-firing bank calls.

Consequence: an orphan PENDING CLMT row (created by the new `a6fdc1c88` prep block, then orchestration aborts before the bank-call block fires) has **no automatic recovery**. The existing flow's only door is:

1. Operator (or upstream re-attempt) re-fires `disburseLoan` for the same parent.
2. `PerformChildLoanBankDisbursementProcessor` short-circuits to the lazy-create branch at [file:74-78](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/PerformChildLoanBankDisbursementProcessor.java#L74) — it **finds the existing CLMT row** and reuses it instead of inserting a new one.

This is documented in [`../platform/async-patterns.md`](../platform/async-patterns.md) under "Things that still don't have automatic recovery" and is the explicit safety story behind why `a6fdc1c88` (the structural CLMT-prep-block split) is safe even though no scheduled poller heals abandoned rows.

### What `accountingBankServiceRetryJob` actually does — debunking the "queue retry" myth

Despite its name, `accountingBankServiceRetryJob` does **not** scan the loan-event queue at all. It scans CRR (the outbound-HTTP audit table) for `status='FAIL'`, recovers the saved request body from `request_payload` + `uri`, and re-POSTs to the bank. This is useful for HTTP-layer transient failures (e.g. timeout while bank acknowledged), but it cannot resurrect a queue row that never reached the bank-call code path. The reverted `e8fef5c35` fix relied on this misreading and was rolled back in `2d9730818` for that reason.

### Cross-links

- Why CLMT rows can be orphaned at all: [`../platform/transaction-model.md`](../platform/transaction-model.md) (explicit `<Transaction>` block boundaries) and [`../platform/async-patterns.md`](../platform/async-patterns.md) (race matrix).
- The `a6fdc1c88` prep-block split that created the orphan-window in exchange for fixing the visibility race: see the 2026-05-05 entry in [`../changelog/CHANGELOG.md`](../changelog/CHANGELOG.md), or `git show a6fdc1c88`.
- Disbursement-engine treatment of these rows end-to-end: [`../engines/disbursement-engine.md`](../engines/disbursement-engine.md).
