# Edge Case: `entity_type` missing/blank in disbursement sync payload

## Symptom
Disbursement sync consumer runs, but `DisburseLoanProcessEntity` failure reason is not updated.

## Code-verified root constraint (truth-audited 2026-07-23)

1. `in.novopay.accounting.consumers.LmsMessageBrokerConsumer#sendResultMessageToKafka(...)`
   - publishes to topic prefix `los_lms_disbursement_sync`
   - payload keys include `external_ref_number`, **`entity_type`**, `status`, `error_code`, `error_message`, `tenant_code`, `timestamp`
   - **FIXED:** key is present (`payload.put("entity_type", …)` ~L311 on current train)
   - **Residual:** value can still be `""` when Kafka message key does not yield `entityType` (parse path ~L102)
2. `in.novopay.los.service.disbursement.DisbursementSyncService#handleDisbursementSyncRecord(...)`
   - reads `entity_type` from ExecutionContext (`executionContext.getStringValue(ENTITY_TYPE)`)
   - if blank/missing: logs `entityType is null` and returns early (no DB update) — **STILL-OPEN**

## Operational guidance (for debugging)
- Inspect the consumed Kafka record to confirm whether `entity_type` is present **and non-blank**.
- Key-present-but-empty behaves like missing for LOS (early return by design).

## Confidence
- High: producer now emits the key; consumer still requires non-blank value (code-verified on watermark train).

## Gap linkage
- LOS blank no-op: High row in `.cursor/gaps-and-risks.md`
- Accounting missing-key claim: **RESOLVED** 2026-07-23 truth audit (was REOPENED 2026-04-22)
