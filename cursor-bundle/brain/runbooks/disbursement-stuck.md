# Runbook — Disbursement stuck

## Symptoms

- LOS sent the disburse trigger; accounting log shows `LmsMessageBrokerConsumer` received but no progression.
- Loan exists in `loan_account` but `loan_status = APPROVED` for hours.
- Or no `loan_account` row at all.
- LOS-side `disburse_loan_process` shows status pending; `disbursementSyncConsumer` not receiving result.

## First SQL

```sql
SELECT a.account_number, la.loan_status, la.disbursement_status,
       la.created_on, la.updated_on, la.external_ref_number
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE a.account_number = ? OR la.external_ref_number = ?;

-- Bank retry queue
SELECT * FROM mfi_accounting.bank_service_call_retry
 WHERE loan_account_id = ? ORDER BY id DESC LIMIT 5;

-- Disbursement transaction history
SELECT * FROM mfi_accounting.loan_disbursement_transaction
 WHERE loan_account_id = ? ORDER BY id DESC;
```

## Decision tree

### A. No `loan_account` row at all

The consumer was skipped at `getDisburseSkipReason`. Three sub-cases:

1. **`ALREADY_ACTIVE`** — duplicate event for an already-completed loan. Verify, then ignore (no action).
2. **`LOCK_LOAN_STATUS`** — loan in `LOCK` status (rare; transient cache). Wait or check Redis.
3. **`LOCK_CACHE_IN_PROGRESS`** — `dl<…>` Redis key exists from a previous attempt that crashed before cleanup. **This is the recurring gap** ([`../gaps-and-risks.md`](../gaps-and-risks.md)).

   **Fix:** delete the stale key from Redis ACCOUNTING DB (5):
   ```
   redis-cli -n 5 KEYS "*disburseLoan{productId}_{externalRefNumber}*"
   redis-cli -n 5 DEL <stale-key>
   redis-cli -n 5 DEL dl<stale-key>
   ```
   Then replay the Kafka message (re-publish to `disburse_loan_api_<tenant>`).

### B. `loan_status = APPROVED`, `disbursement_status` pending bank stage

Stages indicating bank-leg in flight: `LOAN_BOOKED`, `NEFT_STAGE_1_PENDING`, `NEFT_STAGE_1_SUCCESS`, `NEFT_STAGE_2_PENDING`, `REINITIATE_BANK`.

Cross-check the disburseLoan state machine in [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md) §3.

1. Check `bank_service_call_retry` for the latest row → if it's been retrying without success, the bank is the issue.
2. Check `accountingBankServiceRetryJob` last run time in `mfi_batch.batch_schedule WHERE name = 'accountingBankServiceRetryJob'`.
3. Verify the bank's NEFT API health (out-of-band).
4. If bank is healthy and the retry job is scheduled, manually re-fire `accountingBankServiceRetryJob` from the batch service.

#### B.1 — NEFT inquiry returned NDF / "batch not found" (3.3.1.0.1+)

**Symptom:** stuck at `NEFT_STAGE_1_PENDING`. Latest `client_request_response_log` row for `transaction_type=DISBURSEMENT_NEFT_NEF` shows `status=FAIL`, `response` contains `"errorCode":"NDF"` or `"errorDesc":"Batch details not found..."`.

**Root cause (closed `1671a0fad`, 2026-05-07):** bank's NEFT v2 inquiry endpoint returns NDF when the batch ID has not yet been created on bank-side, or the prior NEFT call failed before the bank produced a batch. Pre-fix, the loan stayed pinned at `NEFT_STAGE_1_PENDING` because `rankBackwardSafeFromStates` is forward-only — there was no rollback path.

**Current behaviour (3.3.1.0.1):**
- `CallBankAPIForDisbursementProcessor.saveBankErrorResponseCode` (parent) and `ChildDisbursementLoanEventsQueueSync.saveBankErrorResponseCode` (child) detect NDF / "batch not found" via `isBankBatchNotFoundResponse` (raw-response sniff).
- On detection: backward CAS `NEFT_STAGE_1_PENDING → DTFC_SUCCESS` (race-safe — REJECTED if a callback advanced state in parallel), then `IS_BANK_CALL_FAILED=TRUE` so the child disbursement aborts cleanly.
- The next `disburseLoan` retry (manually re-fired or via `accountingBankServiceRetryJob`) enters at `function_sub_code=DTFC_SUCCESS` and fires a fresh NEF call.

**Action:** if you see this signature, no manual data patch needed — re-fire `disburseLoan` for the LAN. The state machine handles the rollback.

**Verify:**
```sql
SELECT id, status, response, created_on
  FROM mfi_accounting.client_request_response_log
 WHERE loan_account_number = ?
   AND transaction_type LIKE 'DISBURSEMENT_NEFT_%'
 ORDER BY id DESC LIMIT 5;
```
If you see a successful `DTFC_SUCCESS → NEFT_STAGE_1_SUCCESS` transition after a prior NDF FAIL, the rollback worked and the loan progressed.

#### B.2 — Stuck CLMT row (CAS reverted by Hibernate auto-flush)

**Symptom (pre-`4c339282f`):** child loan_account_events_queue row stuck at `NEFT_STAGE_2_PENDING` with `data.external_error_message = "NEI Initiated…"` (sync-handler signature) instead of `"Under Process at Bank"` (async signature) or terminal `COMPLETED`. `updated_on` is the orchestration's commit-time timestamp, not the latest callback's.

**Root cause:** the post-CAS in-memory mutation pattern caused Hibernate auto-flush at outer-tx commit to revert the row to its load-time `updated_on` and overwrite the async-callback CAS.

**Closed on 3.3.1.0.1** by commits `4c339282f` and `09295c377` — CAS is now the sole writer; advisory writes go through `ChildClmtStateMachineService.patchJsonFields`. **No action needed for new disbursements on 3.3.1.0.1+.** Stuck rows from prior versions: re-fire `disburseLoan` and the prep-block split + populate-before-prepare fix will recreate clean CLMT rows.

### C. `loan_status = APPROVED`, `disbursement_status = COMPLETED`

This shouldn't be possible in a clean run — the two progress in lock-step. Indicates partial commit. Look at the latest `audit_log` entry for the loan; manual operator intervention required.

### D. `loan_status = ACTIVE`, no result event reached LOS

The `sendResultMessageToKafka` failed in the consumer's `finally` block, or the topic message was lost.

1. Check accounting app log for `sendResultMessageToKafka` exceptions.
2. Check `los_lms_disbursement_sync` topic for the message (with the correct tenant suffix).
3. If no message: re-publish manually with payload:
   ```json
   { "external_ref_number": "...", "status": "SUCCESS",
     "tenant_code": "...", "timestamp": ... }
   ```
4. If message present but LOS not consuming: see [`kafka-consumer-lag.md`](kafka-consumer-lag.md).

### E. Maker-checker pending

If `maker_checker_enabled=1` for `disburseLoan`, the loan stays in `APPROVED` until the checker action. Check `mfi_approval.application` for the row tagged `disburseLoan_submitApplication`.

## Code anchors

- Consumer: [`LmsMessageBrokerConsumer.java`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java) — `getDisburseSkipReason` names the four skip reasons
- State machine: [`mfi_orc.xml:4-200`](../../novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml#L4) — `function_sub_code` IParam matrix
- Retry job: scheduled by batch service; logic in `accounting:accountingBankServiceRetryJob` Request

## Related

- Full flow: [`../flows/disbursement-end-to-end.md`](../flows/disbursement-end-to-end.md)
- Lifecycle states: [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md)
- Open gap re Redis TTL: [`../gaps-and-risks.md`](../gaps-and-risks.md) (search "dl key TTL")
- **Local repro / regression suite:** [`/home/darpan/darpan/scripts/`](../../scripts/) — start at `START_HERE.md`. `regression_driver.py` reproduces every disburseLoan scenario (S1–S7 retry matrix, NEFT v2 callbacks, INDL/JLG/SHG variants) against a local Yugabyte DB and emits an HTML report
