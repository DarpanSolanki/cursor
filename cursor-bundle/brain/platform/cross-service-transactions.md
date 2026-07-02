# Cross-Service Transaction Map

**Purpose:** Operations spanning **2+ services** without a formal **saga** (no guaranteed compensating transactions across boundaries). **Flow Sync Wave 4** (2026-04-17) — synthesizes Waves 1–4 + code evidence.

**Legend:** **Compensation** = automated undo in callee or caller; **Reconciliation** = batch/report/ops queue that detects and fixes drift; **Monitoring** = alerts/dashboards on stuck states (beyond plain logs).

---

## Every operation that spans 2+ services

### TRANSACTION: Async disbursement (LOS → Kafka → Accounting → Kafka → LOS)

| Field | Detail |
|-------|--------|
| **Services** | LOS, Kafka, Accounting, (Bank external), LOS |
| **Happy path** | LOS persists process state → Redis guard → Kafka `disburse_loan_api_` → Accounting consumes → `disburseLoan` orchestration → bank / book → `los_lms_disbursement_sync` → LOS consumer updates failure_reason on FAILED |
| **Failure scenarios** | **Step:** Kafka send swallowed (**GAP-019**) → **State:** LOS thinks queued, message never arrives. **Step:** Accounting fatal after partial DB → **State:** loan/CRR inconsistent. **Step:** Result Kafka missing `entity_type` (and `stan`) → **State:** LOS skips sync update + weak async correlation. **Step:** Accounting skip branch (`LOCK`/`CACHE`) without sync publish → **State:** LOS process appears stuck/in-progress. |
| **Compensation** | **MISSING** (no cross-service saga) |
| **Reconciliation** | **PARTIAL** — ops, Redis key cleanup, CRR/bank inquiry, manual replay |
| **Monitoring** | **PARTIAL** — logs, stuck disbursement statuses; no universal alert spec in-repo |
| **Risk** | **High** |

---

### TRANSACTION: Scheduled LMS EOD job chain (Batch → Accounting internal APIs)

| Field | Detail |
|-------|--------|
| **Services** | Batch platform, Accounting (multiple Spring Batch jobs via `callInternalAPI`) |
| **Happy path** | Batch `callJobAPi` sets `job_time` from business date → Accounting job runs readers/writers → nested `postTransaction` where applicable |
| **Failure scenarios** | **Step:** Two batch nodes start same job (**multi-node gap**) → **State:** duplicate chunk processing / double posting risk on weak idempotency. **Step:** HTTP timeout from batch to accounting → **State:** Spring Batch execution vs accounting unclear |
| **Compensation** | **MISSING** cluster-wide |
| **Reconciliation** | **PARTIAL** — Spring Batch restart, `batch_failure_audit`, finance recon |
| **Monitoring** | **PARTIAL** — job success/fail in batch tables |
| **Risk** | **High** (duplicate scheduler) / **Medium** (single instance) |

---

### TRANSACTION: Interest accrual posting (Accounting batch → `postTransaction`)

| Field | Detail |
|-------|--------|
| **Services** | Accounting batch service, Accounting ledger engine (same JVM, **separate txn** per internal API contract) |
| **Happy path** | Reader selects accrual rows → `InterestAccrualBookingBatchService.doInterestBooking` → `postTransaction` |
| **Failure scenarios** | **Step:** `postTransaction` succeeds, writer fails before accrual row update → **State:** ledger posted, accrual marker stale (or vice versa). **Step:** Retry with **new** `client_reference_number` → **State:** double ledger (**GAP** time-based CRR) |
| **Compensation** | **MISSING** automatic reverse in batch |
| **Reconciliation** | **PARTIAL** — trial balance, accrual vs GL reports |
| **Monitoring** | **PARTIAL** |
| **Risk** | **High** |

---

### TRANSACTION: Collections partner sync (Payments → Accounting HTTP)

| Field | Detail |
|-------|--------|
| **Services** | Payments, Accounting |
| **Happy path** | Payments persists collection + refs → `collectionLoanRepayment` (retry) → accounting updates loan → payments marks SYNCED |
| **Failure scenarios** | **Step:** Accounting fails after max retries → **State:** payments **SYNC_FAILED**, accounting may lack repayment posting |
| **Compensation** | **MISSING** auto-rollback of payments money rows |
| **Reconciliation** | **EXISTS** — `CollectionExternalSystemUpdateStatusEntity`, `PushPendingLMSUpdatesItemWriter`, partner sync status |
| **Monitoring** | **PARTIAL** — SYNC_FAILED counts |
| **Risk** | **Medium** |

---

### TRANSACTION: SHG child repayment propagation (Payments/Accounting parent API + Accounting async child batch)

| Field | Detail |
|-------|--------|
| **Services** | Payments, Accounting API, Accounting Batch |
| **Happy path** | Payments sends `loanRepayment` on parent with `child_loans[]` → parent posts successfully → `childLoanRepaymentEventGenerationProcessor` enqueues child events in `loan_account_events_queue` → `childLoanEventProcessingBatchJob` executes `childLoanRepayment` (`group_mfi_orc.xml`) → child posting + dues update complete |
| **Failure scenarios** | **Step:** parent mode mapping added but child mode mapping missing in `group_mfi_orc.xml` (for example `DIGITAL`) → **State:** child `postTransaction` receives unresolved `${transaction_type}`/`${transaction_sub_type}` and fails with `Invalid transaction_type and/or transaction_sub_type`; parent appears settled while child is not impacted |
| **Compensation** | **MISSING** cross-leg rollback (parent success does not auto-reverse on child async failure) |
| **Reconciliation** | **REQUIRED** — monitor queue retries and compare parent vs child settlement state |
| **Monitoring** | **REQUIRED** — alert on repeated `childLoanEventProcessingBatchJob` failures for same queue item |
| **Risk** | **High** |

Pre-release linkage checklist for SHG repayment mode changes:

- Mode mapping present in `mfi_orc.xml`, `loans_orc.xml`, and `group_mfi_orc.xml`.
- Child batch logs show concrete `transaction_type/sub_type` values (not placeholders).
- `transaction_catalogue` + `transaction_accounting_rule` rows exist for new subtype.
- One E2E SHG run validates both parent and child LAN impact.

---

### TRANSACTION PATTERN: Parent sync + child async (generic template)

| Field | Detail |
|-------|--------|
| **Pattern** | Parent API succeeds synchronously, child work runs asynchronously from queue/batch |
| **Typical modules** | Group loans, parent-child disbursement, repayment, waiver, restructuring, closure, reversal |
| **Hidden risk** | Parent leg green while child leg fails later (false-positive release confidence) |
| **Primary failure signatures** | Queue stuck in `P`, repeated child batch retries, unresolved placeholders in child API payload, parent-child state mismatch |
| **Control objective** | No release signoff unless both legs pass in same scenario |

Release checklist (apply to every parent-child event, not only repayment):

- Parent and child orchestration have equivalent mapping for newly introduced event/mode/subtype conditions.
- Child batch contract is validated (event queue rows created, picked, and terminalized correctly).
- Child downstream dependencies are validated (catalogue/rules/masterdata/bank contracts if event posts transactions).
- Regression includes at least one multi-child scenario to confirm all children process, not first-child-only.

---

### TRANSACTION: Bulk collection pipeline (Accounting batch → Kafka → Payments)

| Field | Detail |
|-------|--------|
| **Services** | Accounting, Kafka, Payments |
| **Happy path** | `LoanRecurringPaymentItemWriter` publishes `bulk_collection_data_` → Payments consumer creates/updates collections |
| **Failure scenarios** | **Step:** Producer swallow (**GAP-019**) → **State:** accounting thinks published, LCS missing rows. **Step:** Consumer parse/null list (**GAP-044/064**) |
| **Compensation** | **MISSING** |
| **Reconciliation** | **PARTIAL** — collection vs due recon; failed-record topic consumer weak (**GAP-036**) |
| **Monitoring** | **PARTIAL** |
| **Risk** | **High** |

---

### TRANSACTION: Business date advance (Masterdata batch → configuration cache)

| Field | Detail |
|-------|--------|
| **Services** | Masterdata, Redis cache, all consumers of `current.business.date` |
| **Happy path** | `updateBusinessDate` job updates config → batch scheduler **removes** cache key before reading date (`SchedulerCommonService.setJobTime`) |
| **Failure scenarios** | **Step:** Cache stale if other paths skip invalidation (**GAP-029** masterdata invalidation non-fatal) → **State:** wrong business date in postings |
| **Compensation** | **MISSING** |
| **Reconciliation** | **PARTIAL** — ops correct date, replay |
| **Monitoring** | **PARTIAL** |
| **Risk** | **Medium** |

---

### TRANSACTION: Death-foreclosure insurance inbound (Task + Accounting batch)

| Field | Detail |
|-------|--------|
| **Services** | Accounting batch, Task (`updateTaskWorkflow` / `deleteTask`), possibly Actor |
| **Happy path** | Writer posts transactions + updates task workflow |
| **Failure scenarios** | **Step:** Task updated, accounting chunk rolls back → **State:** staging poison / blocked batch (**documented High gap**) |
| **Compensation** | **MISSING** |
| **Reconciliation** | **PARTIAL** — manual staging cleanup |
| **Monitoring** | **PARTIAL** |
| **Risk** | **High** |

---

### TRANSACTION: Loan auto-closure (Accounting batch → DB + Kafka LOS)

| Field | Detail |
|-------|--------|
| **Services** | Accounting, Kafka, LOS |
| **Happy path** | Reader picks **ACTIVE** loans → writer closes → `los_lms_data_sync_` with `entity_type` |
| **Failure scenarios** | **Step:** Writer **catch** swallows → **State:** some loans closed, others not (**existing High**). **Step:** Kafka publish fails silently |
| **Compensation** | **MISSING** |
| **Reconciliation** | **PARTIAL** — loan status vs LOS |
| **Monitoring** | **PARTIAL** |
| **Risk** | **High** |

---

### TRANSACTION: Actor/Masterdata reads during accounting API (synchronous)

| Field | Detail |
|-------|--------|
| **Services** | Accounting, Actor, Masterdata |
| **Happy path** | `getCustomerDetails`, `getOfficeDetails`, `getBankDetails`, etc. populate EC before posting/validation |
| **Failure scenarios** | **Step:** Callee timeout/fatal → **State:** request fails; **no** silent money movement if fatal propagates. **Step:** Cached masterdata wrong (**GAP-029**) → **State:** wrong validation or narrative, potential mis-posting if defaults wrong |
| **Compensation** | **N/A** (read path) |
| **Reconciliation** | **PARTIAL** — audit of posted vs master |
| **Monitoring** | **PARTIAL** |
| **Risk** | **Low–Medium** per call (fatal = fail-fast; cache = subtle) |

---

### TRANSACTION: Portfolio / GL transfer (Accounting → nested internal APIs)

| Field | Detail |
|-------|--------|
| **Services** | Accounting, Actor (`doGLTransfer` target service per registry) |
| **Happy path** | Orchestration calls `doGLTransfer` then local posting |
| **Failure scenarios** | Partial completion across internal API boundaries |
| **Compensation** | **PARTIAL** — reversal patterns if implemented in flow |
| **Reconciliation** | **EXISTS** — GL vs sub-ledger |
| **Monitoring** | **PARTIAL** |
| **Risk** | **Medium** |

---

## Summary counts (Wave 4)

| Category | Count |
|----------|------:|
| **Transactions mapped (this file)** | **10** |
| **High risk (money or closure at stake + weak automation)** | **6** |
| **With meaningful reconciliation artifact** | **4** |

**No new High gap IDs** were minted solely from this map — items align with existing `.cursor/gaps-and-risks.md` rows (disburse Redis/`entity_type`, Kafka swallow, batch multi-node, time-based CRR, auto-closure writer, DCF insurance, bulk collection consumer).

**Wave 6 code evidence — Compensation: MISSING (platform):** Cross-service HTTP uses `NovopayHttpAPIClient` single `execute` with no automatic compensating callback (`novopay-platform-lib/infra-http-client/.../NovopayHttpAPIClient.java`); `NovopayInternalAPIClient` does not implement saga/outbox. Each row’s **Compensation: MISSING** therefore means **no automated cross-service undo** in-repo — recovery is **Reconciliation** / **Monitoring** / ops (per-row narrative above).
