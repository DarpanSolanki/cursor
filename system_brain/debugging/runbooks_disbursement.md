# Debugging Runbook: Disbursement Replay + Sync

This runbook is restricted to the code-verified Kafka/Redis/sync mechanics.

## A) Replay causes duplicate disbursement orchestration (symptom)
1. Confirm which Redis marker is set:
   - LOS producer sets `<cacheKey>` with value `"in_progress"` (no TTL).
   - Accounting consumer checks and locks `"dl" + <originalCacheKey>`.
2. If the consumer processes despite duplicates, inspect:
   - whether `dl+originalCacheKey` exists when the second consumer record starts
   - whether cleanup is reached (consumer cleanup happens in `finally`)
3. Confirm loan-level skip gates:
   - consumer skips when loan is `ACTIVE` and `disbursement_status == COMPLETED`
   - consumer skips when `loan_status == LOCK`

## B) Disbursement sync does not update failure reason (symptom)
1. Verify the payload reaching `DisbursementSyncService` contains `entity_type`.
2. Code behavior:
   - if `entity_type` is blank/missing, the service returns early and does not update DB.
3. In this path, the accounting producer’s published payload omits `entity_type`:
   - `LmsMessageBrokerConsumer` sends `los_lms_disbursement_sync` without `entity_type`.

## C) Skip/no-op in accounting but LOS never receives terminal sync
1. In `LmsMessageBrokerConsumer.processConsumerRecord`, check skip reason:
   - `ALREADY_ACTIVE` -> sync is published.
   - `LOCK_LOAN_STATUS` or `LOCK_CACHE_IN_PROGRESS` -> no sync publish.
2. Symptom:
   - LOS process appears stuck/in-progress with no failure reason update.
3. Triage:
   - confirm skip reason in accounting logs,
   - verify absence/presence of `los_lms_disbursement_sync` event for the same external ref.

## D) Malformed Kafka envelope causes pre-guard failure
1. Consumer assumes payload format `apiName|requestBody|cacheKey` and parses before `try/finally`.
2. If separator shape is broken:
   - parsing can throw before normal result publication and lock-flow behavior.
3. Immediate mitigation:
   - quarantine poison records,
   - re-publish only well-formed envelope payloads.

## E) NEFT callback succeeds but UTR not saved
1. In NEFT callback processor array branch, UTR map key is built with `referenceno`.
2. Later lookup uses external reference (`paymentrefno`), so lookup can return null.
3. Symptom:
   - callback success logs present,
   - stage moved, but UTR not persisted on loan/queue rows.

## Confidence
- High for mechanics above; extend by inspecting the ORC/DB writer steps when needed.

