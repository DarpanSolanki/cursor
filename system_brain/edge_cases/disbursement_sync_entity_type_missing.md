# Edge Case: `entity_type` missing in disbursement sync payload

## Symptom
Disbursement sync consumer runs, but `DisburseLoanProcessEntity` failure reason is not updated.

## Code-verified root constraint
1. `in.novopay.accounting.consumers.LmsMessageBrokerConsumer#sendResultMessageToKafka(...)`
   - publishes to topic prefix `los_lms_disbursement_sync`
   - payload keys include `external_ref_number`, `status`, `error_code`, `error_message`, `tenant_code`, `timestamp`
   - it does NOT include `entity_type`
2. `in.novopay.los.service.disbursement.DisbursementSyncService#handleDisbursementSyncRecord(...)`
   - reads `entity_type` from ExecutionContext (`executionContext.getStringValue(ENTITY_TYPE)`)
   - if blank/missing: logs `entityType is null` and returns early (no DB update)

## Operational guidance (for debugging)
- Inspect the consumed Kafka record (or add temporary logging) to confirm whether `entity_type` exists in the payload reaching `DisbursementSyncConsumer`.
- If `entity_type` is absent, the service will no-op by design (not a DB issue).

## Confidence
- High: both the producer payload keys and the consumer requirement are code-verified.

