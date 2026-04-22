# Inter-service contracts — summary for agents

**Rule**: Treat every contract as **additive-only** unless explicitly approved; grep **all** callers. See `.cursor/rules/api-contract-safety.mdc`.

## HTTP API surface

- **Naming**: `apiName` in path `/api/v1/{apiName}` matches `Request @name` in orchestration XML for that service.
- **Body**: Standard header fields (`tenant_code`, `stan`, `user_handle_value`, …) + service-specific `request` object — exact shape from JTF/API templates under `deploy/application/templates/` and codegen docs `trustt-platform-ai-codegen-artifacts-java/sli/api-documentations/`.
- **Response**: `response_status.status` (`SUCCESS`/`FAIL`), `error_code`, service payload keys — **do not remove or repurpose** keys other modules read.

## Internal API calls

- Implemented via `NovopayInternalAPIClient`:
  - **Same-service optimization**: `NovopayInternalAPIClient#doSameServiceCall(...)` re-populates a new `ExecutionContext` and calls `ServiceOrchestrator.processRequest(...)` with **explicit transaction management** (no HTTP hop).
  - **Cross-service HTTP**: otherwise delegates to `NovopayHttpInternalAPIClient` → `NovopayHttpAPIClient` which POSTs `/{endpoint}/api/{version}/{apiName}` using Apache `CloseableHttpClient`.
- **Auth header (inter-service trust)**: `NovopayHttpAPIClient` injects `Authentication` (OTP) + `Originator` headers before call (see `SecurityManager#getOTP(...)` usage).
- **Timeouts**:
  - Default connect/socket timeouts: `novopay.internal.api.connection.timeout`, `novopay.internal.api.socket.timeout` (both default to `120000` in `NovopayHttpAPIClient`).
  - Per-call overrides are passed through from orchestration `<API connectionTimeout="..." socketTimeout="...">` → `ProcessorOrchestrator#processInternalAPI(...)`.
- **Resilience (code-verified)**:
  - **No built-in retry/circuit-breaker** in `NovopayHttpAPIClient` (single execute; errors mapped to `NovopayFatalException` via `NovopayRequestResponseTemplateUtil#getNovopayErrorCode(...)`).
  - Retries **do** exist for some DB-write paths (example: `ClientRequestResponseLogDAOService#save(...)` uses `@Retryable` for lock acquisition failures).
- **Transaction**: callee commits independently; caller must handle partial failure (compensation, idempotent retry, or explicit reconciliation).

---

## Accounting-v2 Kafka config (verbatim structure from repo)

File: `novopay-platform-accounting-v2/deploy/application/messagebroker/MessageBroker.xml`

**Producers** (enabled in file):

| producerId | Typical use |
|------------|-------------|
| `producer_id_accounting` | Declared in XML; `NovopayKafkaProducer` sends with **topic built at runtime** (`AccountingKafkaProducer#pushDataToKafkaQueue` appends `tenantCode` + optional `_environment`) — exact topic strings per flow (e.g. disburse sync) live in producer call sites |
| `bulk_collection_data_` | Bulk collection pipeline |

**Consumers**:

| topicPrefix | bean | consumersGroupIdPrefix |
|-------------|------|-------------------------|
| `bulk_collection_data_failed_` | `bulkCollectionFailedRecordConsumer` | `bulk_collection_failed_record_consumer` |
| `disburse_loan_api_` | `lmsMessageBrokerConsumer` | `disburse_loan_api_consumer_` |

Tenant/environment suffixing is applied by the message-broker framework at runtime (see infra-message-broker and `system_brain/events/kafka_topics.md`).

---

## Cross-service Kafka contracts (high-value)

| Direction | Topic pattern (typical) | Payload essentials |
|-----------|-------------------------|-------------------|
| LOS → Accounting | `disburse_loan_api_<tenant>[_env]` | `disburseLoan\|{json}\|{cacheKey}` |
| Accounting → LOS | `los_lms_disbursement_sync` | `external_ref_number`, `status`, `error_code`, … — LOS may require **`entity_type`** for some updates |
| Accounting → LOS | `los_lms_data_sync_` | Closure: `external_ref_id`, `entity_type`, `event_type=CLOSURE` |
| Collections pipeline | `bulk_collection_data_`, `collection_primary_allocation_`, … | `system_brain/events/kafka_topics.md` |
| Notifications | `notification_sms_` | `notification_code`, `msisdn`, `locale`, … |

---

## Shared types / DTOs

- **Location**: `infra-*` client modules, shared entities in service JARs consumed by other services, JSON maps through ExecutionContext.
- **Versioning**: No universal schema registry in-repo; compatibility is enforced by **integration tests and caller greps**.

## ExecutionContext keys (contract between processors)

- Not HTTP-visible but **are** contracts **within** a flow and sometimes across internal API boundaries when maps are copied.
- Document new keys when adding processors; never overwrite shared keys unintentionally (`.cursor/rules/execution-context-discipline.mdc`).

## Database as implicit contract

- Other services and reports query accounting tables by column semantics (e.g. `paid_amount` vs `waived_amount`). Schema changes require migration + downstream impact analysis.

---

*Table-level detail: `trustt-platform-ai-codegen-artifacts-java/sli/schema_structure/data_dictionaries/mfi_accounting_data_dictionary.md`.*

---

## HTTP Contract Registry — Accounting [2026-04-17]

**Wave 2 note:** Field-by-field request/response typing for **every** `apiName` is defined by **JTF templates** under `deploy/application/templates/` and codegen `trustt-platform-ai-codegen-artifacts-java/sli/api-documentations/` — not duplicated here. Below: **transport behaviour** (verified in platform-lib) + **inventory** of accounting **`NovopayInternalAPIClient.callInternalAPI`** usage + **inbound** pattern.

### HTTP CONTRACT: accounting → [any remote service via `NovopayInternalAPIClient`]

**API:** `apiName` + `v1` (typical) — resolved to host via `ServiceRegistry.getAPIEndpoint(apiName)` (`NovopayHttpAPIClient` L54-L61).  
**Request fields:** Built from **merged** `ExecutionContext` shared + local maps via `JSONHelperForAPIRequestAsJSONString` (`NovopayHttpInternalAPIClient` L50-L73). Includes `Authentication` header from map (`NovopayHttpInternalAPIClient` L80) — must be populated for cross-service trust.  
**Response fields:** Parsed into `apiResponseMap` with keys from response template — at minimum `status`, `code`, `message` for FAIL handling (`NovopayHttpInternalAPIClient` L93-L97).  
**Null-safe on response:** **Partial** — `parseAPIResponse` / template driven; FAIL throws after parse.  
**Timeout configured:** **Y** — orchestration may pass `connectionTimeout` / `socketTimeout`; **`-1`** → defaults `novopay.internal.api.connection.timeout` / `socket.timeout` (**120000** ms each) (`NovopayHttpAPIClient` L46-L50, L78-L84).  
**Retry exists:** **N** at HTTP client layer (single `httpClient.execute`) — see summary-table row **HTTP internal client has no retry/circuit breaker**.  
**What happens on timeout:** `SocketTimeoutException` propagated from `handleHTTPCallExceptions`; outer `callAPI` catch wraps via `NovopayRequestResponseTemplateUtil.getNovopayErrorCode` → **`NovopayFatalException`** (`NovopayHttpAPIClient` L86-88, L131-141).  
**What happens on 5xx / non-200:** `NovopayHttpInternalAPIClient` L82-L84 → `createExceptionByHttpStatus` → **fatal** (body may be null).  
**Contract verified:** **DRIFT** — resilience (no retry/circuit breaker) documented as platform risk; per-`apiName` body alignment requires template grep.  
**Drift detail:** Callers using `-1,-1` timeouts always get **120s** defaults regardless of callee SLA variance.

### HTTP CONTRACT: accounting → accounting (same-service `doSameServiceCall`)

**API:** Any `apiName` registered to **accounting** in `ServiceRegistry`.  
**Mechanism:** `NovopayInternalAPIClient#doSameServiceCall` — new `ExecutionContext` from merged maps + `ServiceOrchestrator.processRequest` — **no HTTP** (`NovopayInternalAPIClient` L71-L98).  
**On callee FAIL:** Reads `status` / `code` / `message` from child context → **`NovopayFatalException`**.  
**Contract verified:** ✅ **ALIGNED** with documented same-service optimisation; EC key **copy semantics** are the hidden contract (parent must have set all keys callee validators need).

### HTTP CONTRACT: accounting → actor / masterdata / task / payments (representative outbound `apiName` inventory)

**Evidence:** `grep '.callInternalAPI(' novopay-platform-accounting-v2/src/main/java` — **~95+ files** / **100+ call sites** (Wave 2 count). Representative `apiName` strings:

- **Actor / customer / office:** `getCustomerDetails`, `getOfficeDetails`, `getActorDetailsForAccount`, `getOfficeList`, `getEmployeeServiceableOffices`, `getUserDetails`, `getBranchDetails`, `submitAccountDetails`, `validateIFSC` (patterns), `getMasterDataDetails`, …  
- **Task:** `updateTaskWorkflow`, `deleteTask`, `getTaskDetails`, `createAndCompleteTask` (via common processors), …  
- **Masterdata / bank:** `getBankDetails`, `getDatatypeMaster`, `getChildElementsByHierarchyLevel`, …  
- **Payments / collection:** `loanAccountCollection`, …  
- **Self (nested):** `postTransaction`, `reverseTransaction`, `loanRepayment`, `interestAccrualCalculation`, `interestAccrualPosting`, `doGLTransfer`, `postManualJournalEntry`, `loanAccountRebooking`, `fetchLoanForeclosureSimulationDetails`, …  

**Per-call field matrix:** **Deferred** — each pair `(apiName, caller processor)` maps to JTF; use codegen + template path when changing.

### HTTP CONTRACT: * → accounting (inbound)

**API:** Any `<Request name="X">` exposed as `POST .../api/v1/{X}` via **`ServiceGatewayController`** (platform-lib) when routing to accounting tenant.  
**Request fields:** SOF envelope + `request` object — parsed into `ExecutionContext` by **`defaultExecutionContextPopulator`**.  
**Response fields:** `response_status`, `error_code`, payload keys per response template — **must remain additive-only** per `api-contract-safety.mdc`.  
**Null-safe:** Template-dependent.  
**Timeout:** Ingress HTTP server / gateway; not `NovopayInternalAPIClient`.  
**Retry:** Not automatic on accounting HTTP ingress.  

**CONTRACT MATCH CHECK (pattern-level):**

| Caller sends | Accounting expects |
|--------------|-------------------|
| JSON keys per caller’s client template | First processor + validators in orchestration `Request` for that `apiName` — often **different key names** than HTTP JSON (JTF maps to EC keys) |
| **Mismatch hunting** | Requires per-flow template diff — **Wave 3** LOS/Payments focus |

**Contract verified:** **DRIFT** — global pattern known-good; **per-apiName** not fully diffed in Wave 2.

---

## Kafka transport note (accounting producers)

`AccountingKafkaProducer` / `LoanClosureKafkaProducer` delegate to **`NovopayKafkaProducer.sendMessage`**. On send failure, outer **catch logs only** — caller does not receive exception (**silent from caller POV**); aligns with **GAP-019** (platform producer swallow) — see `NovopayKafkaProducer.java` L137-L139.

---

## Flow Sync Wave 3 — LOS + Payments ↔ Accounting [2026-04-17]

**Full narrative:** `.cursor/accounting-flows.md` sections **LOS ↔ Accounting Complete Contract** and **Payments ↔ Accounting Complete Contract**.

### LOS → Accounting (HTTP inventory)

| apiName | LOS evidence file |
|---------|-------------------|
| `getLoanProductDetails` | `AccountingUtil.java`, `CommonUtil.java` |
| `getLoanProductList` | `AccountingUtil.java` |
| `getLoanAccountOverviewDetails` | `AccountingUtil.java` |
| `getLoanAccountList` | `AccountingUtil.java` |
| `getInsurancePremiumAmount` | `AccountingUtil.java` |
| `generateRepaymentSchedule` | `AccountingUtil.java` |
| `checkInsuranceProductGeoEligibility` | `AccountingUtil.java` |
| `calculateStampDutyCharges` | `AccountingUtil.java` |
| `fetchLoanAccountChargeDetails` | `AccountingUtil.java` |
| `getBulkLoanAccountDetails` | `AccountingUtil.java` |
| `getChildLoanAccountList` | `AccountingUtil.java` |
| `updateChildLoanDisbursementStatus` | `AccountingUtil.java` |
| `updateLoanAccountPreDisbursementDetails` | `AccountingUtil.java`, `PrepareDisburseLoanAPIRequestService` (indirect) |
| `getEffectiveInterestRateForInterestSetupCode` | `AccountingUtil.java` |
| `getWorkingDays` | `AccountingUtil.java` |
| `getHolidayList` | `AccountingUtil.java` |
| `getLoanAccountDetails` | `LoanAccountStatusEnquiryAPIUtil.java` |
| `getLoanAccountDerivedData` | `CommonUtil.java` |
| `getCustomerLoanAccountBounces` | `CommonUtil.java` |
| `disburseLoanAudit` | `CommonUtil.java` |

### Accounting → LOS

- **HTTP:** none code-verified from `novopay-platform-accounting-v2` → LOS module.
- **Kafka:** `los_lms_disbursement_sync` (disburse result), `los_lms_data_sync_` (closure — includes **`entity_type`**).

### LOS → Accounting (Kafka)

| Topic | Payload spine | `entity_type` |
|-------|----------------|---------------|
| `disburse_loan_api_` | `disburseLoan\|{json}\|{cacheKey}` | **Y** (`PrepareDisburseLoanAPIRequestService.java` L148-L149) |

### Payments → Accounting (HTTP inventory)

| apiName | Payments evidence |
|---------|---------------------|
| `collectionLoanRepayment` | `MfiCollectionsDAOService.java`, `PushLMSUpdateProcessor.java` |
| `loanPrepayment` | `MfiCollectionsDAOService.java` |
| `loanAccountPartPrepayment` | `MfiCollectionsDAOService.java` |
| `loanDisbursementCancellation` | `MfiCollectionsDAOService.java` |
| `updateCollectionBatchDetails` | `MfiCollectionsDAOService.updateBatchExpirationToLMS` |
| `loanRepayment` | `SGToNpHandoffIWriter.java` |

### Accounting → Payments (Kafka)

| Topic | Producer | Consumer |
|-------|----------|----------|
| `bulk_collection_data_` | `LoanRecurringPaymentItemWriter.java` | `CreateOrUpdateBulkCollectionConsumer.java` |

**Contract checks:** disburse sync **`entity_type`** = **MISMATCH** (existing summary rows). Bulk consumer parse/null **`collection_list`** = **GAP-044**, **GAP-064**.

---

## Actor + Masterdata Contracts [2026-04-17]

**Scope:** `NovopayInternalAPIClient` usage from **`novopay-platform-accounting-v2`** to **Actor**-hosted and **Masterdata**-hosted `apiName` values (grep pass + representative reads). **Not** an exhaustive line-by-line audit of every processor.

### Business date / cache (affects all financial timestamps)

| Mechanism | Evidence | TTL / invalidation | If stale or service down |
|-----------|----------|---------------------|---------------------------|
| **`PlatformDateUtil.getBusinessDateInLong()`** | Used across posting (`CreateTransactionMasterProcessor`, `ReverseTransactionProcessor`, repayment validators, batch processors) | Backed by masterdata **`current.business.date`** in Redis (`ConfigValue` pattern) | Wrong **business_date** / **value_date** on transactions — **financial correctness risk** |
| **Batch scheduler** | `SchedulerCommonService.setJobTime` **removes** Redis key then reads business date (`SchedulerCommonService.java` L291-L297) | Forces refresh on **job start** for batch-triggered paths | Other entry paths may still read **stale** cache if invalidation missed — **GAP-029** |

### Actor service — representative `apiName` inventory (from accounting)

| apiName | Example caller | Financial use |
|---------|----------------|---------------|
| `getCustomerDetails` | `GetLoanAccountDetailsProcessor`, disburse processors, foreclosure, NOC, mandate, notifications writers | KYC/narration/routing; **indirect** money impact if wrong party |
| `getActorDetailsForAccount` | `GetLoanAccountDetailsProcessor`, `PopulateLoanAccountCollectionRequestProcessor` | Account-party linkage |
| `getOfficeDetails` / `getOfficeList` | Loan details, SG JE writer, HDFC integration | Office routing for GL / charges |
| `getBranchDetails` | Repayment validation, mandate update | Branch validation |
| `submitAccountDetails` / `submitSavingsAccountDetails` | Mandate processors | Account setup |
| `getUserDetails` | Collection batch, prepayment | User context |
| `updateMFICustomerDetails` | `CustomerUtil` | Customer sync |
| `getEmployeeServiceableOffices` | Standing instruction processor | Scope validation |
| `getTaskDetails` / `updateTaskWorkflow` / `deleteTask` | Foreclosure, death-foreclosure, waiver, excess refund | **Workflow vs ledger** cross-service risk |

**When Actor is down:** Internal API → **`NovopayFatalException`** (typical); request **fails** — **no** silent default for these calls in the grep-reviewed paths.

### Masterdata service — representative `apiName` inventory

| apiName | Example caller | Financial use |
|---------|----------------|---------------|
| `getBankDetails` | Death claim form preprocessor | Bank metadata |
| `getDatatypeMaster` | SI presentation batch | Reference data |
| `getMasterDataDetails` | Product code list processor | Product metadata |
| `getChildElementsByHierarchyLevel` | Stamp duty processor | Hierarchy-driven charges |
| `getActiveOfficeIdsWithExternalBranchCodes` | SI presentation batch | Office mapping |
| `getTransactionLimitDetails` | Product scheme processors | **Limit enforcement** — can block or allow postings |

**When Masterdata is down:** Same **fatal** pattern; limits/validation may **fail closed** (preferred) vs **wrong** cached config (**GAP-029** invalidation non-fatal).

### Contract count (approximate distinct `apiName` strings)

| Target | Count (order-of-magnitude) |
|--------|----------------------------|
| **Actor-facing** | **~18–25** distinct names in accounting grep sample |
| **Masterdata-facing** | **~8–15** distinct names |

**Cross-service map:** `.cursor/cross-service-transactions.md` § Actor/Masterdata reads.

---

## Contract Health Summary [2026-04-17]

**Scope:** Representative **16** cross-cutting edges from `.cursor/knowledge-graph.md` (full HTTP fan-out = per-`apiName` × caller matrix — not expanded). Kafka topic inventory **146**; HTTP unique `apiName` union **1797** (`.cursor/api-catalogue.md`).

| Total (rep. edges) | Aligned | Drift | Mismatch | Fixed this wave |
|--------------------|---------|-------|----------|-----------------|
| 16 | 2 | 11 | 2 | 0 |

**Notes:** **`entity_type`** on `los_lms_disbursement_sync` remains **MISMATCH** (producer `LmsMessageBrokerConsumer` vs LOS `DisbursementSyncService`). Transport **DRIFT** (no HTTP retry/circuit breaker, default timeouts) dominates the HTTP surface. Wave 6 added **GAP-065..069** (observability, pipe envelope, retry/idempotency documentation) — not “fixed”, documented.

