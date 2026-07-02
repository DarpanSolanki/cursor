# Disbursement engine — sync, async, bank-call, NEFT v2 stage machine

**Branch verified:** `mfi_integration_v3.3.1.0.1` (head `149009993`, audited 2026-05-08).
**Predecessor:** `mfi_integration_v3.2.8.4.1` (head `467947e33`) — diff in [`../accounting/11-deltas-3.3.1.0.1.md`](../accounting/11-deltas-3.3.1.0.1.md).
**Authoritative paths:**
- Sync ORC: [loans_orc.xml](../novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml) `<Request name="disburseLoan">` at L580.
- Async ORC: [mfi_orc.xml](../novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml) `<Request name="disburseLoan" isAsync="true" explicitTxnMgmt="true">`.
- Kafka consumer: [LmsMessageBrokerConsumer.java](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java) (only money-path consumer in this service).
- Bank-call processors: [src/main/java/in/novopay/accounting/loan/disbursement/processor/](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/).
- Bank-call services: [src/main/java/in/novopay/accounting/loan/disbursement/bank/](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/bank/).
- Constants/util: [src/main/java/in/novopay/accounting/loan/disbursement/util/](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/util/).
- CRR DAO: [ClientRequestResponseLogDAOService.java](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/client/repository/ClientRequestResponseLogDAOService.java).

---

## 1. Three entry points

| Entry | Where | Transaction model |
|-------|-------|--------------------|
| **HTTP sync** | `loans_orc.xml` `disburseLoan` (L580) | Implicit single transaction (default for POST) |
| **HTTP async** | `mfi_orc.xml` `disburseLoan` with `isAsync=true explicitTxnMgmt=true` | **Explicit transactions** — each `<Transaction>` block / inner API commits independently |
| **Kafka async** | LOS publishes to `disburse_loan_api_<tenant>[_env]` → [LmsMessageBrokerConsumer.processConsumerRecord](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java#L80) → invokes the same `disburseLoan` orchestration via `executeServiceOrchestration` | Inherits orchestration's explicit txn flag; consumer wraps result publish in `try/finally` |

---

## 2. `disburseLoan` ORC chain (loans_orc.xml L580–L901)

Validators (L581–L602): `mandatoryFieldValidator` on `account_number, client_reference_number`; `patternFieldValidator` on `function_code` (DEFAULT|APPROVE|RESUBMIT), `function_sub_code` (DEFAULT), `run_mode` (TRIAL|REAL); RESUBMIT branch additionally requires `application_id`.

Processor chain (high level):

1. **Bootstrap (L605–L606)** — `populateUserDetails`, `validateLoanDisbursementDetailsProcessor`.
2. **Nested API call (L607–L671)** — `getLoanAccountDetails` v1 — fetches account snapshot, disbursement mode, repayment details, interest setup.
3. **`function_code = DEFAULT` branch (L673–L694)** — maker-checker decision: if disabled → set `call_post_transaction_required=1`; if enabled → only set when `run_mode=TRIAL`.
4. **`function_code = APPROVE` branch (L695–L706)** — populate dates, force `call_post_transaction_required=1`.
5. **`function_code = RESUBMIT` branch (L707–L716)** — re-edit + (if TRIAL) `call_post_transaction_required=1`.
6. **`call_post_transaction_required = 1` branch (L718–L765)** — disbursement-mode router:
   - `CASH` → `transaction_type=LOAN_DISBURSEMENT, sub_type=CASH`.
   - `ACCTWB|OTHACWB` → `sub_type=CASA`; populate disbursement account + CASA placeholder.
   - `OTHBACCT` (NEFT to other-bank) → `sub_type=ACCOUNT_TRANSFER_NEFT`.
   - Common: populate `LOAN_ACCOUNT` placeholder, additional amounts (upfront interest), then **nested `<API name="postTransaction">`** at L751–L761.
7. **`run_mode = REAL` branch (L767–L858)** — final state machine:
   - Maker-checker enabled, `function_code=DEFAULT` → submit for approval (`submitApplication` v1) → response 30220.
   - Maker-checker enabled, `function_code=RESUBMIT` → resubmit → response 30222.
   - Maker-checker disabled → `validateGenerateRepaymentScheduleProcessor` → `generateRepaymentScheduleProcessor` → `createRepaymentScheduleDetailsProcessor` (schedule_number=1) → `createInstallmentAndDueDetailsProcessor` → `updateLoanAccountProcessor` (loan_status=ACTIVE, disbursed_amount=loan_amount) → if `upfront_interest_applicable=true`: `populatePaymentDetailsForDisbursementProcessor` + due/installment updates → `constructRequestForApprovalUsingApprovalTemplate` (audit) → `deleteDraftProcessor` → conditional response (30219 DEFAULT / 30221 APPROVE).
8. **Audit (L861–L900)** — `use_case=LOAN-DSBR-UC001`, `stan`, `account_number`, `status`, `tenant`.

---

## 3. Kafka consumer flow ([LmsMessageBrokerConsumer.java](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java))

### 3.1 Payload contract (L70 comment + parsing)

```
Format: apiName|requestBody|cacheKey
Example: disburseLoan|{"headers":{...},"request":{...}}|disburseLoan44_123456
```

`processConsumerRecord` (L80–L125):
- L82: `originalCacheKey = raw.substring(raw.lastIndexOf("|") + 1)` (e.g. `disburseLoan44_123456`).
- L83: Redis key: `cacheKey = "dl" + originalCacheKey`.
- L85–L91: `productId`/`externRefNumber` extracted by stripping `disburseLoan` prefix and splitting on `_`.

### 3.2 Skip-reason gate ([L130–L158](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java#L130-L158))

Order checked:
1. `loanStatus == ACTIVE && disbursement_status == COMPLETED` AND request is **not** payment-reinitiation → **`ALREADY_ACTIVE`** → publish SUCCESS to LOS (L97), then cleanup keys.
2. `loanStatus == LOCK` → **`LOCK_LOAN_STATUS`** → silent skip; cleanup keys.
3. Redis `cacheKey` already present → **`LOCK_CACHE_IN_PROGRESS`** → silent skip; **do not** clear (another worker is mid-flight).
4. else → `NONE` → proceed.

### 3.3 Reinit detection ([L160–L204](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java#L160-L204))

`extractFunctionSubCodeFromLmsDisburseRaw` parses `requestBody` JSON:
- Primary: `headers.function_sub_code`.
- Fallback: top-level `function_sub_code`.
- Treated as reinitiation when value equals `AccountingConstants.REINITIATE_BANK`.

When reinitiation → bypass the `ALREADY_ACTIVE` skip so a controlled bank re-fire can proceed.

### 3.4 Orchestration dispatch ([L206–L231](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java#L206-L231))

1. Parse `api`, `requestBody` from raw.
2. `jsonHelperForRequestResponse.parseAPIHeader` + `parseAPIRequest` → request map.
3. `populateExecutionContext(api, "v1", requestMap, requestBody)`.
4. `orcXMLParser.getRequestFromOrcXML(tenantCode, "disburseLoan")` (resolves via tenant precedence: mfi, then product).
5. `serviceOrchestrator.executeProcessors(...)` with explicit-txn flag from XML and `undoProcessorList`.

### 3.5 Result publish ([sendResultMessageToKafka L239–L271](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java#L239-L271))

**Verified payload on this branch:**

```json
{
  "external_ref_number": "...",
  "status": "SUCCESS" | "FAILED",
  "error_code": "<from NovopayFatalException.getErrorCode() or UNKNOWN_ERROR>",
  "error_message": "<exception message or notificationUtil.getResponseMessage(errorCode)>",
  "tenant_code": "...",
  "timestamp": <System.currentTimeMillis()>
}
```

Topic: `los_lms_disbursement_sync` (hardcoded literal at L259).

**⚠ DOC DRIFT FOUND ON THIS BRANCH:**
- The payload on this branch does **NOT** include `entity_type` or `stan`.
- `gaps-and-risks.md` previously marked these as RESOLVED on 2026-04-17 — that resolution did not survive into this branch.
- LOS `DisbursementSyncService` still skips when `entity_type` missing (existing High gap row).
- **Action:** entity_type/stan rows in `gaps-and-risks.md` reopened in this resync.

### 3.6 Redis lifecycle

- **Set** at L111: `novopayCacheClient.set(tenantCode, cacheKey, "true", RedisDBConfig.ACCOUNTING.getDbIndex())` — **no TTL parameter**. Documented gap (stale lock if JVM dies between set and `cleanupCacheKeys`).
- **Cleanup** at L233–L235 (`cleanupCacheKeys`): removes both `originalCacheKey` and `cacheKey`. Always called in `finally`, also called on skip (except `LOCK_CACHE_IN_PROGRESS`).

---

## 4. Bank-call orchestration

### 4.1 Parent — [`CallBankAPIForDisbursementProcessor.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/CallBankAPIForDisbursementProcessor.java)

Key behaviour:
- **L61** — for `OTHBACCT` (NEFT-out) initialise `NEFT_STAGE_STATUS` from `disbursement_status` if blank.
- **L108** — call `parentDisbursementBankCallService.findLatestBankCrrForInquiry(...)` to decide inquiry vs new.
- **L112, L122** — `doStatusInquiry()` for MFT or NEFT.
- **L142** — MFT reinit inquiry (uses session-scoped external ref so bank doesn't see duplicate).
- **L188, L230** — `doMFTTransaction()`.
- **L128** — `doNEFTTransaction()` (NEFT v2).
- **L194** — `shouldSkipNeftStage2Initiation` gate (parent–child ST_NEI parity, double-debit guard).
- **L198–L199** — when `NEFT_STAGE_1_SUCCESS` or `NEFT_STAGE_2_PENDING`, swap transaction-type from `..._NEFT_NEF` to `..._NEFT_NEI`.

CRR `transaction_type` strings emitted (parent):
- `<txn>_MFT` (and `_REINIT` suffix for reinitiation)
- `<txn>_NEFT` (NEFT v1 — deprecated by `USE_NEFT_V1=false`)
- `<txn>_NEFT_NEF` (NEFT v2 stage 1)
- `<txn>_NEFT_NEI` (NEFT v2 stage 2)
- `MFT_TRANSACTION_INQUIRY`, `NEFT_TRANSACTION_INQUIRY` (inquiry rows)

### 4.2 Child — [`CallBankAPIForIndividualChildLoanDisbursementProcessor.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/CallBankAPIForIndividualChildLoanDisbursementProcessor.java)

Differs from parent:
- L39 — requires `child_seq_no` (throws MFI_40001 if missing).
- L43 — child idempotency base: `clientReferenceBase = parentLoanAccountNumber + childSequenceNo`.
- Transaction-type spelling embeds external ref: `<txn>_EXTREF<n>_MFT`, `<txn>_EXTREF<n>_NEFT_NEF`, `<txn>_EXTREF<n>_NEFT_NEI` (and `_REINIT` variants).
- Service: `ChildDisbursementBankCallService` (`loan/disbursement/bank/child/`).

### 4.3 Callback processors

- [`DoGenericSyncSTPBankNeftCallBackProcessor.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java) — parent NEF/NEI callback handling.
- [`PostNEFTChildLoanBankDisbursementProcessor.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/PostNEFTChildLoanBankDisbursementProcessor.java) (L50–L88) — logs CRR with `transactionType = transactionIdentifier`; status SUCCESS sets `disbursement_status` + `neft_stage_Status`; FAIL sets `is_bank_call_failed=TRUE` + `BANK_ERROR_PREFIX + responseCode`.
- [`PostMFTChildLoanBankDisbursementProcessor.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/PostMFTChildLoanBankDisbursementProcessor.java) (L99–L130) — CRR fields from callback `apiResponse`/null-envelope (response-fidelity invariant); `resolveTransactionIdentifier` (L136–L147) builds `<txn>_EXTREF<n>_MFT` if context omits identifier. Updates `loan_account_events_queue.data` JSON with `external_error_code/message, disbursement_status` and queue `event_status` to C/P; calls `parentGroupDisbursementStatusSyncService.syncParentAfterChildQueueProgress()` to roll status up.

### 4.4 Services

- [`ParentDisbursementBankCallService.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/bank/parent/ParentDisbursementBankCallService.java) — façade; delegates to MFT / NEFT v1 / NEFT v2 collaborators (`ParentDisbursementMftBankCall`, `ParentDisbursementNeftV1BankCall`, `ParentDisbursementNeftV2BankCall`).
- [`ParentDisbursementNeftV2BankCall.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/bank/parent/ParentDisbursementNeftV2BankCall.java):
  - **`shouldSkipNeftStage2Initiation` (L130–L143)** — returns true when `disbursement_status=NEFT_STAGE_2_PENDING` AND a **SUCCESS** CRR already exists for the orchestration-scoped `DISBURSEMENT_NEFT_NEI` (or `_REINIT` variant). Prevents double ST_NEI.
  - **`performNeftV2InquiryWhenStage1Pending` (L149+)** — runs `neftServicePartnerDiscoveryService.neftTransactionStatusInquiryV2()` (L187); on `errorCode=0` sets `disbursement_status=NEFT_STAGE_1_SUCCESS, neft_stage_Status=NEFT_STAGE_1_SUCCESS` (L204–L205); persists UTR (L212); logs CRR (L208–L210).
  - **`performNeftV2InquiryWhenNotStage1Pending` (L151+)** — DTFC_SUCCESS + previous FAIL allows fresh NEF (L251–L253); STAGE_1_SUCCESS / STAGE_2_PENDING proceeds with NEI (L255–L259).
- **Child stage-1 evidence (`ChildDisbursementNeftV2BankCall.hasSuccessfulChildNeftStage1`)** — gates child stage-2 NEI initiation. Accepts three signals (post-`ede4aa325` on `mfi_integration_v3.2.8.4.1`): (1) SUCCESS NEFT_NEF outgoing CRR, (2) SUCCESS `NEFT_TRANSACTION_INQUIRY` CRR, (3) queue row `disbursement_status` ∈ `{NEFT_STAGE_1_SUCCESS, NEFT_STAGE_2_PENDING}`. The third signal is critical for the "empty synchronous response + async SUCCESS callback" path where there is no SUCCESS outgoing CRR but the queue's status is the bank-attested truth. The pre-`ede4aa325` form required signal 1 only and permanently blocked stage-2 for callback-only-success children.
- **Child in-flight gate (`CallBankAPIForIndividualChildLoanDisbursementProcessor.acquireDistributedInFlightKey`)** — uses `NovopayCacheClient.setIfAbsent` (Redis `SET … PX … NX`) for atomic cross-pod acquisition. Pre-`ede4aa325`/cursor-`ea5dba734` interim form was a get-then-set sequence with a TOCTOU race that allowed cross-pod duplicate execution despite the Redis prefix.
- `ChildDisbursementBankCallService` — symmetric façade for child rail.

### 4.5 Constants ([`DisbursementBankCallConstants.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/util/DisbursementBankCallConstants.java))

| Constant | Value | Purpose |
|----------|-------|---------|
| `USE_NEFT_V1` | `false` | NEFT v2 active; v1 deprecated |
| `EXTERNAL_REF_COUNTER_FORMAT` | `%02d` | Two-digit external-ref counter |
| `MFT_TRANSACTION_INQUIRY` | `MFT_TRANSACTION_INQUIRY` | Inquiry CRR row type |
| `NEFT_TRANSACTION_INQUIRY` | `NEFT_TRANSACTION_INQUIRY` | Inquiry CRR row type |
| `NEFT_SUFFIX` | `_NEFT_NEF` | NEFT v2 stage 1 |
| `NEFT_V1_SUFFIX` | `_NEFT` | NEFT v1 (legacy) |
| `MFT_SUFFIX` | `_MFT` | MFT lane |
| `NEFT_STAGE_1_PENDING/SUCCESS, NEFT_STAGE_2_PENDING` | identical strings | Disbursement state machine |
| `NEFT_STAGE_STATUS` | `neft_stage_Status` | EC key |
| `PARTNER_CODE` | `Hdfc` | CRR partner column |
| `EVNTQ` | `_EXTREF` | Child txn-type infix |
| `DISBURSEMENT_NEFT_CRR_REINIT_SUFFIX` | `_REINIT` | Appended for reinit CRRs |

### 4.6 External ref ([`ExternalReferenceNoUtil.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/util/ExternalReferenceNoUtil.java))

- L23–L34 — `buildMftStatusInquirySessionExternalRef`: uses same counter but a different prefix so bank does not treat the inquiry as a duplicate MFT submit.
- L41–L59 — `buildNeftStatusInquirySessionExternalRef`: NEFT v2 inquiry leg uses `06`-style prefix and shares the counter with NEFT_PAYMENT (`03`) / NEFT_STAGE2_PAYMENT — so an inquiry never collides with the underlying payment ref at the bank.
- L65–L138 — `computeDeterministicExternalReferenceNo` (multiple overloads): idempotent ref by querying latest CRR counter for the type list.
- **Counter rule (L208–L227)**: `nextCounter = lastFailed ? lastCounter + 1 : lastCounter`. Definitive **FAIL** bumps the counter (next call gets a fresh ref); **SUCCESS** or **UNKNOWN** reuses the same ref. This is the application-level idempotency contract — combined with the bank's external-ref dedup, retries that don't bump the counter cannot double-credit the customer.
- **MFT UNKNOWN special-case (L169–L224)**: when the latest `MFT_TRANSACTION_INQUIRY` is `UNKNOWN` and its counter matches the latest `DISBURSEMENT_MFT` counter, `lastFailed` is forced to **false** even if the latest payment row is FAIL. Reasoning: the FAIL might be transport-only and the bank may already have processed; bumping the counter would issue a NEW payment with a different ref and the bank would lose its dedup. The execution-context override params (`mftInquiryLogStatusFromExecution`, `mftInquiryClientReferenceNumberFromExecution`) let in-flight orchestrations pass the inquiry result without a stale DB read. **Critical:** this rule applies only to MFT (the `_MFT` suffix + `02` prefix check at L173–L176); NEFT v2 has its own inquiry path that flips `disbursement_status` directly.
- L66–L84 — overload with `clientReferenceBaseOverride` so child uses `parentLoanAccountNumber + childSeqNo` instead of `loanAccountNumber`.
- The `03` external-ref counter family is shared across original + reinit rows for parent NEFT v2 (kept aligned by the multi-type lookup).

### 4.7 Multi-layer defence against double processing (verified 2026-05-04)

The system relies on **five layered guards** — each layer narrows the window where a duplicate could land at the bank. Failure of any single layer is contained by the next.

| Layer | Mechanism | Scope | File:line |
|---|---|---|---|
| 1 | Kafka consumer Redis dedup (`dl<productId>_<extRef>` key) | Parent `disburseLoan` from LOS | `LmsMessageBrokerConsumer` |
| 2 | Single-thread queue-row processing (one CLMT row → one bank-call thread) | Child SHG/JLG legs | [`PerformChildLoanBankDisbursementProcessor`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/PerformChildLoanBankDisbursementProcessor.java) |
| 3 | Atomic Redis SETNX gate (`child_disbursement_inflight_<lan>\|<txnType>`, 10-min TTL) | Cross-pod child legs (added in `ede4aa325`) | [`CallBankAPIForIndividualChildLoanDisbursementProcessor.acquireDistributedInFlightKey`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/CallBankAPIForIndividualChildLoanDisbursementProcessor.java) |
| 4 | Deterministic external-ref counter (FAIL bumps, SUCCESS/UNKNOWN reuses) | All bank calls | [`ExternalReferenceNoUtil.computeDeterministicExternalReferenceNo`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/util/ExternalReferenceNoUtil.java) L208–L227 |
| 5 | Bank-side idempotency on external-ref | Outside-system | Bank API contract |

**Explicit risk if Layer 4 misfires**: a duplicate ref + later FAIL → counter bump → second payment with new ref → bank sees as separate → **double credit**. This is why the MFT UNKNOWN special-case exists: it forces counter reuse on inquiry-uncertainty so a transport-FAIL doesn't trigger a counter bump while the bank has actually processed.

### 4.8 State integrity primitives

> Post-2026-05-07 architecture. The earlier rank-guard-before-`dao.save` pattern (commits `c2583dca9` / `5bb49d7a4` / `c704969ec` / `ccf7f6b89`) was REPLACED by atomic CAS in PR #260 (`e3d84a53b` … `f6e83c9fe`) and finalized by `4c339282f` + `09295c377` (Hibernate auto-flush race fix). Old rank-guard primitives still live for MFT and as `fromStates` derivation.

- **`ChildClmtStateMachineService`** ([file](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/service/ChildClmtStateMachineService.java)) — sole owner of `loan_account_events_queue` CLMT state transitions. Two methods, both `REQUIRES_NEW`:
  - `transition(ChildClmtTransitionRequest)` — runs the atomic CAS via `LoanAccountEventsQueueRepository.conditionalUpdateClmtState` (`@Modifying` UPDATE … WHERE `(data::jsonb)->>'disbursement_status' = ANY(string_to_array(:fromStatesCsv, ','))`). 1 row updated → `APPLIED`; 0 rows → `REJECTED` (a concurrent writer raced ahead). State, JSON patches, `event_status`, `filler_2`, `filler_3`, and `updated_on=:now` all set in a single statement.
  - `patchJsonFields(rowId, patches, filler2, updatedBy)` — state-agnostic sibling for advisory / error-only writes (added `4c339282f`). Throws if `patches` contains `disbursement_status`, so it can never accidentally revert state.
- **`LoanAccountStateMachineService`** ([file](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/service/LoanAccountStateMachineService.java)) — same shape for `loan_account.disbursement_status` (parent JLG/INDL flow). Used by `DoGenericSyncSTPBankNeftCallBackProcessor.processNEFCallback` / `processNEICallback` and `CallBankAPIForDisbursementProcessor`. Added `8a1969b15`, callsites migrated `f6e83c9fe`.
- **`ChildClmtTerminalStateGuard`** ([file](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/service/ChildClmtTerminalStateGuard.java)) — shared rank table `DTFC_SUCCESS(1) < NEFT_STAGE_1_PENDING(2) < NEFT_STAGE_1_SUCCESS(3) < NEFT_STAGE_2_PENDING(4) < COMPLETED(5)`. Static helper `rankBackwardSafeFromStates(toState)` — strictly-lower-rank states for forward-only CAS, with COMPLETED carve-out (returns all states for idempotent terminal). Every CAS caller uses this to derive `fromStates`. `isAlreadyCompleted(queueId)` and `isAtOrBeyondStage(queueId, expectedStatus)` still exist for MFT post-handler (not yet migrated) and as the canonical "is this row terminal" check.
- **In-memory entity rule (post-`4c339282f`):** any code path that calls a CAS service on a `LoanAccountEventsQueueEntity` MUST NOT subsequently call setters on that entity object. The same entity is loaded by `PerformChildLoanBankDisbursementProcessor:74` and stays in the outer `disburseLoan` Hibernate persistence context; `AbstractBaseEntity` has no `@PreUpdate`, so any in-memory mutation gets auto-flushed at outer-tx commit with stale `updated_on`, reverting the CAS. Cross-reference: `~/.claude/projects/-home-darpan-darpan/memory/feedback_no_inmem_mutation_after_cas.md`.
- **Canonical UTR column on `loan_account_events_queue` is `filler_3`** (`7ab965fe3`). The CAS sets it directly via the request's `.filler3(utrNumber)` builder — no in-memory `setFiller3` is needed (and is now forbidden by the rule above). Async writer: [`DoGenericSyncSTPBankNeftCallBackProcessor.processLoanAccountForChildLoans:262`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L262). Sync writer: [`ChildNeftClmtPostBankService.applyClmtAndSave:104`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/service/ChildNeftClmtPostBankService.java#L104). READER: `BookChildLoanProcessor.java:412` copies `event.getFiller3()` to `loan_disbursement_mode_details.utr_number`. Pre-`7ab965fe3` the sync path wrote to `filler_1` and UTR was stranded; pre-`4c339282f` the sync path mutated the entity in memory and the CAS write was reverted by auto-flush — both now closed.
- **`ParentGroupDisbursementStatusSyncService.syncParentAfterChildQueueProgress(parentAccountId)`** ([file](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/disbursement/service/ParentGroupDisbursementStatusSyncService.java)) — child→parent rollup. Counts CLMT `event_status=C`; only proceeds when ALL CLMTs are done; only flips parent if currently `PARENT_SUCCESS` / `CHILD_SUCCESS`; sets target = `CHILD_SUCCESS` (CLB pending) or `COMPLETED`. Idempotent — every concurrent caller computes the same target.

### 4.9 Async callback handler ([`DoGenericSyncSTPBankNeftCallBackProcessor.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java))

Receives bank batch callbacks (NEFT_NEF / NEFT_NEI). Parses each payment into success / failed / in-progress lists keyed by `PAYMENTREFNO`, then dispatches per-extref. Routing:

- `processSingleCallback` first tries `resolveParentNefTxnByClientRef` (parent CRR for `DISBURSEMENT_NEFT_NEF`). If found → `processLoanAccount` (parent path: flips `loan_account.disbursement_status` directly).
- Otherwise looks up CRR by `client_reference_number` and checks `transaction_type.contains("_EXTREF")` → `processLoanAccountForChildLoans` (child path: flips queue row's embedded `disbursement_status` and event_status).
- `extractChildExternalRef` uses regex `_EXTREF(.*?)_(MFT|NEFT(?:_NEF|_NEI)?)$` (post-`ea5dba734`) — robust against arbitrary `external_ref_number` patterns; pre-fix `replaceAll("\\D+", "")` was ambiguous when the txn-type tail contained extra digits.
- **UTR map keying (post-`ea5dba734`)**: `utrMap` is keyed by `PAYMENTREFNO` (matches the lookup key in `processSingleCallback`); pre-fix it was keyed by `REFERENCENO` (the bank's UTR), so lookup always returned null and child UTRs were never persisted. Fixed in `parseNEFCallback` L159, L181.
- **Late-failure semantics (L367–L373)**: a NEF FAIL callback that arrives after the row is already at `NEFT_STAGE_1_SUCCESS` is **dropped** with a log line. This is intentional (a real bank-callback success cannot be retroactively cancelled by a duplicate-FAIL retry callback), but means contradictory bank callbacks can leave a stuck row. Operationally rare but worth noting.
- **Orchestration-commit-lag retry (added in `8abd48f49`)**: callback-handler lookups by `filler_2` (`processLoanAccountForChildLoans`, `processFailedLoanAccountForChildLoans`, `processInProgressCallbackForChild`) now go through `findClmtQueueRowWithRetry` — 5 attempts with linear-progressive backoff (100ms / 200ms / 300ms / 400ms; total max ≈ 1s). Reason: bank async callbacks can arrive on Tomcat HTTP threads while the disburseLoan orchestration is still inside its open transaction with uncommitted CLMT INSERTs. Under READ COMMITTED isolation a single SELECT returned `null` and the callback bailed silently; the retry covers the orchestration's commit window. First-attempt fast path keeps happy-path latency unchanged. **Kept as defence-in-depth alongside the structural fix below.**
- **CLMT REQUIRES_NEW + idempotency-guard attempt (`e8fef5c35`) — REVERTED in `2d9730818`**: idea was to commit CLMT rows in a separate transaction so async bank callbacks could see them immediately, with an idempotency check to prevent duplicate rows on retry. **Reverted same-day** because the orphan-row safety story was unverified: `accountingBankServiceRetryJob` queries `client_request_response_log` (not `loan_account_events_queue`), and `childLoanEventProcessingBatchJob` explicitly excludes CLMT via `EVENT_TYPE_IGNORE_API_MAP` ([`LoanAccountEventsQueueEntity.java:54`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java#L54), [`ChildLoanEventProcessingItemProcessor.java:60-62`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/childloaneventprocessingbatchjob/ChildLoanEventProcessingItemProcessor.java#L60)). With no scheduled job picking up orphan PENDING CLMT rows, the structural fix would have left rows stuck forever after any orchestration abort. Replaced by `a6fdc1c88` (next bullet) with a verified recovery path.
- **Child MFT post-bank handler OLE stabilization (`5bb49d7a4`)** — same shape as `c2583dca9` for NEFT v2, applied to MFT. `MAX_OLE_ATTEMPTS=3`; targeted OLE catch in `PostMFTChildLoanBankDisbursementProcessor.execute` prevents reactor-pipeline drop + SOF re-fire. Terminal guard kept as `isAlreadyCompleted` (sufficient for MFT's single-step state). CRR-first ordering was already in place pre-this-commit.
- **disburseLoan CLMT prep-block split (`a6fdc1c88`)** — structural fix that closes the visibility race using XML-level transaction boundaries. New processor `PrepareClmtRowsForChildDisbursementProcessor` runs inside its own `<Transaction>` block in [`mfi_orc.xml`](../novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml) immediately before the existing child-bank-call block. The new block commits CLMT rows (each `<Transaction>` is `REQUIRES_NEW` per [`ProcessorOrchestrator.java:111`](../novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ProcessorOrchestrator.java#L111)) before any bank call fires, so async callbacks find the rows immediately. Idempotency: prep-processor's existing-row check + [`PerformChildLoanBankDisbursementProcessor.java:74-78`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/PerformChildLoanBankDisbursementProcessor.java#L74) lazy-create fallback. Orphan recovery: the same line 74-78 path reuses orphan PENDING rows on the next disburseLoan retry — verified by reading the file (not assumed). Per-leg dedup unchanged (Redis SETNX + deterministic external_ref + bank-side dedup).
- **Populate-before-prepare ordering fix (2026-05-06, follow-up to `a6fdc1c88`)** — the prep-block split moved CLMT row creation upstream of `populateAdditionalAmountDetailsForChildDisbursementProcessor`, which is the only place where per-member `net_disbursed_amount` is computed. Result on QA3 parent 11850460 (LAN 6009682925): all 23 CLMT rows committed with `data.net_disbursed_amount=null`, then `CallBankAPIForIndividualChildLoanDisbursementProcessor` silently returned at [lines 61-65](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/CallBankAPIForIndividualChildLoanDisbursementProcessor.java#L61) (empty `totalAmount` → set `IS_BANK_CALL_FAILED=TRUE`, return — **with no log line**) for every child leg. PerformChild's "took 27 ms" for 23 children + zero `reactor-http-epoll-N` activity = no NEFT calls dispatched. Fix: `PrepareClmtRowsForChildDisbursementProcessor.process()` now calls `populateAdditionalAmountDetailsForChildDisbursementProcessor.execute(executionContext)` before invoking `CreateClmtLoanAccountEventsProcessor`, so member objects carry the computed amount when [`ChildLoanMoneyTransferEventsQueueDataPopulator:39`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/disbursement/service/ChildLoanMoneyTransferEventsQueueDataPopulator.java#L39) reads `member.get("net_disbursed_amount")`. Defense-in-depth: same commit converts the silent early-return at `CallBankAPI…:61` into an `LOGGER.error(...)` so any future regression of this shape surfaces in `accounting-mfi.log` instead of dropping every child leg silently. Recovery for parent 11850460 (and any orphan SHG/JLG): soft-delete pending CLMT rows where `data->>'net_disbursed_amount' IS NULL`, then re-fire `disburseLoan` — the new prep block writes fresh rows with the amount populated.
- **Hibernate auto-flush race on the in-memory CLMT entity (2026-05-07, `4c339282f`) — the final fix in the NEFT v2 race series.** Even after the atomic-CAS redesign (`e3d84a53b` … `f6e83c9fe`) closed the DB-side last-writer-wins, one race window survived: `ChildNeftClmtPostBankService.applyClmtAndSave` OK branch and the `processInProgressCallbackForChild` advisory branch were both **mutating the in-memory `LoanAccountEventsQueueEntity`** after the CAS APPLIED (or after CAS REJECTED, in the advisory case). That entity is loaded by `PerformChildLoanBankDisbursementProcessor:74` at the start of `disburseLoan` and stays in the outer NP-Executor thread's persistence context. `AbstractBaseEntity` has **no `@PreUpdate`/`@UpdateTimestamp`** ([`AbstractBaseEntity.java:35-44`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/common/entity/AbstractBaseEntity.java#L35-L44)), so the in-memory `updated_on` keeps its load-time value forever. When the outer `disburseLoan` transaction commits, Hibernate dirty-checks the entity, sees mutations on `data` / `event_status` / `filler_2`, and emits a plain `UPDATE` that **rewrites the row with the in-memory state including the stale `updated_on`** — undoing any later async-callback CAS to `COMPLETED`. On QA3 parent LAN 6009683725 child 19, this manifested as a row stuck at `NEFT_STAGE_2_PENDING` + `"NEI Initiated…"` + `updated_on=12:49:30.904` despite an async-callback CAS having reached the row at 12:54:28.5. **Fix:** the post-CAS in-memory mutation block in `applyClmtAndSave`, the pre-CAS `row.setFiller3(utr)`, and the `dao.save(row)` paths in the failure / parse-error / advisory branches all removed. CAS is now the sole writer. Failure / advisory / parse-error writes go through a new state-agnostic `ChildClmtStateMachineService.patchJsonFields` that does a `@Modifying` JSON-merge UPDATE (rejects any patch containing `disbursement_status`). Dead OLE retry loop dropped (no `@Version`, never fires). RCA narrative is in the commit message of `4c339282f` and the `2026-05-07` entry in `claude/changelog/CHANGELOG.md`. **Rule going forward: any path that calls a CAS service on a CLMT entity MUST NOT subsequently set fields on that entity object.**

- **Sync NEI inquiry post-handler vs async NEI callback race fix (2026-05-06, `c704969ec`)** — at stage-2 the queue row gets written by TWO different threads in close succession: (a) reactor-http-epoll thread running `ChildNeftClmtPostBankService.applyClmtAndSave` to mark `NEFT_STAGE_2_PENDING` after the sync ST_NEI inquiry response, and (b) Tomcat HTTP worker running `DoGenericSyncSTPBankNeftCallBackProcessor.processInProgressCallbackForChild` (codstatus=N) or `processLoanAccountForChildLoans` (codstatus=P) to mark `COMPLETED` from the bank's async NEI callback. With no `@Version` on `LoanAccountEventsQueueEntity`, JPA save = blind UPDATE: last-writer-wins on a column-by-column basis. On QA3 parent 11850760 (LAN 6009683325) child 2, async hit the gateway 119ms after sync started but BEFORE sync's UPDATE committed → async read stale `NEFT_STAGE_1_SUCCESS` → curStatus check at [`DoGenericSyncSTPBankNeftCallBackProcessor:502`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L502) failed (only accepted `NEFT_STAGE_2_PENDING`) → fell to else branch (line 512), updated error fields without transitioning. Sync committed `NEFT_STAGE_2_PENDING` after, overwriting async. Net: row stuck. The signature was visible in `data.external_error_message`: stuck rows show "NEFT ST_NEI Transaction Initiated successfully" (sync handler signature) instead of the bank's "Under Process at Bank" (async handler signature). Two-part fix: (1) async transition condition now accepts `NEFT_STAGE_1_SUCCESS` in addition to `NEFT_STAGE_2_PENDING` (state machine still monotonic forward — bank's NEI callback proves inquiry was issued); (2) sync handler `ChildNeftClmtPostBankService.applyClmtAndSave` OK branch now consults `ChildClmtTerminalStateGuard.isAtOrBeyondStage` before save (was previously only consulted in the OLE catch, which never fires because no `@Version`). Both writers now respect monotonic-forward state machine regardless of timing.

---

## 5. CRR (`client_request_response_log`) — the bank-side audit & idempotency table

### 5.1 [`ClientRequestResponseLogDAOService.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/client/repository/ClientRequestResponseLogDAOService.java)

- **L31–L45** `save(...)` — `@Transactional(REQUIRES_NEW)` + `@Retryable` on lock exceptions (`CannotAcquireLockException`, `LockAcquisitionException`); attempts/backoff from `retryConfiguration` bean.
- **L50–L65** `recover(...)` (`@Recover`) — when retries exhausted: load the loan, set `loanStatus=LOCK`, `filler1="MFI-40099"`, `filler2="Loan account ... has been locked due to save failure in audit"`, save loan, then throw `MFI-40003`. **Side-effect:** loans get LOCK on persistent CRR write failure — needs ops reset; documented Medium gap.
- L67–L90 — Query helpers:
  - `findOneByLoanAccountNumberAndTransactionType(loanAccountNumber, txnTypeList, partner)` — latest CRR for inquiry lookup.
  - `findOneByLoanAccountNumberAndTransactionTypeAndStatusSuccess(...)` — drives `shouldSkipNeftStage2Initiation` and similar idempotency gates.
  - `findOneByClientReferenceNumberAndTransactionType`, `findOneByClientReferenceNumber` — alternate lookups.

### 5.2 [`ClientRequestResponseLogEntity.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/client/entity/ClientRequestResponseLogEntity.java)

| Column | Notes |
|--------|-------|
| `partner` | e.g. `Hdfc` |
| `client_reference_number` | external ref sent to bank |
| `loan_account_number` | row key for lookups |
| `transaction_type` | the deterministic key — e.g. `DISBURSEMENT_NEFT_NEF`, `DISBURSEMENT_NEFT_NEI`, `DISBURSEMENT_MFT_REINIT`, child `DISBURSEMENT_<EXTREF<n>>_NEFT_NEF` |
| `status` | `SUCCESS` / `FAIL` / `UNKNOWN` |
| `request`, `response` | full JSON payloads |
| `system_date`, `business_date`, `updated_on` | timestamps |
| `eligible_for_retry`, `retry_count` | retry framework hooks |

**Response-fidelity invariant (2026-04-14):** in WebClient callback flows, the CRR `status` and `response` must come from the **same** payload source. Child NEFT and child MFT post-processors enforce this (callback `apiResponse` or explicit null-envelope). Historical child-MFT mismatch was tracked as GAP-061 and fixed.

---

## 6. NEFT v2 stage machine — state transitions

Driver field: `loan_account.disbursement_status` + EC `neft_stage_Status`.

```
                     +------------------------+
                     | DTFC_SUCCESS (default) |  fresh load / queue ack
                     +-----------+------------+
                                 |
        ST_NEF (parent: doNEFTTransaction stage 1)
                                 |
                                 v
                     +------------------------+
                     | NEFT_STAGE_1_PENDING  |
                     +-----------+------------+
                                 |
        callback / replay → neftTransactionStatusInquiryV2
                                 |
                  +--------------+--------------+
                  | errorCode=0 |  others       |
                  v             v               v
        NEFT_STAGE_1_SUCCESS  FAIL           UNKNOWN (retry inquiry)
                  |
        ST_NEI  (stage 2; gated by shouldSkipNeftStage2Initiation)
                  |
                  v
        NEFT_STAGE_2_PENDING
                  |
        callback / replay → COMPLETED
```

**Idempotency guards (verified, code-cited):**

- **L1 inquiry gate (2026-04-15):** child path. When `disbursement_status=DTFC_SUCCESS` but a prior child-scoped `..._NEFT_NEF` CRR exists with non-success state, run inquiry instead of hard-skipping (`NeftStage1InquiryGate` shared rule).
- **Parent inquiry parity (2026-04-16):** `CallBankAPIForDisbursementProcessor.performNEFTTransactionInquiry` uses the same `NeftStage1InquiryGate` semantics.
- **ST_NEF double-debit guard (2026-04-16):** parent + child `doNEFTTransaction` skip initiation when `client_request_response_log` already has `status=SUCCESS` for the same scoped `transaction_type`.
- **Parent ST_NEI idempotency parity (2026-04-16):** `shouldSkipNeftStage2Initiation` covers BOTH `NEFT_STAGE_1_SUCCESS` and `NEFT_STAGE_2_PENDING`.
- **Child NEFT v2 CRR transaction_type fallback (2026-04-16):** `PostNEFTChildLoanBankDisbursementProcessor` resolves child-scoped `..._EXTREF<n>_NEFT_NEF` / `..._NEFT_NEI` even if WebClient callback omits `transactionIdentifier`.
- **Lane-scoped CRR selection (2026-04-15):** child bank-retry CRR selection is mode/type-scoped (MFT vs `..._NEFT_NEF` first, `..._NEFT_NEI` fallback), eliminating timing-driven inquiry variance.

**Local test sequence (2026-04-27):** callback-driven authoritative path —
`NEF call → NEF callback → NEFT_STAGE_1_SUCCESS → NEI call → NEI callback → COMPLETED`.
Callback envelopes require `headers.tenant_code` + `request.faxml...` (NEF) or `request.faml...` (NEI); chameleon `simulator_response.validation` for `doGenericSyncSTPNEF/Inquiry/NEI` must be non-blank.

---

## 7. Loan account columns relevant to disbursement

[`LoanAccountEntity.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java) (854 lines):

| Column | Notes |
|--------|-------|
| `loan_status` (enum: `LoanStatus`) | APPROVED, ACTIVE, FORECLOSURE_FREEZE, WRITOFF, CLOSED, DISB_CNCL, **LOCK**, ... |
| `disbursement_status` | `NEFT_STAGE_1_PENDING`, `NEFT_STAGE_1_SUCCESS`, `NEFT_STAGE_2_PENDING`, `COMPLETED`, `PARENT_SUCCESS`, `CHILD_SUCCESS`, `DTFC_SUCCESS`, ... |
| `external_ref_number` | NOT NULL — primary correlation key with LOS |
| `loan_amount`, `disbursed_amount` | money fields |
| `expected_disbursement_date`, `first_repayment_date` | dates |
| `filler_1`–`filler_11` | error code, message, UTR, vtc_id slot — see CLB CLB note in `accounting-flows.md` |

---

## 8. Async event queue — `loan_account_events_queue`

Entity: [`LoanAccountEventsQueueEntity.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java) (L16).

Columns: `id` (PK), `parent_account_id` (FK), **`data`** (JSON event blob), **`event_type`** (REP / FCL / WAIVER / RSTCRE / REOPN / TXNREV / PRTPRE / REBK / CANCL / LEAR / CLB / CLMT), **`event_status`** (`P` PENDING / `C` COMPLETED), `is_deleted`, `event_id`, `reference_number`, `filler_1..5`, audit cols.

Drained by [`childLoanEventProcessingBatchJob`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/childloaneventprocessingbatchjob/) — `JOB_NAME="childLoanEventProcessingBatchJob"`, `GRID_SIZE=30`, `CHUNK_SIZE=50`, cron `0 0 0/2 * * ?`. Reader filters `event_status='P' AND is_deleted=false`. Writer dispatches to the appropriate child orchestration request via internal API (e.g. `childLoanRepayment` from `group_mfi_orc.xml`).

### CLMT writer registry — disbursement state-machine

CLMT rows are the most concurrency-fraught row class in this codebase: writers across 4 thread families (orchestration, reactor, Tomcat HTTP worker, batch) on an entity with **no `@Version`**. The pre-2026-05-07 rank-guard-before-`dao.save` pattern was REPLACED by atomic CAS in PR #260 (`e3d84a53b` … `f6e83c9fe`) and finalized by `4c339282f` + `09295c377`. **Every NEFT v2 state change now goes through `ChildClmtStateMachineService.transition` (with `fromStates` derived from `ChildClmtTerminalStateGuard.rankBackwardSafeFromStates(toState)`); every error/advisory write goes through `patchJsonFields` (state-agnostic, rejects `disbursement_status` patches).** State-machine ranks: `DTFC_SUCCESS`(1) < `NEFT_STAGE_1_PENDING`(2) < `NEFT_STAGE_1_SUCCESS`(3) < `NEFT_STAGE_2_PENDING`(4) < `COMPLETED`(5). Any new state value MUST be added to `DISBURSEMENT_STATUS_RANK` in the same change.

| Writer | File:line | Thread | Guard / forward-only condition |
|---|---|---|---|
| Initial INSERT (DTFC_SUCCESS) | [`ChildLoanMoneyTransferEventsQueueDataPopulator.createEventData:50`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/disbursement/service/ChildLoanMoneyTransferEventsQueueDataPopulator.java#L50) via [`CreateClmtLoanAccountEventsProcessor.process:82`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/disbursement/processor/CreateClmtLoanAccountEventsProcessor.java#L82) | NP-Executor (orchestration) | INSERT — no race |
| Sync NEFT post-handler (success) | [`ChildNeftClmtPostBankService.applyClmtAndSave:106`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/service/ChildNeftClmtPostBankService.java#L106) | reactor-http-epoll | CAS via `transition`; `fromStates = rankBackwardSafeFromStates(nextDisbStatus)` |
| Sync NEFT post-handler (failure / parse-error) | [`ChildNeftClmtPostBankService.applyClmtAndSave:117,130`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/service/ChildNeftClmtPostBankService.java#L117) | reactor-http-epoll | `patchJsonFields` (state-agnostic; never reverts state) |
| Sync MFT post-handler (success → COMPLETED) | [`PostMFTChildLoanBankDisbursementProcessor:135`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/PostMFTChildLoanBankDisbursementProcessor.java#L135) | reactor-http-epoll | CAS via `transition` to COMPLETED (`eb69c0511`) |
| Sync MFT post-handler (failure) | [`PostMFTChildLoanBankDisbursementProcessor:145`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/PostMFTChildLoanBankDisbursementProcessor.java#L145) | reactor-http-epoll | **dao.save (NOT MIGRATED — same auto-flush race risk; documented gap)** |
| Sync inquiry response writer — failure | [`ChildDisbursementLoanEventsQueueSync.saveBankErrorResponseCode:45`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/bank/child/ChildDisbursementLoanEventsQueueSync.java#L45) | NP-Executor | `patchJsonFields` (`09295c377`) |
| Sync inquiry response writer — re-fire success | [`ChildDisbursementLoanEventsQueueSync.saveBankErrorResponseCode:57`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/bank/child/ChildDisbursementLoanEventsQueueSync.java#L57) | NP-Executor | CAS via `transition` (`ccf7f6b89` migrated `eb69c0511`) |
| Async NEF success → STAGE_1_SUCCESS | [`DoGenericSyncSTPBankNeftCallBackProcessor.processLoanAccountForChildLoans:264`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L264) | https-jsse-nio (Tomcat) | CAS via `transition`; `fromStates = {NEFT_STAGE_1_PENDING, DTFC_SUCCESS}` |
| Async NEI success → COMPLETED | [`DoGenericSyncSTPBankNeftCallBackProcessor.processLoanAccountForChildLoans:288`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L288) | https-jsse-nio (Tomcat) | CAS via `transition`; `fromStates = {NEFT_STAGE_2_PENDING, NEFT_STAGE_1_SUCCESS}` |
| Async NEI in-progress (codstatus=N) → COMPLETED | [`DoGenericSyncSTPBankNeftCallBackProcessor.processInProgressCallbackForChild:548`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L548) | https-jsse-nio (Tomcat) | CAS via `transition` (with `newEventStatus=C`) |
| Async NEI in-progress advisory (CAS rejected / ST_NEF in-progress) | [`DoGenericSyncSTPBankNeftCallBackProcessor.processInProgressCallbackForChild:559`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L559) | https-jsse-nio (Tomcat) | `patchJsonFields` (`4c339282f`) |
| Async NEF/NEI failure callback | [`DoGenericSyncSTPBankNeftCallBackProcessor.processFailedLoanAccountForChildLoans:431`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L431) | https-jsse-nio (Tomcat) | CAS via `transition` (state preserved or moved per `isDuplicateLikeNeftFailure`) |
| Async NEI in-progress (codstatus=N) → COMPLETED | [`DoGenericSyncSTPBankNeftCallBackProcessor:510`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L510) | https-jsse-nio (Tomcat) | Same broadened guard as `:502` |
| Async NEF/NEI failure callback | [`DoGenericSyncSTPBankNeftCallBackProcessor:380-394`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L380) | https-jsse-nio (Tomcat) | curStatus IN expected pre-state per branch (line 367/372) |
| Orchestration normalize (event_status only) | [`PerformChildLoanBankDisbursementProcessor:162,166,187,237`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/PerformChildLoanBankDisbursementProcessor.java#L162) | NP-Executor | Runs before async fires; only event_status / failure markers |

**Remaining gap:** `PostMFTChildLoanBankDisbursementProcessor:145` (MFT failure branch) still does `dao.save` and is subject to the same outer-tx Hibernate auto-flush race the NEFT v2 path was vulnerable to before `4c339282f`. Migration to `patchJsonFields` is the same shape as the NEFT failure-branch fix. Open — track in `gaps-and-risks.md` if it bites.

**State-machine race-class status (NEFT v2):** closed. Both the DB-side last-writer-wins (closed by atomic CAS) and the JPA-side auto-flush revert (closed by removing post-CAS in-memory mutations) no longer apply. Advisory error fields are now CAS-protected too via `patchJsonFields`.

**Why no `@Version`:** the migration was explicitly ruled out by the maintainer in this iteration. The rank-guard approach above closes every observed backward-write failure mode (the seven-iteration race-fix sequence) without DDL. If a future race emerges that the rank guard cannot express, revisit `@Version`.

---

## 9. CLB (Child Loan Booking) field propagation (2026-04-14)

`ChildLoanBookingEventsQueueDataPopulator` forwards `loan_details` → child `createOrUpdateLoanAccount` request:
- `vtc_id` → `loan_account.filler_11`
- `sourcing_emp_id`, `servicing_emp_id` → child rows

Source precedence: **member-first** (read from each `member_details[]` item when present; fallback to parent-level EC).

---

## 10. Open issues anchored to this engine (cross-link to `gaps-and-risks.md`)

1. **`entity_type` MISSING from sync payload** (re-confirmed on 3.3.1.0.1 — see §3.5 above). LOS skip stays.
2. **`stan` MISSING from sync payload** — same root cause.
3. **`dl*` Redis key has no TTL** — stale lock if JVM dies between L111 set and L235 cleanup.
4. **CRR save lock recovery → `LoanStatus=LOCK`** — needs ops reset; no automated remediation.
5. **Disburse pipe-delimited contract (`api|json|cacheKey`)** — implicit; cross-deploy-skew between LOS producer and accounting consumer is not contract-tested.
6. **No `src/test` coverage** for `LmsMessageBrokerConsumer` async path.
7. **Child MFT FAIL writer not yet on CAS** — `PostMFTChildLoanBankDisbursementProcessor` FAIL branch still uses legacy `dao.save(row)` (pre-`patchJsonFields` migration). Auto-flush race window remains for MFT-only flows. Migration deferred pending regression testing — track with `gaps-and-risks.md`.

---

## 11. 3.3.1.0.1 deltas (since 3.2.8.4.1)

The full delta narrative lives in [`../accounting/11-deltas-3.3.1.0.1.md`](../accounting/11-deltas-3.3.1.0.1.md). Disbursement-engine touch points (in commit-date order, newest last):

| Commit | Date | Effect on engine |
|---|---|---|
| `e3d84a53b … f6e83c9fe` (PR #260) | 2026-04-28 → 05-04 | Atomic-CAS redesign for CLMT + parent loan_account state. See §4.8. |
| `c704969ec` | 2026-05-06 | Closes async-NEI-callback vs sync-NEI-inquiry-post-handler race. See §4.9 last bullets. |
| `a6fdc1c88` + `55e58d31d` | 2026-05-06 → 05-07 | CLMT prep-block split + populate-before-prepare ordering. See §4.9. |
| `4c339282f` + `09295c377` | 2026-05-07 | Hibernate auto-flush race close — CAS is sole writer, advisory writes via `patchJsonFields`. See §4.8. |
| `331cd8f98` + `aaecd4fb2` | 2026-05-07 | Inquiry crash on pre-NEFT `disbursement_status` — empty-`fromStates` guard added. See §4.1 inquiry block. |
| `7ad7a0adf` | 2026-05-07 | Persist CRR locally on bank parser NPE — guarantees CRR for any malformed bank response. See §5. |
| `1671a0fad` | 2026-05-07 | **NDF / "batch not found" recovery** — parent inquiry now allows `DO_TRANSACTION=TRUE` for `DTFC_SUCCESS`; parser-NPE catch sniffs raw response for NDF; `saveBankErrorResponseCode` does **backward CAS** `NEFT_STAGE_1_PENDING → DTFC_SUCCESS` so next `disburseLoan` retry fires fresh NEF. State machine is monotonic-forward EXCEPT for this one well-defined NDF rollback. See [`../runbooks/disbursement-stuck.md`](../runbooks/disbursement-stuck.md) for the runbook. |
| `340aff84b` | 2026-05-04 | NEFT v2 globally enabled on this branch. |

---

*When editing any of: `loans_orc.xml` `disburseLoan`, `mfi_orc.xml` `disburseLoan`, `LmsMessageBrokerConsumer`, `CallBankAPIFor*Processor`, NEFT v2 services, `ClientRequestResponseLogDAOService`, or any constant in `DisbursementBankCallConstants` — update this file and bump the changelog.*
