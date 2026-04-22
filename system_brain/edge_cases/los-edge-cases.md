# novopay-mfi-los — Edge Cases & Risk Scenarios (Wave 2)

**Date**: 2026-04-10  
**Scope**: Disburse → accounting async path, Redis in-flight, Kafka produce/consume, `DisbursementSyncService`

## Already documented elsewhere (do not duplicate as new gaps)

- **`entity_type` missing on sync** → LOS `DisbursementSyncService` can no-op; Accounting producer contract — see `.cursor/gaps-and-risks.md` table + runbooks “LOS disbursement sync” / “Accounting → LOS sync payload”.
- **Redis in-flight key no TTL** (`DisburseLoanAPIUtil`) — see table + runbook “Disbursement Redis in-flight key”.
- **Platform `NovopayKafkaProducer` swallows send failures** — LOS still returns success after `pushDataToKafkaQueue`; see GAP-019 / platform-lib mining.

---

## Edge: Null Kafka key on LOS disburse (and other) topics

- **Trigger**: Any `pushDataToKafkaQueue` call (e.g. `disburse_loan_api_` prefix).
- **Behavior**: Record key is always `null` → unstable partition for the same business id.
- **Risk**: Ordering/replay semantics; pairs with consumer idempotency and Redis lock patterns.
- **Gap**: GAP-038  
- **File**: `novopay-mfi-los/src/main/java/in/novopay/los/kafka/LosMessageKafkaProducer.java`

## Edge: Full sync payload logged at INFO

- **Trigger**: Every `los_lms_disbursement_sync` (or equivalent) record processed.
- **Behavior**: `DisbursementSyncConsumer` logs entire `clientMap` at INFO.
- **Risk**: PII / operational data in centralized logs.
- **Gap**: GAP-039  
- **File**: `novopay-mfi-los/src/main/java/in/novopay/los/kafka/DisbursementSyncConsumer.java`

## Edge: PostConstruct “wakeup” publishes `{}` to `disburse_loan_api_mfi_*`

- **Trigger**: Application startup (`LosMessageKafkaProducer#wakeupKafkaProducer`).
- **Behavior**: Sends dummy JSON to disburse-style topic with hardcoded tenant `mfi`, null key.
- **Risk**: Junk traffic on production topic, monitoring noise, wrong tenant assumption in multi-tenant ops.
- **Gap**: GAP-040  
- **File**: `novopay-mfi-los/src/main/java/in/novopay/los/kafka/LosMessageKafkaProducer.java`

## Edge: DEBUG logs full pipe-delimited disburse request

- **Trigger**: `DisburseLoanAPIUtil#callDisburseLoanAPI` with DEBUG enabled.
- **Behavior**: Logs `apiName|full_json|cacheKey`.
- **Risk**: Full disburse JSON in logs if DEBUG is on in an environment.
- **Gap**: GAP-041  
- **File**: `novopay-mfi-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java`

## Cross-links

- Orchestration entry: `novopay-mfi-los/deploy/application/orchestration/ServiceOrchestrationXML.xml` (and related deploy XML).
- Accounting consumer / sync contract: `system_brain/edge_cases/disbursement_sync_entity_type_missing.md` (if present), `.cursor/event-registry.md`.
