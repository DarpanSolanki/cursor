# novopay-platform-payments — Edge Cases & Risk Scenarios (Wave 2)

**Date**: 2026-04-10  
**Scope**: Bulk collection Kafka consumer, field collections persistence + notifications, allocation/task producers, `bulk_collection_data` pipeline

**See also**: `system_brain/edge_cases/novopay-platform-payments-edge-cases.md` (DMS, settlement ORC idempotency notes, async `runAsync`).

---

## Edge: Null Kafka key on all `PaymentsKafkaProducer` topics

- **Trigger**: `pushDataToKafkaQueue` for `collection_primary_allocation_*`, `collection_secondary_allocation_*`, `collection_task_processing_*`, etc.
- **Behavior**: `sendMessage(..., null, message, null)` — no stable entity key.
- **Risk**: Partition churn; harder ordering guarantees under retry.
- **Gap**: GAP-042  
- **File**: `novopay-platform-payments/src/main/java/in/novopay/payments/common/util/PaymentsKafkaProducer.java`

## Edge: Bulk consumer success/failure log maps never populated (outer scope)

- **Trigger**: `CreateOrUpdateBulkCollectionConsumer#computeRecords` INFO summary lines.
- **Behavior**: Outer `failedRecords` / `successCollectionRefs` are not the same instances filled inside `processCollectionData` → INFO counts often **always zero** even when inner processing failed/succeeded.
- **Risk**: False “all green” operations view; delayed incident detection.
- **Gap**: GAP-043  
- **File**: `novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java`

## Edge: JSON parse failure → null payload → silent skip

- **Trigger**: Malformed `bulk_collection_data` (or equivalent) message body.
- **Behavior**: `parseData` catches, logs error, returns `null`; processing skipped without DLQ in this method.
- **Risk**: Lost collection intent if offset commits (data drift vs LMS/accounting expectations).
- **Gap**: GAP-044  
- **File**: `novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java`

## Edge: SMS / leader notification swallowed after collection save

- **Trigger**: Field collection path completes `saveAll` then runs notifications.
- **Behavior**: `try/catch` logs “Suppressing execption” and continues — DB state committed, comms may never run.
- **Risk**: Customer/leader inconsistency (money recorded, no alert). Not the same as double-charge; pairs with support load.
- **Gap**: GAP-045  
- **File**: `novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/repository/MfiCollectionsDAOService.java`

## NEFT stage-2 context gate

- **Note**: Medium gap documented in **accounting** (`novopay-platform-accounting-v2`) orchestration/processors — payments module scan did not add a duplicate; see `.cursor/gaps-and-risks.md` and accounting edge cases.

## Double-payment on retry

- **Note**: `callPushLMSUpdateAPI` and similar paths use retries with `SYNC_FAILED` / retrigger patterns — full idempotency proof is per-API contract with accounting/LMS; no separate High gap opened in Wave 2 beyond consumer/producer ordering and parse-loss (GAP-044). Re-verify before replaying `collectionLoanRepayment` after failures.

## Orchestration XML (this service)

- `deploy/application/orchestration/orc_mfi.xml`, `orc_mfi_cross_schema.xml`, `orc_collections.xml`, `product_accounting.xml` — reconcile / interbank processors: confirm bean names exist before changing flows (`reconcileCollectionPayments` chain).
