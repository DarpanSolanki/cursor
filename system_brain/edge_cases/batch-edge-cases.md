# novopay-platform-batch — Edge Cases & Risk Scenarios (Wave 3)

**Date**: 2026-04-10  
**Scope:** Scheduler, `BatchScheduleService`, `SchedulerCommonService`, programmatic cron

## Already in `.cursor/gaps-and-risks.md` (table — do not duplicate)

- **Multi-node:** no distributed leader/lock — two instances can both pass `canStart` / start same group.  
- **In-memory dependency map:** `jobCompletionStatus` is JVM-local — dependency order not cluster-wide.

## Wave 3 additions (numbered gaps)

- **GAP-046** — `AutoScheduler` uses only `getAllTenants().get(0)` for startup `autoSchedule`.  
- **GAP-049** — Scheduler runnables set tenant `ThreadLocalContext` but do not clear it; pooled threads risk cross-tenant bleed.  
- **GAP-050** — `setCompletionStatus` marks dependency complete when job is already running, without correlating execution to current schedule.

## No `@Scheduled` in this module

- Scheduling uses `ThreadPoolTaskScheduler` + `GroupCronTrigger` with **DB** cron (`SchedulingGroupProcessor#schedule`). See `.cursor/scheduler-registry.md` section B.

## Spring Batch job definitions

- **novopay-platform-batch** is primarily a **scheduler/orchestrator**; Spring Batch job beans for accounting live in **novopay-platform-accounting-v2** and **novopay-platform-task**. Chunk/skip/restart semantics for money jobs are covered in accounting mining (`accounting-edge-cases.md`, GAP-031+).

## Reference

- `.cursor/multinode-batch.md` — multi-node branch behaviour, `force_*` flags, Kafka remote partitioning vs scheduler multi-instance.
