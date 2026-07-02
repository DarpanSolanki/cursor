# Inter-service contracts — summary for agents

**Rule**: Treat every contract as **additive-only** unless explicitly approved; grep **all** callers. See `.cursor/rules/api-contract-safety.md`.

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
- Document new keys when adding processors; never overwrite shared keys unintentionally (`.cursor/rules/execution-context-discipline.md`).

## Database as implicit contract

- Other services and reports query accounting tables by column semantics (e.g. `paid_amount` vs `waived_amount`). Schema changes require migration + downstream impact analysis.

---

*Table-level detail: `trustt-platform-ai-codegen-artifacts-java/sli/schema_structure/data_dictionaries/mfi_accounting_data_dictionary.md`.*
