# 08 · Kafka topology — every topic, producer, consumer

> Single page covering Kafka usage across the platform. For full message schemas, see [`../platform/event-registry.md`](../platform/event-registry.md). For topic prefixes / poll intervals / thread counts per consumer, see each service's `deploy/application/messagebroker/MessageBroker.xml`.

## Producer registry (one per service)

| Producer ID | Service |
|---|---|
| `producer_id_los` | LOS |
| `producer_id_accounting` | accounting |
| `producer_id_actor` | actor |
| `producer_id_payments` | payments |
| `producer_id_task` | task |
| `producer_id_approval` | approval (no consumers; producer used for outbound notifications) |
| `producer_id_api_gateway_request_*` / `_response_*` | api-gateway |
| `AuditDataKafkaProducer` | reporting |
| (none) | audit, masterdata, notifications, dms, authorization, batch, initial-setup, webapp |

## The critical-path topics

These are the topics you must understand to debug LMS:

| Topic prefix | Producer | Consumer | What it carries |
|---|---|---|---|
| `disburse_loan_api_<tenant>` | LOS (`DisburseLoanAPIUtil`) | accounting (`LmsMessageBrokerConsumer`) | Disbursement trigger from LOS to LMS. Format `apiName\|body\|cacheKey` |
| `los_lms_disbursement_sync` | accounting (`AccountingKafkaProducer`) | LOS (`disbursementSyncConsumer`, 3 threads, critical) | Disbursement result back to LOS |
| `los_lms_data_sync_*` | LOS / accounting | LOS (`lmsDataSyncConsumer`) | Two-way data sync |
| `bulk_collection_data_<tenant>` | accounting | payments (`createOrUpdateBulkCollectionConsumer`, poll 1500 ms, high pri) | Bulk collection rows pushed from accounting to LCS |

## All Kafka edges grouped by source

### Originated by LOS (`producer_id_los`)

Broad fan-in from external pipelines + own retries:

| Topic prefix | Consumer (LOS) | Purpose |
|---|---|---|
| `disburse_loan_api_<tenant>` | (sent to **accounting**) | Disbursement trigger |
| `indl_qde_borrower_*_factiva_*` (and `jlgdl_*`) | `factivaConsumer` | Bureau (Factiva) eligibility |
| `indl_qde_borrower_*_posidex_*` | `posidexConsumer` | Posidex bureau call 1 |
| `indl_qde_borrower_*_posidex_*_second_call_*` | `posidexSecondCallConsumer` | Posidex call 2 |
| `indl_qde_borrower_*_multi_bureau_*` | `multiBureauConsumer` | Multi-bureau merge |
| `indl_qde_*_internal_dedupe_*` | `internalDedupeConsumer` | Internal mobile dedupe |
| `offline_data_bet_`, `offline_data_pd_`, `offline_data_` | `offlineDataConsumer` | Offline BET/PD ingest |
| `offline_data_td_` | `etbLanIdConsumer` | ETB LAN ID |
| `ckyc_preprocess_api_` | `ckycApiKafkaConsumer` | CKYC preprocessing |
| `geo_tracking_audit_`, `geo_tracking_login_logout_audit_` | `geoTracker*Consumer` | Geo audit |
| `posidex_los_inbound_`, `posidex_los_outbound_` | `posidexInboundLosConsumer`, `posidexOutboundLosConsumer` | Posidex sync |
| `generate_consent_doc_` | `generateConsentDocumentConsumer` | Async consent doc generation |
| `generate_specific_loan_doc_` | `generateSpecificLoanDocumentConsumer` | Async specific doc |
| `save_mmi_request_response_` | `mmiRequestResponseLogConsumer` | MMI logging |

### Originated by accounting (`producer_id_accounting`)

| Topic prefix | Consumer | Purpose |
|---|---|---|
| `los_lms_disbursement_sync` | LOS | Disbursement result |
| `bulk_collection_data_*` | payments | Bulk collection ingest |

### Originated by actor (`producer_id_actor`)

| Topic prefix | Consumer | Purpose |
|---|---|---|
| `posidex_actor_inbound_` | actor | Posidex inbound payloads |
| `session_activity_login_` | actor | Login events |
| `session_activity_logout` | actor | Logout events |
| `update_customer_loan_details` | actor | Customer/loan sync |

### Originated by payments (`producer_id_payments`)

All consumed by payments itself for cache-warming and async processing:

| Topic prefix | Consumer | Purpose |
|---|---|---|
| `collection_customer_details_*` | `populateCollectionCustomerDetailsConsumer` | Customer cache |
| `meeting_center_details_*` | `populateMeetingCenterDetailsConsumer` | Meeting-centre cache |
| `collection_office_details_*` | `collectionOfficeDetailsConsumer` | Office cache |
| `update_collection_task_details_*` | `updateCollectionTaskDetailsConsumer` | Task sync |
| `collection_primary_allocation_*` | `primaryAllocateCollectionConsumer` | Async primary allocation |
| `collection_secondary_allocation_*` | `secondaryAllocateCollectionConsumer` | Async secondary allocation |
| `collection_task_processing_*` | `collectionTaskProcessingConsumer` | Task processing |

### Originated by task (`producer_id_task`)

| Topic prefix | Consumer | Purpose |
|---|---|---|
| `task_user_tat_*` | `taskUserTatConsumer` | TAT events |
| `collection_task_creation_*` | `collectionTaskCreationConsumer` | Collection task creation |
| `finnone_collection_task_creation_*` | `finnoneCollectionTaskCreationConsumer` | Finnone-driven collection tasks |

### Originated by api-gateway

| Topic prefix | Consumer | Purpose |
|---|---|---|
| `api_gateway_request_*` | audit | Gateway request audit |
| `api_gateway_response_*` | audit | Gateway response audit |
| `audit_*` | audit | Functional audit |
| `telemetry_perf_log_*` | audit | Perf metrics |
| `external_service_audit_*` | audit | 3rd-party API call audit |

### Originated by reporting (`AuditDataKafkaProducer`)

| Topic | Consumer | Purpose |
|---|---|---|
| `POSIDEX_ACTOR_INBOUND_TOPIC_NAME` | actor | Posidex extract → actor |
| `POSIDEX_LOS_INBOUND_TOPIC_NAME` | LOS | Posidex extract → LOS |

### Notifications (consumer-only)

| Topic prefix | Consumer | Purpose |
|---|---|---|
| `async_notifications_` | notifications | Generic async dispatch |
| `alerts` | notifications | Internal alerts |
| `notification_sms_` | notifications | SMS channel |
| `notification_email_` | notifications | Email channel |
| `notification_fcm_` | notifications | FCM push |

## Tenant scoping

Most topics end with `<tenant>` (e.g. `disburse_loan_api_mfi`). The `<tenant>` suffix is added by the producer using `ThreadLocalContext.tenant.tenantCode`. Always include the tenant when troubleshooting topic lag or messages.

## Special patterns

- **Retry topics** — many LOS bureau pipelines define a `_retry_` variant (e.g. `indl_qde_borrower_default_factiva_service_retry_`). Same consumer bean handles both.
- **Stage variants** — LOS bureau topics distinguish by stage (`qde`, `conduct_pd`, `cm_dashboard`) and loan type (`indl` for individual, `jlgdl` for JLG/SHG).
- **Multi-thread consumers** — `disbursementSyncConsumer` runs 3 threads (critical path); most others use 1.
- **Poll intervals** — bulk-collection consumer polls every 1500 ms (high priority); standard consumers use Spring defaults.

## Common troubleshooting

- **Lag building** → check consumer health (CPU / DB latency); the framework doesn't auto-DLQ.
- **Disbursement stuck** → most often the cache key cleanup didn't happen; see [`../accounting/05-flows.md`](../accounting/05-flows.md) §1 + [`../runbooks/disbursement-stuck.md`](../runbooks/disbursement-stuck.md).
- **Audit data missing** → gateway → audit topics may be lagged; `getApiResponseByStan` will return "not found" temporarily.
- **Per-tenant outage** → only that tenant's topics affected; cluster-wide kafka issues affect all.

## Where to add a new topic

- Producer side: declare in producer service's `MessageBroker.xml`.
- Consumer side: implement `NovopayMessageBrokerConsumer` interface (in `infra-kafka` lib) + register in consumer service's `MessageBroker.xml`.
- Document in [`../platform/event-registry.md`](../platform/event-registry.md) + add to this atlas.
