<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.mdc only routes here. -->

## Batch platform: scheduler service ↔ accounting ↔ Spring Batch (framework, code-verified)

### Roles of each codebase
- **`trustt-platform-batch`** (separate microservice): owns **scheduling metadata** (batch groups, job definitions, schedules, execution status in the **batch service database**). It does **not** run LMS Spring Batch steps locally for accounting jobs.
- **`trustt-platform-accounting`**: hosts **orchestration `Request`s**, **`*BatchProcessor` entry beans**, and the **Spring Batch job definitions** under `batchnew/` (plus legacy `batch/` e.g. disbursement-cancellation insurance files).
- **`trustt-platform-lib/infra-batch`**: shared **Spring Batch framework** — job lifecycle, partitioning, bulk file helpers, optional multi-node Kafka workers.

### How a scheduled job reaches accounting
1. **`SchedulerCommonService.callJobAPi`** (and **`processSingleJob`** / **`DirectJobExecutor.startNormalJob`** for restart paths) calls  
   **`NovopayInternalAPIClient.callInternalAPI(executionContext, jobName, jobVersion, jobName, ...)`** — the **API/request name** passed to accounting is **`jobName`** (same string used twice in the call signature in code).
2. Before the call, the scheduler sets execution-context keys including:
   - **`function_sub_code` = `BATCH`** (so orchestration `<Control … value="BATCH">` routes to the batch processor),
   - **`op_code` = `START`** (or **`RESTART`** then later **`START`** in group restart flows — see `DirectGroupJobExecutor`),
   - **`job_time`** = business date as long via **`PlatformDateUtil.getBusinessDateInLong()`** after master-data cache eviction for **`current.business.date`** (`SchedulerCommonService.setJobTime`).

### How accounting runs Spring Batch (`infra-batch`)
- **`AbstractBatchJob.runJob(jobName, operationType, overrideParams)`** (code in `AbstractBatchJob.java`):
  - **`START`**: merges **`overrideParams`** into parameters loaded from the DB via **`BatchDBHandlerService.getAllParametersByJob(jobName)`**, adds `jobName` and `tenantCode`, applies **`force_grid_size` / `force_chunk`** overrides if present, then **`startJob(params)`** → publishes **`JobStartEvent`** (async Spring Batch launch).
  - **`RESTART` / `STOP`**: uses **`JobExplorer`** + **`JobRegistry`** to restart/stop the **same `jobName`** Spring Batch job.
- **`ParallelCommonBatchJob.setUpJobAdvanceV2`**: if job metadata has **`is_multi_node=TRUE`** and the active profile is **not** the default profile, sets up **`ParallelKafkaBatchJob`** (manager/worker); otherwise **`ParallelBatchJobV2`** (local **`TaskExecutorPartitionHandler`** partitioning). Comment in code: default/single-node uses **`ParallelBatchJobV2`**.
- **`ParallelBatchJobV2`**: builds partitioned steps; provides **`runBulkFileUploadJob`**, **`runInboundFileUploadJob`**, **`runBulkOutboundJob`** which load **`MasterFileUploadConfig`** / **`MasterOutboundConfig`** and field-validation metadata from the DB before `runJob`.

### Naming invariant (critical for tracing)
- In accounting `*BatchConfigService` classes, **`public static final String JOB_NAME`** is documented as **"same as api"**: it equals the orchestration **`Request name`**, the **Spring Batch job bean name**, and the **string the batch scheduler passes as `jobName`** to `callInternalAPI`.
- **Exception pattern**: some user-facing names differ slightly from internal job beans (always grep `JOB_NAME` + `deploy/application/orchestration` for the exact `Request name`).

### Orchestration batch vs non-batch branch
- Typical pattern in `loans_orc.xml` / `ServiceOrchestrationXML.xml` / `mfi_orc.xml`: **`<Control method="regExp" pattern="${function_sub_code}" condition="=" value="BATCH">`** runs **`*BatchProcessor`**; **`DEFAULT`** (or other codes) runs synchronous/setup processors. Scheduler-driven runs use **`BATCH`**.

### Where to tune performance (checklist)
- **DB-stored job parameters** for each `jobName` (grid size, chunk, `is_multi_node`, `force_grid_size`, etc.) — loaded by **`BatchDBHandlerService`**.
- **Partition SQL / readers** under `trustt-platform-accounting/.../batchnew/**/…ItemReader.java` and **failure row mappers** (chunk boundaries, min/max id queries).
- **Multi-node**: **`ParallelKafkaBatchJob`** path vs single-JVM **`ParallelBatchJobV2`** (throughput vs operational complexity).
- **Hot writers/processors** that call **`postTransaction`**, internal APIs, or external bank/file IO — profile per job in the sections below.

