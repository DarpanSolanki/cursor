# `trustt-platform-batch` — Scheduler + bulk-upload registry

> **Not where business logic lives.** This service has 22 Requests of its own and one job: when a cron fires, call the orchestration `<Request name>` of *another* service (almost always accounting). The contract between batch and accounting is the **Request name string** — see [`../accounting/03-batch-dependency.md`](../accounting/03-batch-dependency.md) for the full inventory.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.batch` |
| DB schema | `mfi_batch` |
| Repo | [`trustt-platform-batch/`](../../trustt-platform-batch/) |
| Service CLAUDE.md | [`(CLAUDE.md removed — use service README / AGENTS.md)`](../../(CLAUDE.md removed — use service README / AGENTS.md)) |

## API surface — 22 Requests across two concerns

**Scheduling registry:**
- `createOrUpdateBatchSchedule`, `getBatchScheduleList`, `getBatchScheduleDetails`, `deleteBatchSchedule`
- `createOrUpdateBatchGroup`, `getBatchGroupList`, `getBatchGroupDetails`, `deleteBatchGroup`
- `createOrUpdateBatchJob`, `getBatchJobList`, `getBatchJobDetails`, `deleteBatchJob`
- `getBatchJobStatus`, `getBatchJobStatusByRefNo`, `getBatchJobLastInstance`

**Bulk uploads:**
- `bulkUploadBatch`, `viewBulkBatchUploadFileStatus`, `downloadBatchUploadedFile`, `getBulkBatchUploadTemplate`, `getAllBulkBatchUploadTypes`, `updateFileUpload`, `bulkBatchSubmitApplication`

No Kafka. No Spring Batch jobs *of its own*.

## Three core tables

| Table | Entity | Purpose |
|---|---|---|
| `batch_job` | `BatchJob` | Registry: `name` = orchestration Request name, `version`, `code`, `status` (ACTIVE/INACTIVE), `job_instance_id` (Spring Batch FK) |
| `batch_schedule` | `BatchSchedule` | Cron schedule: `cron_expression`, `last_run_on`, `next_run_on`, `last_completion_status`, `group_id`, `is_scheduled` |
| `batch_group` | `BatchGroup` + `batch_group_job` | Logical job grouping; jobs ordered by hierarchical priority string (e.g. `"1.2.3"`) |
| `file_upload` | `FileUpload` | Bulk upload staging row |
| `master_file_type_config` | `MasterFileTypeConfig` | Per-upload-type config: format, regex, max records, size, header rows, delimiter, folder path |
| `process_outbound_detail` | `ProcessOutboundDetail` | Outbound file audit trail |

> Spring Batch meta-tables (`BATCH_JOB_INSTANCE`, `BATCH_JOB_EXECUTION`, `BATCH_STEP_EXECUTION`) live in the **target service's** datasource (typically accounting). The batch service polls those over HTTP / DB to get job status.

## Scheduler internals

### `AutoScheduler`
- `@PostConstruct` `onLoadScheduleGroups()` — fetches all tenants, picks the **first**, calls `BatchScheduleService.autoSchedule(context)`. Loads `BatchSchedule` rows with `isScheduled=true`.
- File: [`AutoScheduler.java:30-44`](../../trustt-platform-batch/src/main/java/in/novopay/batch/core/service/AutoScheduler.java#L30-L44)

### `SchedulingGroupProcessor`
- Spring `ThreadPoolTaskScheduler`, **fixed 50 threads** ([SchedulingGroupProcessor.java:53](../../trustt-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulingGroupProcessor.java#L53)).
- `schedule(...)` registers a `ScheduleBatchGroupExecutor` (Runnable) on a `GroupCronTrigger`.
- `cancelGroupSchedule(scheduleId)` cancels via `ScheduledFuture`.

### `ScheduleBatchGroupExecutor.run()`
- Calls `BatchScheduleService.canStart(scheduleId)` — non-atomic check against Spring Batch metadata (`status IN STARTING/STARTED`).
- If true, sets schedule status `RUNNING`, spawns job threads.
- File: [`ScheduleBatchGroupExecutor.java:61-89`](../../trustt-platform-batch/src/main/java/in/novopay/batch/core/service/ScheduleBatchGroupExecutor.java#L61-L89)

### `DirectJobExecutor` — the actual call site
```java
novopayInternalAPIClient.callInternalAPI(
    executionContext, job.getName(), job.getVersion(),
    job.getName(), connTimeout, sockTimeout, true);
```
Forces `function_sub_code = "BATCH"` and `op_code = "RESTART"`.

### Job dependency tracking (in-process, NOT cluster-safe)
- `SchedulerCommonService.jobCompletionStatus` is a `ConcurrentHashMap<String, Boolean>` ([line 59](../../trustt-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java#L59)).
- Hierarchical priority parsed (`"1.2.3"` → root `1`, parent `1.2`, this `1.2.3`).
- `areDependenciesCompleted(priority)` checks the map — pure in-memory.
- **Multi-instance race**: two scheduler instances both read "not running" and both trigger the same job. Documented HIGH RISK in [`../platform/multinode-batch.md`](../platform/multinode-batch.md).

## Bulk upload flow — end-to-end

```
User uploads file via webapp / android
  ▼
gateway → bulkUploadBatch
  ▼
BulkUploadBatchProcessor.process()
  ├── validate upload_type
  ├── load MasterFileTypeConfig (per type)
  ├── FileUploadService.addFileDetails()  →  INSERT file_upload (status=BULK_STATUS_PENDING)
  └── compute: apiName = "bulkFileToSG" + convertToBulkJobType(uploadType) + "Job"
        e.g. uploadType=LOAN_CREATION → bulkFileToSGLoanCreationJob
  ▼
callInternalAPI(apiName, ...)  →  accounting (or LOS)
  ▼
Accounting job reads file_upload_id from ExecutionContext, processes the file
  ▼
FileUploadService.updateStatus()  →  file_upload.status = COMPLETED | FAILED
```

Status read-back: `viewBulkBatchUploadFileStatus` calls `apiName = "viewBulk" + type + "FileStatus"` on the target service; results merged with batch DB metadata.

Download: `downloadBatchUploadedFile` calls `apiName = "download" + type + "UploadedFile"`.

## Job-status feedback — how batch knows the job finished

After `callInternalAPI(jobName, ...)`, `SchedulerCommonService.waitTillJobFinish(jobName)` polls `isJobRunning(jobName)` every 2 s for up to ~1 min (30 attempts × 2 s):
- `isJobRunning` → reads target service Spring Batch tables (`status IN STARTING/STARTED`).
- `isJobFailed` → checks `status IN FAILED/ABANDONED/UNKNOWN`.
- `getScheduleStatus(scheduleId)` aggregates per-job statuses → returns `COMPLETED/FAILED/RUNNING/NOT_STARTED`.

**No async callbacks.** Pull-only. Special case: `executePortfolioTransfer` returns immediately, no polling.

## Known gotchas

1. **Job-name typos are silent** — accounting Request renamed but `batch_job.name` not updated → 404 on next fire, only logged by `DirectJobExecutor`.
2. **Fixed 50-thread pool** — heavy concurrent jobs starve.
3. **Multi-node race** documented in [`../platform/multinode-batch.md`](../platform/multinode-batch.md). No leader election.
4. **In-process dependency tracking** — restarts lose `jobCompletionStatus`; downstream jobs may fire too early.
5. **`AutoScheduler` picks first tenant only on startup** — multi-tenant clusters need explicit per-tenant init.
6. **Forces `function_sub_code = BATCH` and `op_code = RESTART`** — orchestration validators in target services must allow these.
7. **Spring Batch meta-tables in accounting schema, registry in `mfi_batch`** — don't confuse them when writing migration/audit queries.

## When you'll touch this service

- Adding a new scheduled job → it is **registered by the OWNING service at startup**, NOT hand-inserted here: wire the job's `BatchConfigService.buildJobForTenant()` into that service's `*JobLoader` + add a `BatchJobPlaceholderConfig` stub bean + an `api_master` row + a matching `<Request>`. `buildJobForTenant` auto-seeds the `batch_job`/`batch_group`/`batch_schedule` rows (with the cron); this service's `AutoScheduler` arms them on restart. Full chain + silent-fail modes: [system-activation-and-wiring §1](../platform/system-activation-and-wiring.md). (A manual `batch_job` insert is ad-hoc/legacy only.)
- Onboarding a new bulk upload type → insert `master_file_type_config` row + create the `bulkFileToSG<Type>Job` and `bulkSGTo<Type>Job` Requests in the target service.
- Investigating "EOD didn't run" → see [`../runbooks/eod-failed.md`](../runbooks/eod-failed.md).
