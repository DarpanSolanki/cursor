# 05 · Integration topology — who talks to whom and how

> Two transports: **HTTP** (sync, via gateway / `NovopayInternalAPIClient`) and **Kafka** (async). This page is the cross-service edge map. For deep details on event schemas, see [`../platform/event-registry.md`](../platform/event-registry.md). For HTTP routing details, see the per-service brain doc.

## HTTP edges (sync)

```
                                   ┌──────────────────┐
                                   │      webapp      │
                                   └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │   api-gateway    │
                                   └─────┬─────┬──────┘
                                         │     └─────────────────────────────┐
                       ┌─────────────────┘                                   │
                       │  (every Request: gateway → checkPermissionByUsecase ▶ authorization)
                       │
   ┌───────────────────┼───────────────────────────────────────────────────────────┐
   │                   │                                                            │
   ▼                   ▼                                                            ▼
┌─────────┐         ┌──────────────────────────────────────────────────────┐    ┌─────────┐
│   los   │         │              accounting (LMS)                        │    │ payments│
│         │ ──HTTP─►│   - getUseCaseDetails                                │ ◄─ │  (LCS)  │
│         │         │   - getCustomerDetails / getOfficeDetails / Hierarchy│    │         │
│         │         │   - submitApplication (for maker-checker)            │    │         │
│         │         │   - createOrUpdateTask                               │    │         │
│         │         │   - verifyDocuments                                  │    │         │
│         │         │   - getNotificationMessageByNotificationCode         │    │         │
│         │         │   - masterDataValidator (declarative)                │    │         │
│         │         │   - bank NEFT / insurance providers (external)       │    │         │
└────┬────┘         └─┬────┬────┬────┬─────┬───────┬────────┬─────────────┘    └────┬────┘
     │                │    │    │    │     │       │        │                        │
     │                │    │    │    │     │       │        │                        │
     ▼                ▼    ▼    ▼    ▼     ▼       ▼        ▼                        ▼
   ┌─────┐         ┌─────┐ ┌─────┐ ┌──────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐
   │actor│         │actor│ │ task│ │approve│ │  dms   │ │notif.    │ │ masterdata   │ │  actor   │
   └─────┘         └─────┘ └─────┘ └──────┘ └────────┘ └──────────┘ └──────────────┘ └──────────┘
                            ▲
                            │ getRoleCodesByTaskIds
                            │
                       ┌────┴────┐
                       │  tasks  │ ─HTTP─▶ actor (employee/office hierarchy)
                       └─────────┘ ─HTTP─▶ approval (task config maker-checker)

       ┌───────────┐  one-way HTTP  (uses jobname = orchestration RequestName)
       │   batch   │ ──────────────────────▶ accounting (and occasionally LOS for bulk uploads)
       └───────────┘

       ┌────────────┐                                ┌─────────────────────┐
       │   audit    │ ◄── outbound: getTimelineAction│      task           │
       └────────────┘   (when function_code != WITHOUT_TIMELINE)──────────┘

       ┌────────────────────────────────────────┐
       │   reporting → DMS (uploadDocument)     │  via gateway
       │   reporting → ES (audit)               │
       └────────────────────────────────────────┘
```

### Most-called HTTP endpoints (cross-service hot paths)

- `getUserDetails` / `getCustomerDetails` / `getOfficeDetails` / `getHierarchyElement` / `getRoleDetailsByUserId` → **actor**
- `submitApplication` / `approveApplication` / `rejectApplication` → **approval**
- `getUseCaseDetails` → **actor** (use-case master)
- `createOrUpdateTask` / `deleteTask` → **task**
- `verifyDocuments` / `uploadDocument` / `downloadDocument` → **dms**
- `getNotificationMessageByNotificationCode` → **notifications**
- `checkPermissionByUsecase` → **authorization** (gateway-side every request)
- `loanRepayment` / `postTransaction` / `getLoanAccountDetails` / `disburseLoan` → **accounting**

Routing happens via `NovopayInternalAPIClient.callInternalAPI(executionContext, apiName, version, ...)`. The internal client uses the per-tenant service registry (seeded by initial-setup; cached in gateway).

## Kafka edges (async)

```
LOS ─producer_id_los─▶ disburse_loan_api_<tenant>     ─▶ accounting (LmsMessageBrokerConsumer)
                       indl_qde_*                       ─▶ LOS itself (factiva, posidex, multibureau, dedupe consumers)
                       offline_data_*                   ─▶ LOS (offlineDataConsumer)
                       ckyc_preprocess_api_             ─▶ LOS (ckycApiKafkaConsumer)
                       geo_tracking_*                   ─▶ LOS (geoTrackerAuditConsumer)
                       generate_consent_doc_            ─▶ LOS (generateConsentDocumentConsumer)
                       generate_specific_loan_doc_      ─▶ LOS (generateSpecificLoanDocumentConsumer)
                       posidex_los_*                    ─▶ LOS (posidex sync)
                       save_mmi_request_response_       ─▶ LOS (mmiRequestResponseLogConsumer)

accounting ─producer_id_accounting─▶ los_lms_disbursement_sync ─▶ LOS (disbursementSyncConsumer)
                                       bulk_collection_data_*    ─▶ payments (createOrUpdateBulkCollectionConsumer)

actor ─producer_id_actor─▶ posidex_actor_inbound_      ─▶ actor (posidexInboundActorConsumer)
                            session_activity_login_     ─▶ actor (sessionActivityLoginConsumer)
                            session_activity_logout     ─▶ actor (sessionActivityLogoutConsumer)
                            update_customer_loan_details ─▶ actor (updateCustomerLoanDetailsConsumer)

payments ─producer_id_payments─▶  collection_customer_details_*   ─▶ payments (cache populator)
                                   meeting_center_details_*        ─▶ payments
                                   collection_office_details_*     ─▶ payments
                                   update_collection_task_details_*─▶ payments
                                   collection_primary_allocation_* ─▶ payments
                                   collection_secondary_allocation_*─▶ payments
                                   collection_task_processing_*    ─▶ payments

task ─producer_id_task─▶ task_user_tat_*               ─▶ task
                          collection_task_creation_*    ─▶ task
                          finnone_collection_task_creation_* ─▶ task

api-gateway ─producer_id_api_gateway_*─▶ api_gateway_request_*   ─▶ audit (request log)
                                          api_gateway_response_*  ─▶ audit (response log)
                                          telemetry_perf_log_*    ─▶ audit
                                          audit_*                 ─▶ audit (functional)
                                          external_service_audit_*─▶ audit

reporting ─AuditDataKafkaProducer─▶ POSIDEX_ACTOR_INBOUND_TOPIC_NAME ─▶ actor
                                     POSIDEX_LOS_INBOUND_TOPIC_NAME   ─▶ LOS

notifications ─consumer-only─▶ async_notifications_, alerts, notification_sms_, notification_email_, notification_fcm_
```

Per-tenant scoping: most topic names end with `<tenant>` (e.g. `disburse_loan_api_mfi`).

## Redis usage by service

| Service | Redis DB | What |
|---|---|---|
| accounting | 5 (ACCOUNTING) | Loan products, schemes, interest details, accounting rules, asset criteria, internal accounts, price master, tax, txn catalogue. Also `dl<…>` disbursement dedup |
| actor | 3 (ACTOR) | Actor / employee / office / user details, portfolio transfer context |
| masterdata | 1 (MASTER_DATA) | Code masters by `(dataType, dataSubType, locale)` |
| notifications | 2 (NOTIFICATION) | Templates by notification code |
| payments | 0 (DEFAULT) | Finnone caches (10 h TTL on `finnone_static_product_list`, employee/office maps, formatted-id maps) |
| LOS | 5 (ACCOUNTING) — disbursement dedup | `dl<…>` keys; also OTP/Aadhaar in DEFAULT |
| api-gateway | (apiRateLimit DB) | Bucket4j rate-limit state |
| OTP | DEFAULT (DB 0) | Notifications service |

`RedisDBConfig` enum lives in `infra-cache`. Full registry: [`../platform/redis-key-registry.md`](../platform/redis-key-registry.md).

## Rules of thumb

- **Sync calls go through the gateway** — `NovopayInternalAPIClient` does not bypass the gateway in production. STAN, dedup, audit, rate-limit all apply.
- **Kafka topics are tenant-scoped** — when troubleshooting, always include the tenant suffix.
- **Failures on async paths surface late** — a stuck consumer doesn't block callers. Watch lag, not just throughput.
- **Redis is per-tenant** — `NovopayCacheClient` prefixes every key with the tenant code automatically. Don't share keys across tenants.
- **No eventual consistency between accounting GL and bank** — settlement is sync NEFT → wait for the bank to confirm before posting.
