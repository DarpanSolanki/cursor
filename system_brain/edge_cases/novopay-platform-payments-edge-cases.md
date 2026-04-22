# novopay-platform-payments — Edge Cases & Risk Scenarios

**Date**: 2026-04-09  
**Scope**: collections, settlements, Finnone integrations, Kafka allocation/task pipeline

## Critical Paths (financial impact)
- Collections settlement + reconciliation (`reconcileCollectionPayments` → interbank transfer leg)
- Collections → accounting repayment updates
- Finnone inbound/outbound file jobs (collection state sync)

---

## Edge Case: DMS download uses raw HttpClient with no timeouts and throws blank error codes

- **Trigger**: DMS slowness/outage during document fetch.
- **Current behavior**: Uses `HttpClients.createDefault()` with no explicit timeouts and throws `NovopayFatalException("", "")`.
- **Expected behavior**: Proper timeouts + meaningful error codes; avoid unbounded waits and avoid blank error codes.
- **Gap reference**: (will be linked to GAP when payments lens batch is written)
- **File**: `novopay-platform-payments/src/main/java/in/novopay/payments/util/DmsUtil.java`

## Edge Case: Kafka publishes use `null` key → per-entity ordering not guaranteed

- **Trigger**: Producing events for collection/task pipelines without a stable key.
- **Current behavior**: `sendMessage(..., null, message, ...)` → partitioning is random.
- **Expected behavior**: Use stable partition key (collection_id / external_reference_id) to preserve ordering for entity-scoped processing.
- **Gap reference**: (will be linked to GAP when payments lens batch is written)
- **File**: `novopay-platform-payments/src/main/java/in/novopay/payments/common/util/PaymentsKafkaProducer.java`

## Edge Case: Settlement flow triggers interbank transfer in orchestration chain without explicit persisted idempotency marker

- **Trigger**: Replay/retry of `reconcileCollectionPayments`.
- **Current behavior**: ORC chains `doCollectionReconcileProcessor` → `doInterBankTransferForCollectionProcessor` (risk of double-initiation unless processor enforces idempotency).
- **Expected behavior**: Persist and check “transfer initiated/UTR present” flag before any second initiation.
- **Gap reference**: (to be materialized during deeper processor scan)
- **File**: `novopay-platform-payments/deploy/application/orchestration/orc_collections.xml`

## Edge Case: Async runAsync usage in DAO services can lose error signal and saturate common pool

- **Trigger**: High volume processing paths invoking `CompletableFuture.runAsync`.
- **Current behavior**: Multiple `runAsync` call sites exist (e.g., in DAO services); if using common pool, saturation can cause delays and silent failures.
- **Expected behavior**: Use bounded executor + completion/error tracking + correlation ids.
- **Gap reference**: (to be linked when payments async lens batch is written)
- **File**: `novopay-platform-payments/src/main/java/in/novopay/payments/collections/repository/CollectionsDAOService.java`

