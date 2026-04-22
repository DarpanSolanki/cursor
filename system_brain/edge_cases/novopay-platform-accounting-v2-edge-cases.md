# novopay-platform-accounting-v2 — Edge Cases & Risk Scenarios

**Date**: 2026-04-09  
**Scope**: Accounting core (loan lifecycle, posting engine entrypoints, Kafka consumer disbursement path, batch jobs)

## Critical Paths (financial impact)
- Disbursement (Kafka consumer + orchestration) + LOS sync publish
- `postTransaction` ledger persistence (client_reference_number dedupe)
- Interest accrual posting (batch)
- Loan closure / auto-closure (batch)

---

## Edge Case: Kafka disbursement consumer lock key has no TTL → stuck replays

- **Trigger**: Consumer crash/hang after lock key is set in Redis and before `finally` cleanup.
- **Current behavior**: Lock existence causes “skip in progress” behavior; without TTL it can block forever.
- **Expected behavior**: Lock keys must have TTL + token-based ownership; stale keys must self-heal.
- **Gap reference**: `GAP-004` (existing) and reinforced by ongoing scan context
- **File**: `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`

## Edge Case: Result publish to LOS can fail silently (event dropped)

- **Trigger**: Kafka publish failure while sending `los_lms_disbursement_sync`.
- **Current behavior**: Failure is caught and logged; caller proceeds, so LOS may never see final status.
- **Expected behavior**: Fail-fast or outbox + retry; DLQ for permanent failures.
- **Gap reference**: `GAP-??` (captured as part of this scan in accounting-v2 evidence; to be numbered in next GAP batch)
- **File**: `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`

## Edge Case: Time-based `client_reference_number` in batches defeats dedupe on replay

- **Trigger**: Batch rerun/retry after partial progress (interest accrual, billing, asset criteria, DCF, refunds).
- **Current behavior**: New `client_reference_number` generated on each run; `ClientReferenceNumberDedupProcessor` cannot detect business-duplicate postings.
- **Expected behavior**: Deterministic idempotency key derived from business tuple (account_id + date + txn_type + run id).
- **Gap reference**: `GAP-016`, `GAP-017`, `GAP-018/019` class of issues
- **File**: `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/interest/interestaccrualbooking/InterestAccrualBookingBatchService.java` (and other batch writers)

## Edge Case: Batch writers swallow exceptions → “successful” job with missing/partial state changes

- **Trigger**: Exceptions during batch writer persist/update.
- **Current behavior**: Some writers catch and log (or debug-log) and continue, allowing the step/job to appear successful.
- **Expected behavior**: Fail the step/chunk; mark per-record failure state; provide retry/DLQ semantics.
- **Gap reference**: `GAP-018`, `GAP-020`
- **File**: `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/refund/proactiveexcessamountrefund/ProactiveExcessAmountRefundItemWriter.java`, `.../loanaccountclosure/LoanAccountAutoClosureItemWriter.java`

