# Platform Knowledge Graph

**Center:** `novopay-platform-accounting-v2`  
**Generated:** 2026-04-17  
**Companion:** `.cursor/knowledge-graph.mmd` (Mermaid), `.cursor/api-catalogue.md`, `.cursor/cross-service-transactions.md`

---

## Node Registry

| Node ID | Type | Name | Description | Risk level |
|---------|------|------|-------------|------------|
| SVC-ACC | SERVICE | novopay-platform-accounting-v2 | Ledger, loans, batches, Kafka consumers | **High** (money system of record) |
| SVC-LOS | SERVICE | novopay-mfi-los | Origination, disburse orchestration | **High** |
| SVC-PAY | SERVICE | novopay-platform-payments | Collections, cash | **High** |
| SVC-ACT | SERVICE | novopay-platform-actor | Customers, offices, actors | **Medium** |
| SVC-MD | SERVICE | novopay-platform-masterdata-management | Business date, reference data | **High** (SPOF for date) |
| SVC-BAT | SERVICE | novopay-platform-batch | Scheduler → internal API job start | **High** (duplicate-run) |
| SVC-TASK | SERVICE | novopay-platform-task | Workflow tasks | **Medium** |
| SVC-NOT | SERVICE | novopay-platform-notifications | SMS/email/FCM | **Medium** |
| SVC-AUTHZ | SERVICE | novopay-platform-authorization | Permissions | **High** |
| SVC-APP | SERVICE | novopay-platform-approval | Maker-checker | **Medium** |
| SVC-AUD | SERVICE | novopay-platform-audit | Audit trail | **Low** |
| SVC-DMS | SERVICE | novopay-platform-dms | Documents | **Medium** |
| SVC-GW | SERVICE | novopay-platform-api-gateway | Ingress, forward routes | **High** |
| SVC-RPT | SERVICE | trustt-platform-reporting | Reports | **Low** |
| LIB-PLAT | PLATFORM_LIB | novopay-platform-lib | Gateway, orchestration, HTTP client, Kafka wrapper | **High** |
| DB-ACC | DB_SCHEMA | mfi_accounting (Yugabyte) | loan_account, transaction_*, GL | **High** |
| DB-LOS | DB_SCHEMA | LOS DB | loan_app, disburse_process | **High** |
| DB-PAY | DB_SCHEMA | Payments DB | collections_* | **High** |
| RD-BD | REDIS_KEY_GROUP | current.business.date | Masterdata cache; cleared on batch job start | **High** |
| RD-DISB-LOS | REDIS_KEY_GROUP | disburseLoan* / in_progress | LOS producer dedupe | **High** (no TTL) |
| RD-DISB-ACC | REDIS_KEY_GROUP | dl* | Accounting consumer in-flight | **High** (no TTL) |
| K-DISB-REQ | KAFKA_TOPIC | disburse_loan_api_* | LOS → Accounting async disburse | **High** |
| K-DISB-SYNC | KAFKA_TOPIC | los_lms_disbursement_sync | Accounting → LOS result | **High** (**mismatch**) |
| K-DATA-SYNC | KAFKA_TOPIC | los_lms_data_sync_* | Closure sync | **Medium** |
| K-BULK | KAFKA_TOPIC | bulk_collection_data_* | Accounting → Payments due pipeline | **High** |
| K-BULK-FAIL | KAFKA_TOPIC | bulk_collection_data_failed_* | Failed bulk records | **Medium** |
| K-NOT-SMS | KAFKA_TOPIC | notification_sms_* | Customer comms | **Low** |
| BAT-ACC-71 | BATCH_JOB | accounting *BatchConfigService* | 71 Spring Batch entry points in ACC | **High** |
| SCH-BAT | SCHEDULER | batch_schedule cron | DB-driven EOD triggers | **High** |

**Kafka (full topic inventory):** **146** sections in `.cursor/event-registry.md` — only **money-critical** topics are expanded as nodes above; treat **KAFKA_TOPIC** as **146** discoverable entries linked from the registry.

**Total explicit nodes in this table:** **29** (+ **146** topic refs via registry).

---

## Edge Registry

| Edge ID | From | To | Protocol | Contract | Data direction | Gap ref |
|---------|------|-----|----------|----------|----------------|---------|
| E1 | SVC-GW | SVC-ACC | HTTP_SYNC | DRIFT (timeouts, no retry) | Inbound API | HTTP client gap |
| E2 | SVC-GW | *all SVC* | HTTP_SYNC | DRIFT | Ingress | GAP-054/055 |
| E3 | SVC-LOS | SVC-ACC | HTTP_SYNC | DRIFT | Outbound internal | — |
| E4 | SVC-LOS | K-DISB-REQ | KAFKA_ASYNC | ALIGNED (payload); producer **DRIFT** (key null) | Produce | GAP-038,019 |
| E5 | K-DISB-REQ | SVC-ACC | KAFKA_ASYNC | DRIFT (Redis TTL) | Consume | disburse gaps |
| E6 | SVC-ACC | K-DISB-SYNC | KAFKA_ASYNC | **MISMATCH** (`entity_type`) | Produce | entity_type rows |
| E7 | K-DISB-SYNC | SVC-LOS | KAFKA_ASYNC | **MISMATCH** | Consume | DisbursementSyncService |
| E8 | SVC-ACC | K-DATA-SYNC | KAFKA_ASYNC | ALIGNED | Produce | GAP-019 |
| E9 | SVC-PAY | SVC-ACC | HTTP_SYNC | DRIFT | collectionLoanRepayment | HTTP |
| E10 | SVC-ACC | K-BULK | KAFKA_ASYNC | DRIFT (producer swallow) | Produce | GAP-019 |
| E11 | K-BULK | SVC-PAY | KAFKA_ASYNC | DRIFT (consumer parse) | Consume | GAP-044,064 |
| E12 | SVC-BAT | SVC-ACC | HTTP_SYNC | DRIFT | START batch job | multinode |
| E13 | SVC-ACC | SVC-ACT | HTTP_SYNC | DRIFT | getCustomerDetails… | — |
| E14 | SVC-ACC | SVC-MD | HTTP_SYNC | DRIFT | getBankDetails… | GAP-029 |
| E15 | SVC-BAT | SVC-MD | REDIS_SHARED | DRIFT | clear business date cache | — |
| E16 | LIB-PLAT | * | PLATFORM_LIB | DRIFT | EC, templates, Kafka | GAP-019,020 |

**Total edges (enumerated above):** **16** representative (+ **~100+** implicit HTTP apiName edges internal to each service — see `api-catalogue.md`).

---

## Critical money paths

### MONEY PATH: Loan disbursement

`SVC-GW` →(HTTP `disburseLoan` or LOS flow)→ `SVC-LOS` → `DisburseLoanProcessor` / `DisburseLoanAPIUtil` → **Redis** `RD-DISB-LOS` → **Kafka** `K-DISB-REQ` → `SVC-ACC` `LmsMessageBrokerConsumer` → **Redis** `RD-DISB-ACC` → orchestration `disburseLoan` → **DB-ACC** / bank → **Kafka** `K-DISB-SYNC` → `SVC-LOS` `DisbursementSyncConsumer`.

| Hop | Class.method (representative) | Contract | Failure | Gap |
|-----|------------------------------|----------|---------|-----|
| LOS → Kafka | `DisburseLoanAPIUtil.callDisburseLoanAPI` | pipe+json | GAP-019 | GAP-019 |
| Consumer | `LmsMessageBrokerConsumer.processConsumerRecord` | cache+api | TTL stale | Redis High |
| Sync back | `sendResultMessageToKafka` / `handleDisbursementSyncRecord` | **MISMATCH** (`entity_type`) | LOS no-op | entity_type |

### MONEY PATH: Loan repayment

`SVC-GW` or `SVC-PAY` → HTTP **`loanRepayment`** / **`collectionLoanRepayment`** → `SVC-ACC` orchestration → **`postTransaction`** / allocation processors → **DB-ACC**.

| Hop | Notes | Gap |
|-----|-------|-----|
| Payments LMS push | `MfiCollectionsDAOService.callPushLMSUpdateAPI` | SYNC_FAILED recon |
| Internal API | No HTTP retry | High |

### MONEY PATH: Interest accrual

`SCH-BAT` → `SVC-BAT` → HTTP **`interestAccrualPosting`** job → `InterestAccrualBookingBatchService.doInterestBooking` → **`postTransaction`** with **time-based** `client_reference_number` → **DB-ACC**.

| Hop | Risk | Gap |
|-----|------|-----|
| CRR generation | Replay double-post | Accrual High row |
| Multi-node | Duplicate job | Scheduler High |

### MONEY PATH: Loan closure

Batch **`loanAccountClosure`** → `LoanAccountAutoClosureItemReader` (ACTIVE only) → `LoanAccountAutoClosureItemWriter` → **DB-ACC** CLOSED → `PushLoanAccountClosureDetailsProcessor` → **K-DATA-SYNC** → LOS.

| Hop | Risk | Gap |
|-----|------|-----|
| Writer catch | Partial chunk | Auto-closure High |

### MONEY PATH: Bulk collection

Accrual/recurring **`LoanRecurringPaymentItemWriter`** → **K-BULK** → `CreateOrUpdateBulkCollectionConsumer` → **DB-PAY**.

| Hop | Risk | Gap |
|-----|------|-----|
| Producer | Silent fail | GAP-019 |
| Consumer | parse / NPE | GAP-044,064 |

### MONEY PATH: Reversal / manual JE

HTTP **`reverseTransaction`** / **`postManualJournalEntry`** → posting engine → **DB-ACC**.

| Hop | Risk | Gap |
|-----|------|-----|
| Tests | — | GAP-059 |

---

## Failure propagation map

| Node | Direct impact | Cascade | Data at risk | Recovery | Time to detect |
|------|---------------|---------|--------------|----------|----------------|
| SVC-MD down | Business date stale | All value_date/business_date | Wrong EOD posting | Ops date fix | Hours |
| SVC-BAT duplicate | Two job instances | Double chunk processing | Duplicate GL lines | Disable node; recon | Hours |
| K-DISB-SYNC mismatch | LOS state stale | Ops re-disburse risk | LOS vs ACC status | Manual patch | Days |
| LIB-PLAT Kafka swallow | Event lost | Downstream never runs | All async | DLQ missing | Days |

---

## Contract health summary

| Metric | Count (representative edges §Edge Registry) |
|--------|---------------------------------------------|
| **Total** | 16 |
| **ALIGNED** | 2 |
| **DRIFT** | 11 |
| **MISMATCH** | 2 (sync payload + LOS consumer = one logical mismatch counted on E6–E7) |
| **UNKNOWN** | 1 |

**Non-aligned edges:** E1–E5 (various DRIFT), E6–E7 (**MISMATCH**), E9–E16 (mostly DRIFT). **Full HTTP surface:** predominantly **DRIFT** at transport (no retry, 120s defaults) per Wave 2.

---

## Single points of failure

| Service | Called by | If it dies | Blast radius |
|---------|-----------|------------|--------------|
| **accounting-v2** | LOS, payments, batch, internal nested APIs | No ledger / disburse / enquiry | **Platform-wide lending** |
| **masterdata** (business date) | All posting + batch | Wrong date → wrong books | **All tenants** using cache |
| **batch platform** | Cron only | EOD jobs don’t start | Accrual, closure, DPD stall |
| **API gateway** | All external clients | No ingress | Total outage |
| **Yugabyte (ACC DB)** | accounting | No money data | Total |

---

**Flow Sync Wave 6 (2026-04-17):** Deep cross-service gap mining + observability matrix — new **GAP-065..069** in `.cursor/gaps-and-risks.md`. **Type 1 field drift:** `entity_type` absent in accounting sync JSON vs LOS `ENTITY_TYPE` required (existing + file:line in gap narratives). **Type 7:** accounting `MessageBroker.xml` money consumers lack explicit `maxPollRecords` (**GAP-065**). **Type 8 / EC:** `loanWriteoff` vs `PrepaymentApproppriationProcessor` (**GAP-062**); `account_details` NPE (**GAP-063**).

**Wave 7 revalidation (2026-04-22):** full disbursement audit confirms E6/E7 mismatch is still active in current runtime code (`LmsMessageBrokerConsumer.sendResultMessageToKafka` omits `entity_type`) and correlation is still partial (`stan` absent). See reopened/new gaps **GAP-070..073**.

**Wave 8 payment-reinit execution validation (2026-04-22):** parent disbursement reinit scenarios confirm lane typing and traceability on accounting disbursement path (`DISBURSEMENT_MFT_REINIT` / `DISBURSEMENT_NEFT_REINIT`) with monotonic reference progression across repeated explicit attempts; this strengthens money-path confidence inside node `SVC-ACC` for parent reinit flow while E6/E7 contract mismatch remains unresolved.

**Wave 9 disbursement demo execution setup (2026-04-23):** local operator wrapper `scripts/run_disbursement_full_matrix.sh` now provides one-command product-scoped validation (`JLG`/`INDL`/`SHG`/`ALL`) with DB-backed terminal-state checks and SHG CLMT queue evidence; this standardizes manual demo/verification entry for MONEY PATH: Loan disbursement.
