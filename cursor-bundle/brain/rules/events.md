---
description: Kafka/events hygiene, consumer patterns, idempotency, disbursement sync contract
globs:
  - "**/MessageBroker*.xml"
  - "**/*Consumer*.java"
  - "**/*Producer*.java"
  - "**/*KafkaConfig*.java"
  - "**/*MessageBroker*.java"
alwaysApply: false
---

# Events & Kafka — Active Intelligence

## Before any edit

1. Check `.cursor/event-registry.md` — topic prefix, producer, consumer, config
2. Avoid **orphan** topics (produce with no consumer) unless explicitly documented as external
3. Review consumer **catch** paths: swallow + silent commit vs typed errors / DLQ

## Rules that are non-negotiable for production hygiene

- New financial/async topic: **consumer** and **failure posture** defined in the same change set when possible
- Consumer: distinguish validation/business (no blind retry) vs transient (retry)
- Publish paths: handle or propagate failure; do not assume fire-and-forget is safe for money state
- Update `.cursor/event-registry.md` **before** closing a task that adds/changes topics or payloads

## After any event change

Update `.cursor/event-registry.md` with (minimum):

- Topic / prefix
- Producer class + method (or config id)
- Consumer class + method
- Payload key fields (code-evidenced)
- Error handling Y/N + risk flag

Also append `.cursor/changelog.md` when behaviour or contract changes.

---

# Kafka consumer patterns (merged)

## Consumer structure

```java
public class XxxConsumer implements NovopayMessageBrokerConsumer {

    @Override
    public void consumeMessage(String message, String topic, String tenant) {
        try {
            ThreadLocalContext.setTenant(new PlatformTenant(tenant));

            // 1. Parse message
            // 2. Idempotency check (skip if already processed)
            // 3. Build ExecutionContext
            // 4. Process (orchestration or direct service call)
            // 5. Publish result if needed

        } catch (CannotAcquireLockException e) {
            throw e; // Rethrow for retry — transient failure
        } catch (NovopayFatalException e) {
            log.error("Fatal error processing message: {}", e.getErrorCode(), e);
            // Publish to failure topic if needed
        } catch (Exception e) {
            log.error("Unexpected error processing message from topic {}: {}", topic, e.getMessage(), e);
            // Publish to failure/DLQ topic
        } finally {
            // Clean up: remove cache locks, clear thread-local
        }
    }
}
```

## Idempotency (non-negotiable)

Kafka delivers at-least-once. Consumers MUST handle duplicates:

```java
// Check status before processing
LoanAccountEntity account = daoService.findByExternalRef(externalRef);
if (account != null && "ACTIVE".equals(account.getStatus())) {
    log.info("Loan {} already ACTIVE, skipping", externalRef);
    return;
}

// Use Redis lock for in-flight dedup
String cacheKey = "disbursement:" + externalRef;
if (redisTemplate.hasKey(cacheKey)) {
    log.info("Disbursement for {} already in flight, skipping", externalRef);
    return;
}
redisTemplate.opsForValue().set(cacheKey, "processing", Duration.ofMinutes(10));
```

Why: The `LmsMessageBrokerConsumer` incident showed that without idempotency, duplicate Kafka messages trigger 3x NEFT calls for the same loan.

## Partition key strategy

Use meaningful partition keys so messages for the same entity hit the same partition (preserving order):

- Loan operations: partition by `external_ref_number` or `account_number`
- Collection operations: partition by `challan_number`

## Error classification in consumers

| Error type | Action |
|-----------|--------|
| `CannotAcquireLockException` | Rethrow — Kafka retries |
| `NovopayFatalException` | Log + publish to failure topic |
| Validation failure | Log + skip (don't retry invalid data) |
| Unexpected exception | Log + publish to DLQ |

## Message format

Typical format: `apiName|requestBody|cacheKey` (pipe-separated) or JSON object.

Always validate message format before parsing — corrupt messages should not crash the consumer.

## Full orchestration vs direct service call

- **Full orchestration** (`ServiceOrchestrator.executeProcessors()`): When the consumer triggers a complete business flow with validators, multiple processors, controls.
- **Direct service call**: When the consumer does a single focused operation (e.g. status sync, data update).

Choose based on whether the operation needs the full orchestration pipeline or is a simple targeted update.

## DisburseLoan / LMS disbursement sync contract (code-verified)
This is a money-movement/idempotency pattern; use it when debugging disbursement replays and “no update” sync behavior.

- Producer side (`DisburseLoanAPIUtil#callDisburseLoanAPI`) sends Kafka message:
  - `disburseLoan|<request_json>|<cacheKey>`
  - where `<cacheKey> = "disburseLoan" + <product_id_defaultString> + "_" + <external_ref_number_defaultString>`
  - and it writes a Redis marker: `novopayCacheClient.set(tenant, cacheKey, "in_progress", RedisDBConfig.ACCOUNTING)` with **no TTL**.
- Accounting consumer side (`LmsMessageBrokerConsumer`) expects the message cacheKey as the **last** pipe segment:
  - `originalCacheKey = <cacheKey>`
  - processing lock key = `dl + originalCacheKey`
  - it skips when `novopayCacheClient.get(tenant, "dl"+originalCacheKey, ACCOUNTING) != null`
  - it sets the lock to `"true"` and always removes both `originalCacheKey` and `"dl"+originalCacheKey` in `finally`.
- Accounting consumer publishes result to `los_lms_disbursement_sync` with payload keys:
  - `external_ref_number`, `status`, `error_code`, `error_message`, `tenant_code`, `timestamp`
  - it does **not** include `entity_type`.
- LOS sync handler (`DisbursementSyncService#handleDisbursementSyncRecord`) requires `entity_type`:
  - if `entity_type` is blank/missing it logs `entityType is null` and returns early (no DB update).
