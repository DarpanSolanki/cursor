# Runbook — Replaying a Kafka or HTTP callback safely

## When you'd do this

- A Kafka message was lost or never consumed (e.g. disbursement result, bureau callback).
- A bank / Razorpay / eMandate / eSign callback hit gateway but failed processing.
- An external vendor file landed but wasn't ingested.

## Idempotency layers (read first)

The platform has three idempotency layers. Understand which one applies before you replay anything.

| Layer | Where | What it dedups |
|---|---|---|
| Gateway STAN | `mfi_api_gateway.request_stan_log` | Per-call STAN; rejects exact-same STAN within window |
| Audit replay | `mfi_audit.response_log` | `getApiResponseByStan` returns prior response, allowing safe retry |
| Posting dedup | `mfi_accounting.transaction_master.client_reference_number` | Rejects duplicate transaction headers |

If you replay with the **same** STAN / client_reference_number, the system should reject the duplicate. If you replay with a **new** STAN, you risk double-posting.

## Decision tree

### A. Replay a disbursement Kafka event (LOS → accounting)

1. Confirm: the original message did not get consumed (check accounting log; check `loan_account` doesn't exist for the `external_ref_number`).
2. Check Redis ACCOUNTING DB 5 for stale `dl<…>` keys — clear them ([`disbursement-stuck.md`](disbursement-stuck.md) §A.3).
3. Re-publish the **exact original message** to `disburse_loan_api_<tenant>` (same key + value).
4. Watch accounting log for `LmsMessageBrokerConsumer` pickup.
5. If `getDisburseSkipReason` returns `ALREADY_ACTIVE`, the loan exists and the previous attempt actually succeeded — no replay needed.

### B. Replay a result event (accounting → LOS)

1. Confirm: LOS-side `disburse_loan_process` shows pending; accounting actually completed.
2. Re-publish to `los_lms_disbursement_sync` with the same payload as the original.
3. LOS `disbursementSyncConsumer` is idempotent on the `external_ref_number` — safe to replay.

### C. Replay a bank NEFT callback

1. Locate the original callback payload in `mfi_api_gateway.CallbackRequestResponseLog`.
2. Re-POST to the gateway callback endpoint (`doGenericSyncSTPBankNEFNeftCallBack` or `…NEINeftCallBack`).
3. The accounting state machine progresses to the next stage based on `function_sub_code`.

### D. Replay a Razorpay / Easebuzz / eMandate / eSign callback

1. Locate the callback in gateway's callback log.
2. Re-invoke the corresponding callback controller.
3. These are **not idempotent at the application layer** in all cases — verify the downstream Request handles "already processed" gracefully (e.g. `updatePaymentStatus` typically does).

### E. Replay a Kafka topic message that was lost

If a topic message was lost (broker issue, manual deletion):
1. Identify the producer side — does it still have the source data?
2. Re-publish from the source. The framework appends to topic; consumer offset advances normally.
3. **Don't shift consumer offsets backwards** unless you're certain the consumer is idempotent end-to-end. Replay = re-execute side effects.

### F. Re-ingest a vendor file (Finsall / Finnone / VYMO / NPA reverse-feed)

1. Check the staging table (`file_staging_*`) — is the row present?
2. If present with status `PENDING` / `FAILED`, re-trigger the corresponding `bulkSGTo…Job`.
3. If staging row missing, re-upload the file via the bulk-upload Request.

## Safe replay checklist

Before replaying any event:

- [ ] I know whether the original processed successfully (prevents double-post).
- [ ] I know which idempotency layer protects me (STAN, client_ref, audit replay).
- [ ] I have the **original payload** (not a re-constructed one).
- [ ] I know the consumer/handler is idempotent on the relevant key.
- [ ] I have a way to verify post-replay success (DB row, log line, downstream side-effect).

## Code anchors

- Gateway dedup: [`novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/`](../../novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/)
- Audit replay: `getApiResponseByStan` Request in audit
- Accounting txn dedup: `clientReferenceNumberDedupProcessor` in [`novopay-platform-accounting-v2`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/processor/ClientReferenceNumberDedupProcessor.java)

## Related

- Disbursement stuck: [`disbursement-stuck.md`](disbursement-stuck.md)
- Kafka topology: [`../system/08-kafka-topology.md`](../system/08-kafka-topology.md)
- Kafka consumer lag: [`kafka-consumer-lag.md`](kafka-consumer-lag.md)
