# Disbursement Flow Intelligence (code-verified hot path)

This document captures the concrete, code-verified Kafka/idempotency/sync chain for disbursement replay debugging.

## 1) Trigger -> Kafka request (LOS producer)
Class: `in.novopay.los.util.DisburseLoanAPIUtil`

Method: `callDisburseLoanAPI(ExecutionContext executionContext)`

Verified behavior:
1. Builds `apiName = "disburseLoan"`.
2. Builds `<cacheKey>`:
   - `cacheKey = "disburseLoan" + <product_id_defaultString> + "_" + <external_ref_number_defaultString>`
3. Sends Kafka message payload (pipe-separated):
   - `disburseLoan|<request_json>|<cacheKey>`
4. Redis in-flight marker:
   - If `novopayCacheClient.get(tenant, cacheKey, ACCOUNTING) != null`:
     - returns without pushing Kafka (`DISBURSEMENT_REQUEST_IN_REDIS_CACHE`)
   - Else:
     - sets `novopayCacheClient.set(tenant, cacheKey, "in_progress", ACCOUNTING)` with **no TTL**
5. Publishes to Kafka topic prefix:
   - `losMessageKafkaProducer.pushDataToKafkaQueue(request, "disburse_loan_api_")`

## 2) Kafka consumer -> run accounting ORC (Accounting)
Class: `in.novopay.accounting.consumers.LmsMessageBrokerConsumer`

Verified behavior:
1. Message format assumption: `apiName|requestBody|cacheKey`.
2. Parses:
   - `originalCacheKey` = last pipe segment
   - processing lock key = `cacheKey = "dl" + originalCacheKey`
3. Skip gates (`getDisburseSkipReason`):
   - skips if loan is already `ACTIVE` and `disbursement_status == COMPLETED`
   - skips if `loan_status == LOCK`
   - skips if Redis contains the **dl-prefixed** lock (`dl+originalCacheKey`)
4. In-flight lock:
   - sets `novopayCacheClient.set(tenant, "dl"+originalCacheKey, "true", ACCOUNTING db)`
5. Executes accounting orchestration:
   - resolves ORC `<Request name="...">` from `api` and runs `ServiceOrchestrator.executeProcessors(...)`
6. Cleanup in `finally`:
   - removes both `originalCacheKey` and `dl+originalCacheKey`

## 3) Accounting -> Kafka result payload (sync trigger)
Class: `LmsMessageBrokerConsumer`

Method: `sendResultMessageToKafka(...)`

Verified result payload keys (sent to topic prefix):
- topic prefix: `los_lms_disbursement_sync`
- payload includes:
  - `external_ref_number`, `status`, `error_code`, `error_message`, `tenant_code`, `timestamp`
- IMPORTANT contract detail:
  - payload does **not** include `entity_type`

## 4) Kafka sync consumer -> update disburse_loan_process
Consumer: `in.novopay.los.kafka.DisbursementSyncConsumer`
- Parses JSON record to `Map` and does `executionContext.putAll(clientMap)`.
- Calls `DisbursementSyncService.handleDisbursementSyncRecord(executionContext)`.

Service: `in.novopay.los.service.disbursement.DisbursementSyncService`
Verified update gating:
1. Requires `external_ref_number`:
   - if blank: returns early (“external reference number is null”)
2. Requires `entity_type`:
   - if blank/missing: returns early (“entityType is null”)
3. Requires non-success disbursement status:
   - if `status == SUCCESS`: returns early (no update)
4. Skips DB update if current disburse process status is already in terminal set:
   - `COMPLETED`, `CHILD_SUCCESS`, `LAR_TASK_INITIATED`
5. Otherwise updates failure reason:
   - `updateFailureReason(id, code_error, error_message)`

## 5) `disbursement_status` writes in accounting-v2 ORC (validated write points)

This section is about what accounting-v2 persists into `loan_account.disbursement_status` across stages.

### 5.1 Pre-bank stage persistence (ORC)
- `updateDisbursedLoanAccountStatusProcessor` / `updateDisbursementStatusProcessor` persist intermediate statuses like:
  - `LOAN_BOOKED`
  - `DTFC_SUCCESS`
  - `REJECTED` (reject path)

### 5.2 Post-bank execution: what happens on success vs failure/UNKNOWN
- Bank-leg processor: `in.novopay.accounting.loan.disbursement.processor.CallBankAPIForDisbursementProcessor`
- Status persistence is done in `saveBankErrorResponseCode(...)` with these semantics:
  - when `IS_BANK_CALL_FAILED == FALSE`:
    - non-NEFT flow (`!isNeft`)
      - if member_details exist -> `PARENT_SUCCESS` else `COMPLETED`
    - NEFT flow (`isNeft`)
      - sets `loan_account.disbursement_status` to the current NEFT stage value from context (e.g. `NEFT_STAGE_*`)
  - when `IS_BANK_CALL_FAILED == TRUE` (failure/UNKNOWN/uncertain transport):
    - it does NOT call `setDisbursementStatus(...)`
    - it only fills `filler1/filler2` (error code/message) and saves

### 5.3 Lock recovery path (loan_status LOCK) does not update disbursement_status
- Lock recovery: `ClientRequestResponseLogDAOService.recover(...)`
- It sets `loan_account.loan_status = LOCK` and filler fields.
- Not found in code: a corresponding `loan_account.setDisbursementStatus(...)` in this lock-recovery flow.

### 5.4 NEFT callback stage progression (stage-wise update)
- ORC callback entrypoints:
  - `doGenericSyncSTPBankNEFNeftCallBack` with `callback_type = ST_NEF`
  - `doGenericSyncSTPBankNEINeftCallBack` with `callback_type = ST_NEI`
- Processor: `in.novopay.accounting.loan.disbursement.processor.DoGenericSyncSTPBankNeftCallBackProcessor`
  - on ST_NEF success:
    - sets `loan_account.disbursement_status = NEFT_STAGE_1_SUCCESS`
  - on ST_NEI success:
    - sets `loan_account.disbursement_status = COMPLETED`
  - failure/DTFC success handling:
    - sets `loan_account.disbursement_status = DTFC_SUCCESS`

## Confidence / gaps
- High: the exact Kafka payload format and Redis lock semantics above.
- High: `DisbursementSyncService` hard requirement on `entity_type`.
- Medium/UNVERIFIED: exact DB tables mutated beyond `loan_account.disbursement_status` in each stage (requires ORC and writer-level re-walk).

## 6) 2026-04-22 audit corrections (critical)

1. `los_lms_disbursement_sync` payload still omits both:
   - `entity_type` (contract-critical for LOS update),
   - `stan` (cross-service correlation-critical for RCA).
2. Accounting consumer skip reasons are asymmetric:
   - `ALREADY_ACTIVE` publishes sync,
   - `LOCK_LOAN_STATUS` / `LOCK_CACHE_IN_PROGRESS` return without sync message.
3. Consumer parsing happens before guarded `try/finally`:
   - malformed `api|json|cacheKey` input can fail before normal send/cleanup flow.
4. NEFT callback UTR map bug (array payload branch):
   - map key stored by `referenceno`, but later lookup uses external ref (`paymentrefno`).
   - can drop UTR propagation for successful callback rows.

## 7) 2026-04-22 parent payment-reinit execution validation

Validation window covered parent `REINITIATE_BANK` scenarios via accounting API execution path:

1. Parent MFT reinit and parent NEFT reinit both persisted on dedicated CRR lanes:
   - `DISBURSEMENT_MFT_REINIT`
   - `DISBURSEMENT_NEFT_REINIT`
2. Client reference generation progressed forward per attempt (no observed reuse/regression in reruns).
3. Explicit second reinit after fresh mode update executed as a new valid attempt for both MFT and NEFT parent flows.

Architect interpretation:
- Flow stitching for lane typing + reference progression is healthy for parent reinitiation.
- Replay suppression behavior should be validated in a dedicated idempotency-focused runbook cycle.

