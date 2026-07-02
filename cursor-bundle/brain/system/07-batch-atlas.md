# 07 · Batch atlas — every scheduled job in the platform

> Single page covering every batch job across services. Owned by [`novopay-platform-batch`](../services/novopay-platform-batch.md). For full details on the batch ↔ accounting contract, read [`../accounting/03-batch-dependency.md`](../accounting/03-batch-dependency.md). For per-service job inventories, see the per-service brain doc.
>
> **Rule:** `BatchJob.name` in `mfi_batch.batch_job` MUST equal `<Request name="…">` in the target service. A renamed Request without a registry update silently 404s.

## How to read this atlas

- "Trigger" = how the job fires. Almost always: cron in `mfi_batch.batch_schedule` → `DirectJobExecutor` → HTTP to target service Request.
- "Owns" = the service whose orchestration XML defines the Request and runs the Spring Batch job.
- "Output" = side-effects on tables / GL / files / Kafka / external systems.
- "Depends on" = upstream data the job reads.

## Daily — the EOD/BOD core (accounting)

> ⚠ **Important — `runEODJobs` is NOT an aggregator of every EOD job.** Verified on 3.3.1.0.1 by reading [`MfiRunEODJobsProcessor.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/custom/mfi/jobs/processor/MfiRunEODJobsProcessor.java) (~L23–L28): the orchestration only invokes **5 child Requests** sequentially via `novopayInternalAPIClient.callInternalAPI(...)`. **Billing, interest accrual + posting, derived-fields refresh, trial balance, and the post-EOD report job all run on their own independent cron schedules**, not from `runEODJobs`. This was previously documented as one big aggregator — the corrected layout is below.

### `runBODJobs` (BOD aggregator, ~04:00 IST)

| Job (Request) | Owner | Output |
|---|---|---|
| Server clock advance | accounting | `business_date` updated |
| Holiday roll-forward | accounting | calendar adjustments |
| `generateEnachPresentationFile` | accounting | `enach_presentation_*` rows + outbound file |
| `expirePendingMandatesBatchJob` | accounting | mandate state transitions |
| Day-counter resets | accounting | counters in derived fields |

### `runEODJobs` (the 5-step DPD → NPA → penal pipeline, ~21:00 IST)

Sequential, fail-forward. First failure aborts subsequent steps in this orchestration.

| Order | Job (Request) | Owner | Output | Depends on |
|---:|---|---|---|---|
| 1 | `loanAccountDpdCalcJob` | accounting | `loan_account.past_due_days` | due-details rows |
| 2 | `loanAccountAssetCriteriaJob` | accounting | `loan_account.asset_criteria_slabs_id` | DPD + asset_criteria_slabs |
| 3 | `loanAccountAssetClassificationJob` | accounting | `loan_account_derived_fields.asset_classification` (+ NPA-tier-change GL post) | criteria slab → classification map |
| 4 | `penalInterestAccrualCalculation` | accounting | `penal_interest_accrual_details` UPSERT | DPD + penal slabs |
| 5 | `penalInterestAccrualBooking` | accounting | GL hits via `postTransaction` (DR PENAL_INT_RECEIVABLE / CR PENAL_INT_INCOME) | step 4 rows |

### Other "EOD-time" jobs (independent cron schedules — NOT in `runEODJobs`)

These run on standalone `mfi_batch.batch_schedule` rows. There is **no enforced ordering** between them and `runEODJobs` — coordination happens via clock time.

| Job (Request) | Default cron | Output | Notes |
|---|---|---|---|
| `loanAccountBillingJob` | ~`0 0 18 * * ?` | `loan_account_billing_details` | If billing fires before accrual on a given day, it bills with stale interest data — known timing variance. |
| `interestAccrualCalculation` | ~`0 0 18 * * ?` | `interest_accrual_details` UPSERT | Idempotent on (loan_id, accrual_date). |
| `interestAccrualPosting` | separate | GL hits (DR INT_RECEIVABLE / CR INT_INCOME) | **Re-running same day = double-posting.** No `(loan_id, effective_date, function_code)` unique constraint. |
| `updateLoanAccountDerivedFieldsJob` | ~`0 0 19 * * ?` | denorm refresh | |
| `trialBalanceCalculation` | ~`0 0 20 * * ?` | `trial_balance` daily snapshot | |
| `trialBalanceZeroisationJob` | ~`0 0 21 * * ?` | closing → next-day open | |
| `generateTBZeroisationReport` | ~`0 0 21 * * ?` | report file | |
| `extractCasaBalanceFor180/182ProductCode` | configured | extract files | |
| `generatePostEODReports` | ~`0 0 22 * * ?` | dispatches to reporting service | |
| `updateLoanAccountDerivedFieldsMonthlyJob` | `0 0 0 1 * ?` (monthly) | monthly denorm refresh | |

**Operational implications:**
1. "EOD didn't run" can mean any one of: `runEODJobs` (DPD→NPA pipeline) failed, OR billing failed, OR accrual failed, OR posting failed, OR TB calc/zeroisation failed. Each is a separate cron — check `mfi_batch.batch_schedule.last_completion_status` per job.
2. If `runEODJobs` fails at 21:00, billing was already done at 18:00 with yesterday's DPD/asset state — **no automatic re-billing**.
3. No distributed lock protects `runEODJobs` orchestration; if two batch-service nodes fire simultaneously, both call the 5 child jobs (chunk-tracking prevents double-processing within one JVM, NOT across pods). See [`../platform/multinode-batch.md`](../platform/multinode-batch.md).

## Loan servicing (accounting, scheduled separately)

| Request | Frequency | Output |
|---|---|---|
| `loanAccountClosure` | configured | Auto-close FORECLOSED → CLOSED for loans missed by inline auto-closure |
| `loanAdvanceRepayment` | configured | Apply standing payments to next due |
| `loanRecurringPaymentBatchApi` | configured | Recurring debit |
| `rescheduleLoanAccountRescheduleBatch` | configured | Apply pending reschedule events |
| `registerLoanAccountRescheduleEvent` | configured | Record reschedule trigger |
| `updateCollectionBatchDetails` | configured | Sync collection batch state |
| `updateLoanAccountDerivedFieldsMonthlyJob` | monthly | Monthly denorm refresh |

## SHG/JLG fan-out (accounting)

| Request | Frequency | Output |
|---|---|---|
| `childLoanEventProcessingBatchJob` | every few minutes | Drains `loan_account_events_queue` (status='P') and dispatches to per-event-type Request. See [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md) |

## Bulk-upload pairs (accounting)

Pattern: `bulkFileToSG…Job` ingests file → staging; `bulkSGTo…Job` applies staging → core.

| Pair | Domain |
|---|---|
| `bulkFileToSGFinsallRepaymentJob` / `bulkSGToFinsallRepaymentJob` | Finsall repayment file |
| `bulkFileToSGManualJournalEntriesJob` / `bulkSGToManualJournalEntriesJob` | Manual JE bulk |
| `bulkFileToSGForeclosureChargeUpdateJob` / `bulkSGToForeclosureChargeUpdateJob` | Foreclosure charge bulk |
| `bulkFileToSGNocBlockUnblockJob` / `bulkSGToNocBlockUnblockJob` | NOC block/unblock |
| `bulkFileToSGDispatchDetailsJob` / `bulkSGToDispatchDetailsJob` | Dispatch details |
| `bulkFileToSGSecNpaReverseFeedFileJob` / `bulkSGToSecNpaReverseFeedFileJob` / `bulkOutboundSecNpaReverseFeedFileJob` | Secondary-NPA reverse-feed |
| `bulkFileToSGManualHoldRemovalJob` | Manual-hold removal (file-only) |
| `bulkFileToSGTransactionReversalJob` | Bulk txn reversal |
| `bulkFileToSGAssetCriteriaGroupUpdateJob` | Asset-criteria group update |
| `bulkSGToDisbursementCancellationJob` | Disbursement cancellation |
| `bulkSGToPostDisbursementInsuranceUpdateJob` | Post-disbursement insurance update |
| `bulkSGToRefundMarkingJob` | Refund marking |

## NOC / dispatch / extracts (accounting)

`generateNocFileJob`, `extractCasaBalanceFor180ProductCode`, `extractCasaBalanceFor182ProductCode`, `accountingBankServiceRetryJob`, `doGenericSyncSTPBankNEFNeftCallBack`, `doGenericSyncSTPBankNEINeftCallBack`.

## Insurance (accounting, per provider)

Outbound + inbound + run-trigger triplets per provider:

```
outboundDeathForeclosureInsuranceJob          inboundDeathForeclosureInsuranceJob          runInboundDeathForeclosureInsuranceJob
outboundDisbursementBajajErgoHealthInsuranceJob   inboundDisbursementBajajErgoHealthInsuranceJob   runInboundDisbursementBajajErgoHealthInsuranceJob
outboundDisbursementHdfcLifeLifeInsuranceJob     inboundDisbursementHdfcLifeLifeInsuranceJob     runInboundDisbursementHdfcLifeLifeInsuranceJob
outboundDisbursementHdfcErgoHealthInsuranceJob   inboundDisbursementHdfcErgoHealthInsuranceJob   runInboundDisbursementHdfcErgoHealthInsuranceJob
outboundDisbursementCancellation* (×3 providers) / inboundDisbursementCancellation* (×3) / runInboundDisbursementCancellation* (×3)
```

## Payments (LCS) ~48 jobs

`bulkFileToSG…Job` / `bulkSGTo…Job` pairs for: confirm payment, dynamic one/two, excel agency, finnone loan correction, finone reverse, loan category upload, loan exception upload, np handoff, np rev trails, priority calendar, reschedule data upload, static dt type.

Outbound / sync to vendors: `bulkOutboundNpAgencyExtractJob`, `bulkOutboundNpCollReportJob`, `bulkOutboundNpHandOffFileJob`, `bulkOutboundNpRacCasesJob`, `bulkOutboundNpReverseHandoffJob`, `bulkOutboundNpTrialHistoryJob`, `collToStagNpAgentSyncJob`, `collToStagNpCollReportSyncJob`, `collToStagNpHandOffFileSyncJob`, `collToStagNpRacCasesSyncJob`, `collToStagNpTrialHistorySyncJob`.

Finnone inbound: `runInboundFinoneJob`, `runInboundStaticFinoneJob`, `runFinoneReverseJob`, `runInboundNpHandoffJob`, `runInboundNpRevTrailsJob`.

Reminders: `reminderForPtpCalenderCustomerJob`, `reminderForPtpCalenderUserJob` (+ `Rm`), `collectNowGenerateReceiptNotificationJob` (+ `RM`, `CH`).

Cash deposit: `cashDepositCutoffTimeElapsedForCollectorJob`.

## LOS bulk uploads

`bulkFileToSGSalesPromocodeJob` / `bulkSGToSalesPromocodeJob`, `bulkFileToSGShgCodeJob` / `bulkSGToShgCodeJob`, `bulkFileToSGIrrJob`, `bulkFileToSGReKycDetailsJob`, `bulkFileToSGRiskProfileJob`, `amlRiskProfileFile`. Plus CKYC and rejected/success data jobs.

## Task

`notifyUsersForPendingTasksJob` (TAT reminders), `rejectExpiredBatchJob`, `calculateUserTatBatch`.

## Reporting

`generateRBIAdfBankDetailsExtractJob`, `generateUAMPopulationExtractJob`, `spanSoJob`, plus 60+ other report-specific jobs (each has its own Request `generate*Job` in the reporting service's `ServiceOrchestrationXML.xml`).

## Where the canonical schedule lives

`mfi_batch.batch_schedule` — per row: `cron_expression`, `last_run_on`, `next_run_on`, `last_completion_status`. The batch service's `AutoScheduler` loads these on startup.

`mfi_batch.batch_job` — registry: `name = <orchestration Request name>`, `version`, `code`, `status`.

`mfi_batch.batch_group` + `batch_group_job` — sequencing by hierarchical priority string (e.g. `"1.2.3"`).

## What every job execution looks like

```
cron fires
  → AutoScheduler picks up
    → ScheduleBatchGroupExecutor.run()
      → canStart() check (Spring Batch metadata)
        → DirectJobExecutor.startNormalJob()
          → NovopayInternalAPIClient.callInternalAPI(executionContext, jobName, version, ...)
            → gateway routes to target service
              → ServiceOrchestrator.executeProcessors(...) for that <Request>
                → Spring Batch Job/Step/Reader/Processor/Writer
                  → batch_failure_audit (per-row failures)
        → waitTillJobFinish (poll Spring Batch meta every 2s, up to 30 attempts)
```

Multinode race risk documented in [`../platform/multinode-batch.md`](../platform/multinode-batch.md).

## When you'll touch this

- Adding a new job → the `batch_job`/`batch_schedule` rows are **auto-seeded by the owning service at startup** (`buildJobForTenant`), not hand-inserted: wire the `BatchConfigService` into a `*JobLoader` + `BatchJobPlaceholderConfig` bean + `api_master` row + `<Request>`. Chain + silent-fail modes: [system-activation-and-wiring §1](../platform/system-activation-and-wiring.md).
- Investigating "EOD didn't run" → see [`../runbooks/eod-failed.md`](../runbooks/eod-failed.md).
- Investigating "stuck child events" (SHG/JLG) → check `loan_account_events_queue` and `childLoanEventProcessingBatchJob` last run.
