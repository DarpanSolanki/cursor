# novopay-platform-lib — Edge Cases & Risk Scenarios

**Date**: 2026-04-09  
**Scope**: platform framework libraries used by all services (navigation, message broker, http client, cache, transaction interfaces)

## Critical Paths (financial impact)
- Orchestration execution (`ServiceOrchestrator` → validators/processors → transaction boundaries)
- Kafka producer/consumer plumbing (event delivery for money flows)
- HTTP internal client usage (cross-service calls inside money flows)

---

## Edge Case: Async orchestration runs “fire-and-forget” with no durable outcome

- **Trigger**: Any ORC request marked async (`isAsync=true`) or any caller using `ServiceOrchestrator#processAsyncRequest`.
- **Current behavior**: Async execution starts via `CompletableFuture.runAsync(...)` and returns immediately; completion/failure is not returned to caller and is not persisted as an async job record.
- **Expected behavior**: Async runs must have a durable status record (PENDING/RUNNING/SUCCESS/FAILED), correlation ids, and deterministic retry/idempotency semantics.
- **Gap reference**: `GAP-020`
- **File**: `novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ServiceOrchestrator.java`

## Edge Case: Kafka send failures are swallowed by producer wrapper

- **Trigger**: Kafka broker outage, auth failure, serialization error, metadata timeout.
- **Current behavior**: Producer catches exceptions, logs, and returns without surfacing failure to caller; default callback logs error but does not propagate or persist.
- **Expected behavior**: Critical flows must either fail-fast (so orchestration can rollback/compensate) or persist to an outbox and retry until delivered (DLQ on poison).
- **Gap reference**: `GAP-019`
- **File**: `novopay-platform-lib/infra-message-broker/src/main/java/in/novopay/infra/message/broker/producer/NovopayKafkaProducer.java`

## Edge Case: Crypto helper returns empty/invalid outputs due to swallowed exceptions

- **Trigger**: Crypto algorithm mismatch, invalid key/iv, bad input encoding.
- **Current behavior**: Empty `catch` blocks in crypto helpers can return empty hash/token values; another method prints stack trace and continues.
- **Expected behavior**: Crypto failures must be fatal with explicit error codes; no downstream network/bank call should proceed with invalid crypto material.
- **Gap reference**: `GAP-018`
- **File**: `novopay-platform-lib/infra-transaction-interface/src/main/java/in/novopay/infra/util/EncryptionUtil.java`

