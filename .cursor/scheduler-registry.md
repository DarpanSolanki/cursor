# Scheduler registry — Waves 1–4 services

**Scope:** `novopay-platform-lib`, `novopay-platform-accounting-v2`, `novopay-mfi-los`, `novopay-platform-payments`, `novopay-platform-task`, `novopay-platform-actor`, `novopay-platform-batch`, `novopay-platform-api-gateway` (Java `src/main/java`, 2026-04-10 scan).

**Legend — Lock Y/N:** `Y` only if an explicit distributed lock / DB advisory lock / leader election guards the runnable. `N` does not mean “safe on multi-instance” — see `.cursor/gaps-and-risks.md` (batch multi-node rows) and `.cursor/multinode-batch.md`.

---

## A) `@Scheduled` methods (Spring annotation)

| Service | Class | Method | Cron / schedule | Lock | Risk |
|--------|--------|--------|-----------------|------|------|
| novopay-platform-lib | `NovopayApiClientConfig` | `httpConnectionMonitor.run` (anonymous `Runnable` bean) | `fixedDelay = 15000` ms | N | **Low** — idle connection eviction / stats; ensure `@EnableScheduling` active for this config bean only where intended. |
| novopay-platform-accounting-v2 | — | — | *No `@Scheduled` found* | — | — |
| novopay-mfi-los | — | — | *No `@Scheduled` found* | — | — |
| novopay-platform-payments | — | — | *No `@Scheduled` found* | — | — |
| novopay-platform-task | — | — | *No `@Scheduled` found* | — | — |
| novopay-platform-actor | — | — | *No `@Scheduled` found* | — | — |
| novopay-platform-batch | — | — | *No `@Scheduled` found* | — | — |
| novopay-platform-api-gateway | `FilterConfig` | `sessionPurge` | `${novopay.service.gateway.session.cleanup.cron}` (Spring **cron** expression) | N | **Medium** — purges expired sessions per tenant via `sessionDAOService.invalidateExpiredSessions`; ensure cron not duplicated unsafely on multi-instance (DB is source of truth for expiry; verify idempotency). |

*Discovery:* `@Scheduled` also on `novopay-platform-api-gateway/.../FilterConfig.java` (`sessionPurge`).

---

## B) Programmatic schedulers — batch service (`ThreadPoolTaskScheduler` + DB cron)

Cron expressions live on `batch_schedule.cron_expression` (and related APIs), not as `@Scheduled` constants.

| Service | Class | Method | Cron / schedule | Lock | Risk |
|--------|--------|--------|-----------------|------|------|
| novopay-platform-batch | `SchedulingGroupProcessor` | `schedule(BatchSchedule, jobs, cronExpression)` | **DB** `batch_schedule.cron_expression` | N | **High** — multi-instance race / duplicate triggers; see gaps table + `multinode-batch.md`. |
| novopay-platform-batch | `AutoScheduler` | `onLoadScheduleGroups` (`@PostConstruct`) | **Once** at startup (loads all schedules for **first tenant only** — GAP-046) | N | **High** — other tenants may miss bootstrap. |
| novopay-platform-batch | `ScheduleBatchGroupExecutor` | `run` | Invoked on each cron tick from (B) | N | **High** — `ThreadLocalContext` leak risk (GAP-049). |
| novopay-platform-batch | `SchedulerCommonService` | `processJobs` | Drives parallel job starts per tick | N | **High** — in-memory dependency map cluster-wide; fixed thread pool 50. |

---

## C) Job metadata `cron_expression` (task service — seeded into batch platform / LMS groups)

These are **not** Spring `@Scheduled` in task; they are strings in job setup maps (actual execution is triggered when **batch** service runs the registered job).

| Service | Class | Method / constant | `cron_expression` value | Lock | Risk |
|--------|--------|-------------------|-------------------------|------|------|
| novopay-platform-task | `RejectExpiredTasksBatchJobConfig` | `JOB_NAME = rejectExpiredBatchJob` | `0 0 18 * * ?` | N | EOD expiry — pairs with GAP-053 chunk config. |
| novopay-platform-task | `CalculateUserTatBatchConfigService` | user TAT job | `0 0 0/3 ? * *` | N | Every 3 hours. |
| novopay-platform-task | `NotifyUsersForPendingTasksJobBatchConfigService` | pending notifications | `0 15 * * * ?` | N | At :15 each hour. |
| novopay-platform-task | `NotificationsConfigService` | `triggerNotifications` | `0 0/15 * * * *` | N | Every 15 minutes. |
| novopay-platform-task | `SendMeetingCenterPendingNotiBatchConfigService` | meeting center pending | `0 0 10 * * ?` | N | Daily 10:00. |

---

## D) Maintenance

When adding `@Scheduled` or new DB cron jobs in these services, update this file and `.cursor/gaps-and-risks.md` if multi-instance or tenant safety changes.

**Wave 4 note:** `/forward/*` is **outside** `/api/*` servlet filter registrations — see `GAP-055` (not a scheduler issue; document here for ingress/security reviews).
