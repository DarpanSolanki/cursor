# Runbook — Kafka consumer lag

## Symptoms

- Disbursement result not reaching LOS (lag on `los_lms_disbursement_sync`).
- Bulk collection rows piling up on `bulk_collection_data_*`.
- Bureau response missing on LOS (lag on `indl_qde_*` or `jlgdl_*`).
- Audit data missing in DB / ES (lag on `api_gateway_*` / `audit_*` topics).
- Notification not delivered (lag on `notification_*`).

## Confirm the lag (out-of-band)

```bash
# From any kafka client / management tool:
kafka-consumer-groups.sh --bootstrap-server <broker> --describe --all-groups
# Look for high LAG values
```

## Decision tree by topic

### A. `los_lms_disbursement_sync` lagged → LOS doesn't see disbursement results

Consumer: `disbursementSyncConsumer` in LOS (3 threads, critical path).

1. Is the LOS service alive / healthy?
2. Is the consumer thread CPU-saturated or DB-blocked? Check thread dump.
3. Is downstream `disburse_loan_process` UPDATE slow? Check DB lock / index health.
4. If consumer crashed, restart LOS. Offsets are broker-managed — it'll resume.
5. If lag is too large to drain in time, scale by increasing the LOS consumer thread count (config) and restart.

### B. `bulk_collection_data_*` lagged → payments not ingesting bulk rows

Consumer: `createOrUpdateBulkCollectionConsumer` in payments (poll 1500 ms, high pri).

1. Is payments service alive?
2. Is `mfi_payments` DB latency high?
3. Bulk-collection logic is per-row INSERT/UPDATE; check for slow query on collection tables.

### C. LOS bureau topics lagged

Consumers: `factivaConsumer`, `posidexConsumer`, `posidexSecondCallConsumer`, `multiBureauConsumer`, `internalDedupeConsumer` etc.

Each is per-stage / per-loan-type / per-retry. Heavy lag here means loan applications stall in the eligibility stage. Most issues are external (provider API down) — the consumer keeps retrying via the `_retry_` topic. Check provider health.

### D. `api_gateway_*` topics lagged → audit DB / ES behind

Consumer: audit service.

1. ES cluster health.
2. Audit DB write latency.
3. `getApiResponseByStan` will return "not found" for recent calls — gateway dedup may incorrectly accept retries. Reduce client retry rate temporarily.

### E. `notification_*` topics lagged → notifications not sent

Consumer: notifications service.

1. Notifications service alive?
2. SMS / email / FCM provider connectivity?
3. Check notifications app log for adapter errors (e.g. Vodafone XML POST timeout).

## What this platform doesn't have

- **No DLQ topology.** Failed records are caught + logged + retried in-process. There is no dead-letter topic to inspect.
- **No automatic offset reset.** Offsets are broker-managed at consumer-group level.

## General recovery

1. Identify the topic + consumer group with high lag.
2. Identify the consumer's owning service.
3. Check that service's app log for ERRORs around the lag window.
4. Restart the service if consumer thread is stuck.
5. If the lag is from an external dependency (provider down), wait + monitor — retries will catch up.

## When in doubt

- Use the per-service brain doc to identify which consumer owns which topic prefix.
- Cross-link: [`../system/08-kafka-topology.md`](../system/08-kafka-topology.md) for the full topology.

## Code anchors

- Consumer interface: `NovopayMessageBrokerConsumer` (in `infra-kafka` lib)
- Per-service `MessageBroker.xml` declares topic ↔ bean mapping
