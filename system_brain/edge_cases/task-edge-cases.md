# novopay-platform-task — Edge Cases & Risk Scenarios (Wave 3)

**Date**: 2026-04-10  
**Scope:** Task orchestration, embedded Spring Batch jobs, Kafka consumers (`collection_task_creation_`, `finnone_collection_task_creation_`, `task_user_tat_`), Finnone integration

## Cross-references (gaps)

- **GAP-047** — `TriggerNotificationsProcessor` swallows exceptions; escalation notifications may not fire.
- **GAP-048** — `RejectExpiredBatchJobItemWriter` hardcodes `user_id` `"2"` for auto-reject API calls.
- **GAP-051** — `FinnoneCollectionTaskCreationConsumer#processForCreatePtp` broken `task_id` condition.
- **GAP-052** — Finnone consumer logs full `ConsumerRecords` on error.
- **GAP-053** — `RejectExpiredTasksBatchJobConfig` uses `chunk = Integer.MAX_VALUE` in `getJobBeanConfigParameters`.

## Kafka / ordering

- Task producers (e.g. `TaskKafkaProducer`) inherit platform `NovopayKafkaProducer` behaviour (send failure swallow — GAP-019) and null-key patterns where applicable — verify per topic before replay.

## Batch jobs in this repo

- Reject expired, user TAT, notify pending tasks, meeting center notifications — cron strings live in `*BatchConfigService` classes; execution is driven by **novopay-platform-batch** scheduler invoking accounting/task services. See `.cursor/scheduler-registry.md` section C.

## Redis / cache

- Task caches actor/employee/office data (see service `CLAUDE.md`); stale cache can wrong assignment — not a new numbered gap in Wave 3.
