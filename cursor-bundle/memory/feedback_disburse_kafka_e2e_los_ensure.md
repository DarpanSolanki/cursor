# Disburse Kafka E2E setup is permanent (TDPQA-54) — 2026-07-21

## Root cause of recurring "LOS not ready"
`novopay-service-lib.sh` historically had **no `los` (or `simulators`) map entry**. Agents could not
`ensure los`; Kafka-path disburse kept failing as incomplete setup.

## Permanent fix
- Services: `accounting`, `los` (:8013 `/los`), `simulators` (:8018), `actor` (:8003),
  `masterdata` (:8014) in `novopay-service-lib.sh`.
- `agent-ops.sh before-test disburse*` → ensure accounting + los + actor + masterdata + simulators
  + fail-closed if consumer group `disburse_loan_api_consumer_mfi_local` has no active members.
- Kafka E2E: `bash scripts/bin/disburse-indl-kafka-quick.sh` (`--via-kafka`, column audit).
  Cache key entity_type must be `INDIVIDUAL`/`GROUP` (not product label INDL/JLG/SHG).
- HTTP quick scripts still valid for money path but **do not** prove ownerToken/Redis locks.
- Chain failure modes: actor down → 13009 getCustomerDetails; masterdata down → actor fails
  getBulkUniqueMasterData → same 13009.

## Deploy
Ship **accounting before/with LOS** for 4-segment Kafka message
(`apiName|json|cacheKey|ownerToken`).
