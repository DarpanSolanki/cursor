# Rule Improvements Applied (this session)

## 1) `.cursor/rules/events.mdc` (Kafka consumer patterns section)
Added a code-verified disbursement money-movement contract section:
- exact `disburseLoan|<request_json>|<cacheKey>` message format
- producer Redis marker (no TTL) on `<cacheKey>`
- accounting consumer lock key prefixing with `dl + <originalCacheKey>`
- `los_lms_disbursement_sync` result payload keys and the fact it omits `entity_type`
- `DisbursementSyncService` hard requirement on `entity_type` (blank/missing => early return / no DB update)

## 2) `.cursor/rules/api-contract-safety.mdc`
Explicitly broadened “what counts as a contract” to include:
- Kafka/async payload mandatory fields treated as mandatory keys by downstream services

## 3) `.cursor/rules/accounting.mdc` (Module reference)
Updated the `createTransactionDetailsProcessor` knowledge bullet with the exact debit/credit sign mapping:
- `netAmount > 0` => `CrDrIndicator.C`
- `netAmount < 0` => `CrDrIndicator.D`
- `netAmount == 0` => skip row creation
