# Disbursement Consumer Skip Without LOS Sync Notification

## Scope
- Component: accounting Kafka consumer `LmsMessageBrokerConsumer`.
- Skip reasons: `LOCK_LOAN_STATUS`, `LOCK_CACHE_IN_PROGRESS`, `ALREADY_ACTIVE`.

## Verified behavior (2026-04-22)
- On skip:
  - `ALREADY_ACTIVE` sends success sync via `sendResultMessageToKafka(...)`.
  - `LOCK_LOAN_STATUS` and `LOCK_CACHE_IN_PROGRESS` return without publishing any LOS sync status.

## Why it matters
- LOS may not receive a terminal signal for skipped records and can appear stuck/in-progress.
- Ops RCA becomes harder because skip reason is visible in accounting logs but not reflected in LOS process state.

## Evidence file
- `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`

## Risk
- High (cross-service state divergence).

