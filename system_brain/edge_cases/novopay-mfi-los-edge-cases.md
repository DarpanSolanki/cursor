# novopay-mfi-los — Edge Cases & Risk Scenarios

**Date**: 2026-04-09  
**Scope**: LOS origination + disbursement producer + sync consumers

## Critical Paths (financial impact)
- Disbursement producer → Kafka (`disburse_loan_api_`) → Accounting consumer orchestration
- Disbursement sync consumer (`los_lms_disbursement_sync`) → LOS DB updates (failure_reason/status)

---

## Edge Case: Disbursement request is logged as full payload (PII/financial payload leakage)

- **Trigger**: Any call to `DisburseLoanAPIUtil#callDisburseLoanAPI`
- **Current behavior**: Logs `apiName|<full request json>|<cacheKey>` at DEBUG.
- **Expected behavior**: Log only correlation ids (tenant, external_ref_number, cacheKey hash) and status.
- **Gap reference**: (covered under security lens; will be linked to a GAP when LOS security batch is written)
- **File**: `novopay-mfi-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java`

## Edge Case: Redis in-flight dedupe key has no TTL → stale key blocks replays indefinitely

- **Trigger**: JVM crash after key set; or exception paths that don’t remove key.
- **Current behavior**: Key is set without TTL in Redis DB index `ACCOUNTING`; subsequent calls skip as duplicate.
- **Expected behavior**: Set with TTL + token + safe cleanup.
- **Gap reference**: `GAP-003` (existing)
- **File**: `novopay-mfi-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java`

## Edge Case: Disbursement sync consumer logs full consumed map (PII leakage)

- **Trigger**: Any consumed sync message.
- **Current behavior**: Logs `clientMap` at INFO.
- **Expected behavior**: Log only minimal fields (external_ref_number, entity_type, status, error_code) and Kafka offset.
- **Gap reference**: (covered under security lens; will be linked to a GAP when LOS security batch is written)
- **File**: `novopay-mfi-los/src/main/java/in/novopay/los/kafka/DisbursementSyncConsumer.java`

## Edge Case: Missing `entity_type` causes LOS sync no-op (status not persisted)

- **Trigger**: Accounting publishes sync payload without `entity_type`.
- **Current behavior**: Service logs and returns early → LOS does not update failure_reason/status.
- **Expected behavior**: Consumer tolerates missing field (fallback) and persists status.
- **Gap reference**: `GAP-001` and `GAP-002` (existing)
- **File**: `novopay-mfi-los/src/main/java/in/novopay/los/service/disbursement/DisbursementSyncService.java`

