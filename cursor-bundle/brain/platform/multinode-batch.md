# Multi-node batch processing (branch `multinode_v3.2.8.2`) — reference

This document is a **branch analysis** of the multi-node batch framework work on branch `multinode_v3.2.8.2`.  
It is **not yet in production** but is expected to be, so this knowledge base documents it **now**.

## 1) What “multi-node” means in this branch

In `novopay-platform-batch`, “multi-node” is implemented as:

- **In-process parallelism**: jobs within a scheduled group can be executed concurrently using a thread pool (`CompletableFuture` over `Executors.newFixedThreadPool(50)`).
- **Multi-instance intent via shared DB checks**: code consults Spring Batch execution status (STARTING/STARTED) to decide whether a job can start.

What this branch does **not** implement (no evidence found in code):

- No explicit **node registration**, **node discovery**, or **node heartbeats**
- No explicit **leader election**
- No explicit **distributed lock** (Redis / DB row lock) guarding schedule/job start

## 2) Node lifecycle (as implemented)

### Startup

- `AutoScheduler.onLoadScheduleGroups()` triggers scheduling load on application startup:
  - `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/AutoScheduler.java`
  - Calls `TenantDetailsDAOService.getAllTenants()` and selects the **first** tenant as the “batch tenant”
  - Builds an `ExecutionContext` and calls `BatchScheduleService.autoSchedule(...)`

### Registration / discovery

- **None**: there is no persisted “node registry” table and no cache-based membership tracking in the code paths reviewed.

### Job pickup and execution

- Scheduled groups are scheduled via `SchedulingGroupProcessor.schedule(...)` from `BatchScheduleService.groupScheduleNovo(...)`.
- Actual job execution is triggered via `NovopayInternalAPIClient.callInternalAPI(...)` with `function_sub_code=BATCH` and `op_code=START/RESTART`:
  - `SchedulerCommonService.callJobAPi(...)`
  - `DirectJobExecutor.startNormalJob()` (restart path)
  - `DirectGroupJobExecutor.startGroupJob()` (group restart path)

### Completion

- `BatchScheduleService.updateExecutionCompletionState(...)` updates `batch_schedule` run metadata.
- `BatchScheduleService.getScheduleStatus(...)` reads Spring Batch execution records (or uses schedule metadata for special-case API jobs like `executePortfolioTransfer`).

### Failure and recovery

- “Unknown state” cleanup: `BatchScheduleService.fixUnknownStateJobs(...)` calls `jobService.fixUnknownJob(...)`.
- Restart on failure: `SchedulerCommonService.reTryForFailed(...)` calls:
  - `batchJobService.fixJobExecutionStatus(jobName)`
  - `batchJobService.setExecutionParams(...)`
  - internal API call with `op_code=RESTART`

## 3) Distribution and job dependency model

### Parallelization rule

- Jobs are assigned “priority” strings (hierarchical), e.g. `1`, `1.1`, `2.3.1`.
- Jobs are grouped by root priority (first number), and jobs with the same root priority are executed concurrently (one `CompletableFuture` per job).
- Child jobs wait for parent completion using `areDependenciesCompleted(jobPriority)` against an **in-memory** map:
  - `SchedulerCommonService.jobCompletionStatus` (`ConcurrentHashMap<String, Boolean>`)

### Cluster-wide implication

Because dependency tracking is in-memory:

- If multiple `novopay-platform-batch` instances run, the dependency graph is only enforced per JVM, not cluster-wide.

## 4) Infrastructure touch points

### Internal HTTP (platform-lib)

Batch uses `NovopayInternalAPIClient` to trigger jobs across services:

- `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java`
- `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/DirectJobExecutor.java`

This inherits the infra risk: **no retry/circuit breaker** (documented as High in `.cursor/gaps-and-risks.md`).

### Redis

Batch scheduler clears masterdata business date cache key before computing job time:

- `SchedulerCommonService.setJobTime(...)` removes `current.business.date` cache key from `RedisDBConfig.MASTER_DATA`

### Database

Coordination relies on Spring Batch execution tables (via `JobService`) and `batch_schedule` metadata:

- `BatchScheduleRepository` uses native SQL against `batch_schedule`

## 4A) Batch job parameters / flags (DB-driven)

These “batch job parameters” are persisted in the **batch DB** table `batch_job_parameter` (per job, by `job_id`) and are loaded at runtime to override step/job behavior.

### Where parameters are read and applied (code-backed)

- **DB → in-memory config map (`configParams`)**
  - `novopay-platform-lib/infra-batch/src/main/java/in/novopay/infra/batch/service/BulkMasterHelperService.java`
    - `updateForceParamByJob(jobName, configParams)` reads DB params for the job and copies any key starting with `force_` into `configParams`.
    - Special case: if `force_chunk` exists, it also sets `configParams["chunk"]`.
- **Setup-time routing: single-node vs manager/worker (remote partitioning)**
  - `novopay-platform-lib/infra-batch/src/main/java/in/novopay/infra/batch/builder/CustomCommonStepBuilder.java`
    - Reads `is_multi_node` from DB.
    - If default profile OR `is_multi_node != TRUE` → uses `CustomStepBuilder` (single-node, local).
    - Else → uses `CustomKafkaStepBuilder` (manager/worker via Kafka remote partitioning).
- **Job setup: default profile vs manager/worker profile**
  - `novopay-platform-lib/infra-batch/src/main/java/in/novopay/infra/batch/service/ParallelCommonBatchJob.java`
    - If default profile OR `is_multi_node != TRUE` → delegates to `ParallelBatchJobV2` (local partitioning).
    - Else → delegates to `ParallelKafkaBatchJob` (Kafka remote partitioning).
- **Runtime start override (chunk/grid sizing)**
  - `novopay-platform-lib/infra-batch/src/main/java/in/novopay/infra/batch/service/AbstractBatchJob.java`
    - `forceOverrideGridSize(params)` prefers `force_chunk` and `force_grid_size`.
    - If `force_grid_size` is absent, it may compute `grid_size` from `batch_count/chunk`.

### Flags and what they do (exact behavior)

- **`force_chunk`**
  - Overrides the **chunk size** (items per transaction) for chunk-oriented steps.
  - Applied by `BulkMasterHelperService.updateForceParamByJob()` (sets `configParams["chunk"]`) and by `AbstractBatchJob.forceOverrideGridSize()` (runtime param map).
- **`force_grid_size`**
  - Overrides the **partition grid size** (number of partitions) for partitioned steps.
  - Applied by `AbstractBatchJob.forceGridSize(...)` / `forceOverrideGridSize(...)`.
- **`force_async`**
  - Makes worker steps use `AsyncItemProcessor` + `AsyncItemWriter` (async item processing inside the worker).
  - Single-node path: `novopay-platform-lib/infra-batch/.../builder/CustomStepBuilder.java`
  - Remote-partitioning worker path: `novopay-platform-lib/infra-batch/.../builder/CustomKafkaStepBuilder.java`
- **`is_multi_node`**
  - Enables **manager/worker remote partitioning** (Kafka) for that job when non-default profiles are active.
  - Routing points: `CustomCommonStepBuilder`, `ParallelCommonBatchJob`.
  - Note: this is distinct from `novopay-platform-batch` scheduler multi-instance safety (which is a separate concern).
- **`force_msg_driven`** (Kafka worker consumption mode)
  - When TRUE, worker inbound flow uses `KafkaMessageDrivenChannelAdapter` with a listener container (message-driven).
  - When FALSE, worker inbound flow uses a poller-based inbound adapter.
  - Implemented in `CustomKafkaStepBuilder.inboundFlowWorkerMsg(...)` vs `inboundFlowWorker(...)`.
- **`force_ex_channel`** (Spring Integration channel type on worker inbound)
  - When TRUE, worker inbound channel is `ExecutorChannel(jobOperatorExecutor)` (async dispatch).
  - When FALSE, worker inbound channel is `DirectChannel()` (sync dispatch).
  - Implemented in `CustomKafkaStepBuilder.inboundFlowWorker(...)` / `inboundFlowWorkerMsg(...)`.
- **`force_consumer_async`** (poller-based worker consumer)
  - Only applies to the poller-based inbound flow (`inboundFlowWorker`).
  - When TRUE, the poller uses `.taskExecutor(kafkaTaskSchedulerExecutor)`.
  - Implemented in `CustomKafkaStepBuilder.inboundFlowWorker(...)`.
- **`force_task_executor`** (worker step execution)
  - When TRUE, calls `workerStepBuilder.taskExecutor(jobOperatorExecutor)` to parallelize step execution.
  - Implemented in `CustomKafkaStepBuilder.getWorkerStepBuilder(...)` and `getAsyncWorkerStepBuilder(...)`.

### Seed / ops scripts (where these flags are set)

- Workspace scripts that update/insert these params:
  - `update_batch_job_parameters_with_insert.sql`
  - `insert_force_async_for_loan_jobs.sql`
  - These scripts set (at least) `force_async`, `force_chunk`, `force_grid_size`, `is_multi_node`, `force_consumer_async`, `force_ex_channel`, `force_task_executor`, `force_msg_driven`.

## 5) Accounting integration impact

**Direct touch:** This branch’s multi-node behavior is in `novopay-platform-batch` and triggers jobs via internal APIs.  
Whether it “touches accounting” depends on which batch jobs/groups configured in `batch_group_job` invoke accounting-v2 requests (not exhaustively enumerated in this document because it’s config-driven).

**Key risk:** If multi-instance scheduling races, accounting jobs (interest accrual, posting, refund writers) can be triggered twice → money/state correctness risk.

## 6) Risk surface and new gaps (from this branch)

### Race across nodes (no distributed lock)

The current “canStart/isJobRunning” checks are not atomic across instances. Two schedulers can race:

- Node A reads “not running”
- Node B reads “not running”
- both call internal API start → duplicate job execution

### Dependency correctness across nodes

Dependency tracking is per-node (`jobCompletionStatus`), not persisted. In a multi-node deployment, ordering can be violated cluster-wide.

These gaps are recorded in `.cursor/gaps-and-risks.md` and have runbooks in `.cursor/runbooks.md`.

## 7) Production readiness checklist (multinode)

**Status:** NOT READY (as of this analysis)

Blocking must-haves before production:

- **Leader election or distributed lock** for schedule/job start (per schedule/group/job)
- **Atomic start** (compare-and-set RUNNING) persisted, not inferred by “is running”
- **Cluster-safe dependency tracking** (persisted DAG state or single leader)
- Clear idempotency posture for each job side-effect (DB writes, Kafka, file writes)

Suggested effort to reach readiness: **~1–2 weeks** depending on scope of jobs + QA.

