# Disbursement Sync Payload Missing `entity_type` And `stan`

## Scope
- Flow: LOS -> `disburse_loan_api_` -> Accounting -> `los_lms_disbursement_sync` -> LOS sync consumer.

## What was verified (2026-04-22)
- Accounting producer (`LmsMessageBrokerConsumer.sendResultMessageToKafka`) currently emits:
  - `external_ref_number`, `status`, `tenant_code`, `timestamp`, optional `error_code`/`error_message`.
- It does **not** emit `entity_type` and does **not** emit `stan`.
- LOS sync consumer (`DisbursementSyncService`) hard-requires `entity_type`; blank -> early return.

## Why it matters
- Failure sync events can be silently ignored by LOS (`entityType is null`), so process table `failure_reason` remains stale.
- Missing `stan` weakens async correlation between original LOS request and accounting sync-back.

## Evidence files
- `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`
- `novopay-mfi-los/src/main/java/in/novopay/los/service/disbursement/DisbursementSyncService.java`

## Current risk
- High for correctness (`entity_type` contract drift).
- Medium for observability (`stan` correlation drift).

