# Event registry (Kafka) — production-ready registry

**Truth sources:** per-service `deploy/application/messagebroker/MessageBroker.xml` + the referenced consumer Java class.

**Topic name convention:** this repo’s config uses `<topicPrefix>`; runtime topics may be tenant/env suffixed by framework.

## Registry entries (146)
### `alerts`
- **Topic name (exact in config):** `alerts`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-notifications/src/main/java/in/novopay/notifications/fcm/service/FcmPushNotificationService.java`:22 → `import in.novopay.notifications.alerts.dao.AppNotificationLogDaoService;`
  - `./novopay-platform-notifications/src/main/java/in/novopay/notifications/fcm/service/FcmPushNotificationService.java`:23 → `import in.novopay.notifications.alerts.entity.AppNotificationLogEntity;`
- **Consumer:** service `novopay-platform-notifications` | class `in.novopay.notifications.utils.NotificationsBrokerConsumer` | methods ``computeRecords``
- **Consumer config:** group `consumer_id_notification_` | threads `1` | pollTime `1000` | maxPollRecords `10` | XML `novopay-platform-notifications/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `headers`, `request`, `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `api_gateway_request_`
- **Topic name (exact in config):** `api_gateway_request_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/RequestResponseLogFilter.java`:124 → `reqResMessageKafkaProducer.pushDataToKafkaQueue(entity.toJsonString(), "api_gateway_request_");`
  - `./novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/MfiRequestResponseLogFilter.java`:119 → `reqResMessageKafkaProducer.pushDataToKafkaQueue(entity.toJsonString(), "api_gateway_request_");`
- **Consumer:** service `novopay-platform-audit` | class `in.novopay.audit.consumer.RequestMessageBrokerConsumer` | methods ``computeRecords``
- **Consumer config:** group `consumer_id_api_gateway_request_` | threads `10` | pollTime `1000` | maxPollRecords `10` | XML `novopay-platform-audit/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `api_gateway_response_`
- **Topic name (exact in config):** `api_gateway_response_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/RequestResponseLogFilter.java`:184 → `reqResMessageKafkaProducer.pushDataToKafkaQueue(responseLogEntity.toJsonString(), "api_gateway_response_");`
  - `./novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/MfiRequestResponseLogFilter.java`:173 → `reqResMessageKafkaProducer.pushDataToKafkaQueue(responseLogEntity.toJsonString(), "api_gateway_response_");`
- **Consumer:** service `novopay-platform-audit` | class `in.novopay.audit.consumer.ResponseMessageBrokerConsumer` | methods ``computeRecords``
- **Consumer config:** group `consumer_id_api_gateway_response_` | threads `10` | pollTime `1000` | maxPollRecords `10` | XML `novopay-platform-audit/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `async_notifications_`
- **Topic name (exact in config):** `async_notifications_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/common/processor/SendAsyncNotificationDataToKakaProcessor.java`:144 → `"async_notifications_" + executionContext.getValue("tenant_code", String.class), serviceName,`
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/common/processor/SendAsyncNotificationDataToKakaProcessor.java`:174 → `"async_notifications_" + executionContext.getValue("tenant_code", String.class), serviceName,`
- **Consumer:** service `novopay-platform-notifications` | class `in.novopay.notifications.processor.NotificationMessageBrokerConsumer` | methods ``computeRecords``
- **Consumer config:** group `consumer_id_notification_` | threads `1` | pollTime `1000` | maxPollRecords `10` | XML `novopay-platform-notifications/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `body`, `handle_type`, `handle_value`, `notification_code`, `notification_message`, `password`, `sms_default_priority`, `sms_default_provider`, `sms_default_sender_code`, `stan`, `subject`, `templateCode`, `url_template`, `username`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `audit_`
- **Topic name (exact in config):** `audit_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/AuditTypeEnum.java`:5 → `DEFAULT("default", "audit_"),`
  - `./novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/AuditTypeEnum.java`:6 → `GEO_TRACKING("geoTracking", "geo_tracking_audit_");`
- **Consumer:** service `novopay-platform-audit` | class `UNKNOWN` | methods ``computeRecords``
- **Consumer config:** group `consumer_id_audit_` | threads `1` | pollTime `1000` | maxPollRecords `1` | XML `novopay-platform-audit/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** UNKNOWN
- **Risk flags:** ⚠️ consumer class unresolved

### `bulk_collection_data_`
- **Wave 3 (2026-04-17):** Producer JSON keys code-verified: `timestamp`, `client_code`, `collection_list` (`LoanRecurringPaymentItemWriter.java` L196-L199). Consumer expects `collection_list` of objects with `col_ext_ref_id`, `due_details`, `customer`, `group_detail` (`CreateOrUpdateBulkCollectionConsumer`, `BulkCollectionExtractor`). **GAP-064** if `collection_list` null.
- **Topic name (runtime):** `bulk_collection_data_<tenantCode>[_<environment>]` — suffix from `AccountingKafkaProducer` (`novopay-platform-accounting-v2/.../AccountingKafkaProducer.java` L23-L31). **Kafka message key:** `null` (producer passes `null` to `NovopayKafkaProducer.sendMessage`).
- **Direction:** accounting **PRODUCES** → payments **CONSUMES**.
- **Producer:** `novopay-platform-accounting-v2` | `LoanRecurringPaymentItemWriter` → `AccountingKafkaProducer.pushDataToKafkaQueue` | `LoanRecurringPaymentItemWriter.java` ~L196-L203.
- **Producer payload (root JSON):** `timestamp` (string), `client_code` (`NOVOPAY`), `collection_list` (JSONArray).
- **Collection element (from `LoanRecurringPaymentBatchProcessor` ~L157-L245):** `col_ext_ref_id`, `customer` `{id}`, `group_detail` `{group_id}`, `due_details` (loan_account_number, due_date, dpd, principal/interest/penalty fields, EMI metadata, `instrument_type`, …).
- **Consumer:** `novopay-platform-payments` | `CreateOrUpdateBulkCollectionConsumer.computeRecords` | reads root `timestamp`, `collection_list`; per element `col_ext_ref_id`, `due_details`, `customer`, `group_detail` (`CreateOrUpdateBulkCollectionConsumer.java` ~L71-L94).
- **Consumer config:** group `bulk_collection_data_consumer_` | threads `1` | pollTime `1500` | maxPollRecords `1` | XML `novopay-platform-payments/deploy/application/messagebroker/MessageBroker.xml`
- **Contract match (Wave 2):** ✅ **ALIGNED** on core keys and nesting — producer fields match consumer accessors.
- **Null-checked on consumer:** **Partial** — utility `getStringValue`; `collection_list` assumed non-null when details object non-null.
- **Publish failure handled (accounting):** **N** — `NovopayKafkaProducer` logs on failure; no caller callback (**GAP-019**).
- **Dead letter topic:** **N** (this path).
- **Consumer idempotent:** **Partial** — DB-driven; retries depend on payments logic.
- **Gap reference:** **GAP-019** (producer visibility).
- **Error handling:** Y (consumer)
- **Risk flags:** none new beyond platform producer swallow

### `bulk_collection_data_failed_`
- **Topic name (runtime):** prefix `bulk_collection_data_failed_` + tenant/env suffix (payments producer; constant in `BulkCollectionExtractor.java` L52).
- **Direction:** payments **PRODUCES** → accounting **CONSUMES**.
- **Producer:** `novopay-platform-payments` | failed-record path using `BULK_COLLECTION_FAILED_RECORDS_TOPIC`.
- **Consumer:** `novopay-platform-accounting-v2` | `BulkCollectionFailedRecordConsumer.computeRecords` | persists raw `consumerRec.value()` to `BulkCollectionLog.failedRecord` (no JSON parse).
- **Consumer config:** group `bulk_collection_failed_record_consumer` | threads `1` | pollTime `100` | maxPollRecords `` | XML `novopay-platform-accounting-v2/deploy/application/messagebroker/MessageBroker.xml`
- **Contract match (Wave 2):** **DRIFT** — opaque blob contract by design.
- **Null-checked on consumer:** **N**
- **Publish failure handled:** not verified Wave 2.
- **Dead letter:** **N** | **Consumer idempotent:** **N** | **Gap reference:** **GAP-036**
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class

### `ckyc_preprocess_api_`
- **Topic name (exact in config):** `ckyc_preprocess_api_`
- **Producer (best-effort, literal reference):**
  - `./novopay-mfi-los/src/main/java/in/novopay/los/batch/ckyc/writer/CkycInputDataItemWriter.java`:216 → `String topic = "ckyc_preprocess_api_";`
  - `./novopay-mfi-los/src/main/java/in/novopay/los/batch/ckyc/ckycapijob/TriggerCkycApiProcessor.java`:44 → `String topic = "ckyc_preprocess_api_";`
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.batch.ckyc.ckycapijob.CkycApiKafkaConsumer` | methods ``computeRecords``
- **Consumer config:** group `ckyc_preprocess_api_` | threads `2` | pollTime `3000` | maxPollRecords `2` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `collection_customer_details_`
- **Topic name (exact in config):** `collection_customer_details_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/topics/ActorTopics.java`:9 → `public static final String COLLECTION_CUSTOMER_DETAILS_TOPIC = "collection_customer_details_";`
- **Consumer:** service `novopay-platform-payments` | class `in.novopay.payments.collections.mfi.consumer.PopulateCollectionCustomerDetailsConsumer` | methods ``computeRecords``
- **Consumer config:** group `collection_customer_details_` | threads `1` | pollTime `100` | maxPollRecords `1` | XML `novopay-platform-payments/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `address_line_1`, `address_line_2`, `address_line_3`, `address_line_4`, `address_type`, `city`, `create_group_info_flag`, `customer_aadhaar_no`, `customer_external_id`, `customer_id`, `customer_name`, `customer_pan_no`, `customer_passport_no`, `customer_voter_no`, `customer_vtc_id`, `customer_vtc_name`, `cycle_count`, `cycle_type`, `disb_account_no`, `disbursement_account_number`, `disbursement_amount`, `dl_no`, `dob`, `dsa_lead_number`, `ext_collector_id`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `collection_office_details_`
- **Topic name (exact in config):** `collection_office_details_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/custom/mfi/office/processor/CreateOrUpdateOfficeCollectionInfoKafkaProducer.java`:100 → `String topic = "collection_office_details_";`
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/bulk/office/iwriter/SGToOfficeUpsertIWriter.java`:136 → `actorKafkaProducer.pushDataToKafkaQueue( message.toJSONString(), "collection_office_details_");`
- **Consumer:** service `novopay-platform-payments` | class `in.novopay.payments.collections.mfi.consumer.CollectionOfficeDetailsConsumer` | methods ``computeRecords``
- **Consumer config:** group `collection_office_details_consumer_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-platform-payments/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `collection_primary_allocation_`
- **Topic name (exact in config):** `collection_primary_allocation_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java`:59 → `private static final String PRIMARY_ALLOCATION_TOPIC = "collection_primary_allocation_";`
- **Consumer:** service `novopay-platform-payments` | class `in.novopay.payments.collections.mfi.consumer.PrimaryAllocateCollectionConsumer` | methods ``computeRecords`, `processRecordsForSecondaryAllocation`, `processAllocationData``
- **Consumer config:** group `collection_primary_allocation_consumer_` | threads `1` | pollTime `1000` | maxPollRecords `1` | XML `novopay-platform-payments/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `allocation_data`, `primary_alloc_data`, `tenant_code`, `transmission_datetime`, `user_id`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `collection_secondary_allocation_`
- **Topic name (exact in config):** `collection_secondary_allocation_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/PrimaryAllocateCollectionConsumer.java`:57 → `private static final String SECONDARY_ALLOCATION_TOPIC = "collection_secondary_allocation_";`
  - `./novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java`:60 → `private static final String SECONDARY_ALLOCATION_TOPIC = "collection_secondary_allocation_";`
- **Consumer:** service `novopay-platform-payments` | class `in.novopay.payments.collections.mfi.consumer.SecondaryAllocateCollectionConsumer` | methods ``computeRecords`, `processApiResponse`, `processRecordsForTaskCreation``
- **Consumer config:** group `collection_secondary_allocation_consumer_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-platform-payments/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `allocation_data`, `external_id`, `secondary_alloc_data`, `task_creation_data`, `tenant_code`, `transmission_datetime`, `user_id`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `collection_task_creation_`
- **Topic name (exact in config):** `collection_task_creation_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-payments/src/main/java/in/novopay/payments/collections/task/util/MfiTaskUtility.java`:706 → `paymentsKafkaProducer.pushDataToKafkaQueue(message, "collection_task_creation_");`
- **Consumer:** service `novopay-platform-task` | class `in.novopay.task.mfi.consumers.CollectionTaskCreationConsumer` | methods ``computeRecords``
- **Consumer config:** group `collection_task_creation_consumer_` | threads `1` | pollTime `1000` | maxPollRecords `1` | XML `novopay-platform-task/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `collection_id`, `task_id`, `task_status`, `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `collection_task_processing_`
- **Topic name (exact in config):** `collection_task_processing_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/SecondaryAllocateCollectionConsumer.java`:127 → `paymentsKafkaProducer.pushDataToKafkaQueue(taskCreationData.toString(), "collection_task_processing_");`
  - `./novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java`:220 → `paymentsKafkaProducer.pushDataToKafkaQueue(messageData.toString(), "collection_task_processing_");`
- **Consumer:** service `novopay-platform-payments` | class `in.novopay.payments.collections.mfi.consumer.CollectionTaskProcessingConsumer` | methods ``computeRecords``
- **Consumer config:** group `collection_task_creation_consumer_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-platform-payments/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `collection_id`, `local_map`, `shared_map`, `task_creation_data`, `tenant_code`, `transmission_datetime`, `user_id`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `disburse_loan_api_`
- **Topic name (runtime):** `disburse_loan_api_<tenant>[_env]` (framework + LOS producer).
- **Direction:** LOS **PRODUCES** → accounting **CONSUMES**.
- **Producer:** `novopay-mfi-los` | `DisburseLoanAPIUtil` → `losMessageKafkaProducer.pushDataToKafkaQueue(request, "disburse_loan_api_")` | see `DisburseLoanAPIUtil.java` ~L83.
- **Consumer:** `novopay-platform-accounting-v2` | `LmsMessageBrokerConsumer.computeRecords` / `processConsumerRecord` | `LmsMessageBrokerConsumer.java`.
- **Consumer config:** group `disburse_loan_api_consumer_` | threads `1` | pollTime `100` | maxPollRecords `` | XML `novopay-platform-accounting-v2/deploy/application/messagebroker/MessageBroker.xml`
- **Payload format (string value):** `apiName|requestBody|cacheKey` — see `LmsMessageBrokerConsumer` L69, L161-L162 (`api` = substring before first `|`; `requestBody` between pipes; `cacheKey` after last `|`). Consumer merges into EC via `parseAPIHeader` / `parseAPIRequest` (`LmsMessageBrokerConsumer.java` L164-L170).
- **Contract match (Wave 2):** ✅ **ALIGNED** on framing — LOS must preserve delimiter contract; inner JSON is `apiName`-specific (typically `disburseLoan`).
- **Null-checked on consumer:** **Partial** — `StringUtils` on skip paths; malformed pipe layout can throw `StringIndexOutOfBoundsException`.
- **Publish failure handled (LOS):** not expanded Wave 2.
- **Dead letter:** **N** (known path).
- **Consumer idempotent:** **Partial** — Redis `dl` + DB skip rules (**no TTL** on consumer key — existing High gaps).
- **Gap reference:** Redis TTL (summary table); **`entity_type`** on `los_lms_disbursement_sync` (not this topic).
- **Error handling:** Y (try/catch in consumer; result publish separate).
- **Risk flags:** sync payload **entity_type** missing on `los_lms_disbursement_sync` (see that topic).

### `external_service_audit_`
- **Topic name (exact in config):** `external_service_audit_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-platform-audit` | class `in.novopay.audit.consumer.ExternalServiceAuditConsumer` | methods ``computeRecords``
- **Consumer config:** group `external_service_audit_` | threads `1` | pollTime `1000` | maxPollRecords `1` | XML `novopay-platform-audit/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `tenant`
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `finnone_collection_task_creation_`
- **Topic name (exact in config):** `finnone_collection_task_creation_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-payments/src/main/java/in/novopay/payments/collections/util/FinnoneTaskUtility.java`:70 → `private static final String FINNONE_COLL_TASK_TOPIC = "finnone_collection_task_creation_";`
- **Consumer:** service `novopay-platform-task` | class `in.novopay.task.mfi.consumer.FinnoneCollectionTaskCreationConsumer` | methods ``computeRecords`, `processForCreatePtp`, `processForUpateFinnoneTask`, `processforClosingAndDeletingTask`, `processForUpdateTask``
- **Consumer config:** group `finnone_collection_task_creation_consumer_` | threads `4` | pollTime `1000` | maxPollRecords `1` | XML `novopay-platform-task/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `api_name`, `api_version`, `collection_amount`, `collection_date`, `collection_id`, `count`, `customer_name`, `fields_type_list`, `finnone_task_action`, `group_name`, `loan_account_number`, `office_id`, `product_type`, `requestName`, `stan`, `task_assignee_contributor`, `task_ids`, `task_status`, `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `generate_consent_doc_`
- **Topic name (exact in config):** `generate_consent_doc_`
- **Producer (best-effort, literal reference):**
  - `./novopay-mfi-los/src/main/java/in/novopay/los/processor/GenerateConsentThroughKafkaProcessor.java`:93 → `String topic = "generate_consent_doc_";`
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.GenerateConsentDocumentConsumer` | methods ``computeRecords``
- **Consumer config:** group `generate_consent_doc_` | threads `2` | pollTime `5000` | maxPollRecords `2` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `generate_specific_loan_doc_`
- **Topic name (exact in config):** `generate_specific_loan_doc_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.GenerateSpecificLoanDocumentConsumer` | methods ``computeRecords``
- **Consumer config:** group `generate_specific_loan_doc_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** Y
- **Risk flags:** ⚠️ producer unresolved in-repo

### `geo_tracking_audit_`
- **Topic name (exact in config):** `geo_tracking_audit_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.GeoTrackerAuditConsumer` | methods ``computeRecords``
- **Consumer config:** group `geo_tracking_audit_` | threads `2` | pollTime `2000` | maxPollRecords `2` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** Y
- **Risk flags:** ⚠️ producer unresolved in-repo

### `geo_tracking_login_logout_audit_`
- **Topic name (exact in config):** `geo_tracking_login_logout_audit_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/user/processor/AuditLoginLogoutProcessor.java`:49 → `actorKafkaProducer.pushDataToKafkaQueue(message.toString(), "geo_tracking_login_logout_audit_");`
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/user/processor/AuditLoginLogoutProcessor.java`:79 → `actorKafkaProducer.pushDataToKafkaQueue(message.toString(), "geo_tracking_login_logout_audit_");`
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.GeoTrackerLoginLogoutAuditConsumer` | methods ``computeRecords``
- **Consumer config:** group `geo_tracking_login_logout_audit_` | threads `2` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `activity_type`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `indl_cm_dashboard_borrower_default_factiva_service_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_default_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_factiva_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_default_factiva_service_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_default_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_default_factiva_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_default_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_default_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_default_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_default_multi_bureau_service_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_default_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_default_multi_bureau_service_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_default_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_default_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_default_posidex_service_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_default_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_default_posidex_service_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_default_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_default_posidex_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_default_posidex_service_second_call_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_default_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_default_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_default_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_default_posidex_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_factiva_service_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_factiva_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_multi_bureau_service_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_posidex_service_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_borrower_posidex_service_second_call_`
- **Topic name (exact in config):** `indl_cm_dashboard_borrower_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_borrower_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_co_borrower_default_factiva_service_`
- **Topic name (exact in config):** `indl_cm_dashboard_co_borrower_default_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_co_borrower_factiva_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_co_borrower_default_factiva_service_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_co_borrower_default_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_co_borrower_default_factiva_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_co_borrower_default_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_co_borrower_default_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_co_borrower_default_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_co_borrower_default_multi_bureau_service_`
- **Topic name (exact in config):** `indl_cm_dashboard_co_borrower_default_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_co_borrower_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_co_borrower_default_multi_bureau_service_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_co_borrower_default_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_co_borrower_default_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_co_borrower_default_posidex_service_`
- **Topic name (exact in config):** `indl_cm_dashboard_co_borrower_default_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_co_borrower_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_co_borrower_default_posidex_service_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_co_borrower_default_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_co_borrower_default_posidex_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_co_borrower_default_posidex_service_second_call_`
- **Topic name (exact in config):** `indl_cm_dashboard_co_borrower_default_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_co_borrower_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_cm_dashboard_co_borrower_default_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `indl_cm_dashboard_co_borrower_default_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_cm_dashboard_co_borrower_default_posidex_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_conduct_pd_factiva_service_`
- **Topic name (exact in config):** `indl_qde_borrower_conduct_pd_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_conduct_pd_factiva_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_conduct_pd_multi_bureau_service_`
- **Topic name (exact in config):** `indl_qde_borrower_conduct_pd_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_conduct_pd_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_conduct_pd_posidex_service_`
- **Topic name (exact in config):** `indl_qde_borrower_conduct_pd_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_conduct_pd_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_conduct_pd_posidex_service_second_call_`
- **Topic name (exact in config):** `indl_qde_borrower_conduct_pd_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_conduct_pd_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_default_factiva_service_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_default_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_default_factiva_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_default_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_default_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_default_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_default_multi_bureau_service_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_default_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_default_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_default_posidex_service_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_default_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_default_posidex_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_default_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_default_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_default_posidex_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_onboarding_factiva_service_`
- **Topic name (exact in config):** `indl_qde_borrower_onboarding_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_onboarding_factiva_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_onboarding_multi_bureau_service_`
- **Topic name (exact in config):** `indl_qde_borrower_onboarding_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_onboarding_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_onboarding_posidex_service_`
- **Topic name (exact in config):** `indl_qde_borrower_onboarding_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_onboarding_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_onboarding_posidex_service_second_call_`
- **Topic name (exact in config):** `indl_qde_borrower_onboarding_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_onboarding_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_qde_factiva_service_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_qde_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_qde_factiva_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_qde_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_qde_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_qde_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_qde_multi_bureau_service_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_qde_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_qde_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_qde_posidex_service_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_qde_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_qde_posidex_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_borrower_qde_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `indl_qde_borrower_qde_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_borrower_qde_posidex_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_conduct_pd_factiva_service_`
- **Topic name (exact in config):** `indl_qde_co_borrower_conduct_pd_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_conduct_pd_factiva_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_conduct_pd_multi_bureau_service_`
- **Topic name (exact in config):** `indl_qde_co_borrower_conduct_pd_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_conduct_pd_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_conduct_pd_posidex_service_`
- **Topic name (exact in config):** `indl_qde_co_borrower_conduct_pd_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_conduct_pd_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_conduct_pd_posidex_service_second_call_`
- **Topic name (exact in config):** `indl_qde_co_borrower_conduct_pd_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_conduct_pd_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_default_factiva_service_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_default_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_default_factiva_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_default_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_default_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_default_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_default_multi_bureau_service_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_default_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_default_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_default_posidex_service_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_default_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_default_posidex_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_default_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_default_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_default_posidex_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_onboarding_factiva_service_`
- **Topic name (exact in config):** `indl_qde_co_borrower_onboarding_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_onboarding_factiva_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_onboarding_multi_bureau_service_`
- **Topic name (exact in config):** `indl_qde_co_borrower_onboarding_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_onboarding_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_onboarding_posidex_service_`
- **Topic name (exact in config):** `indl_qde_co_borrower_onboarding_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_onboarding_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_onboarding_posidex_service_second_call_`
- **Topic name (exact in config):** `indl_qde_co_borrower_onboarding_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_onboarding_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_qde_factiva_service_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_qde_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_qde_factiva_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_qde_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_qde_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_qde_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_qde_multi_bureau_service_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_qde_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_qde_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_qde_posidex_service_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_qde_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_qde_posidex_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `indl_qde_co_borrower_qde_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `indl_qde_co_borrower_qde_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `indl_qde_co_borrower_qde_posidex_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_borrower_default_factiva_service_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_borrower_default_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_borrower_factiva_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_borrower_default_factiva_service_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_borrower_default_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_borrower_default_factiva_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_borrower_default_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_borrower_default_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_borrower_default_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_borrower_default_multi_bureau_service_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_borrower_default_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_borrower_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_borrower_default_multi_bureau_service_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_borrower_default_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_borrower_default_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_borrower_default_posidex_service_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_borrower_default_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_borrower_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_borrower_default_posidex_service_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_borrower_default_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_borrower_default_default_posidex_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_borrower_default_posidex_service_second_call_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_borrower_default_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_borrower_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_borrower_default_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_borrower_default_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_borrower_default_posidex_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_factiva_service_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_factiva_service_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_factiva_service_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_factiva_service_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_internal_dedupe_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_internal_dedupe_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_internal_dedupe_service_retry_` | threads `1` | pollTime `2000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_multi_bureau_service_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_multi_bureau_service_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_multi_bureau_service_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_multi_bureau_service_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_posidex_service_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_posidex_service_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_posidex_service_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_posidex_service_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_posidex_service_second_call_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_posidex_service_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_cm_dashboard_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `jlgdl_cm_dashboard_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_cm_dashboard_posidex_service_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_factiva_service_`
- **Topic name (exact in config):** `jlgdl_household_details_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_factiva_service_` | threads `3` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_factiva_service_retry_`
- **Topic name (exact in config):** `jlgdl_household_details_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_factiva_service_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_internal_dedupe_retry_`
- **Topic name (exact in config):** `jlgdl_household_details_internal_dedupe_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `jlgdl_household_details_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_internal_dedupe_service_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_multi_bureau_service_`
- **Topic name (exact in config):** `jlgdl_household_details_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_multi_bureau_service_retry_`
- **Topic name (exact in config):** `jlgdl_household_details_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_posidex_service_`
- **Topic name (exact in config):** `jlgdl_household_details_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_posidex_service_retry_`
- **Topic name (exact in config):** `jlgdl_household_details_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_posidex_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_posidex_service_second_call_`
- **Topic name (exact in config):** `jlgdl_household_details_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_household_details_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `jlgdl_household_details_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_household_details_posidex_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_conduct_bet_factiva_service_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_conduct_bet_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_conduct_bet_factiva_` | threads `2` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_conduct_bet_multi_bureau_service_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_conduct_bet_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_conduct_bet_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_conduct_bet_posidex_service_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_conduct_bet_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_conduct_bet_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_conduct_bet_posidex_service_second_call_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_conduct_bet_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_conduct_bet_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_default_factiva_service_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_default_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_default_factiva_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_default_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_default_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_default_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_default_multi_bureau_service_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_default_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_default_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_default_posidex_service_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_default_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_default_posidex_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_default_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_default_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_default_posidex_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_onboarding_factiva_service_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_onboarding_factiva_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_onboarding_factiva_` | threads `3` | pollTime `4000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_onboarding_multi_bureau_service_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_onboarding_multi_bureau_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_onboarding_multi_bureau_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_onboarding_posidex_service_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_onboarding_posidex_service_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_onboarding_posidex_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_onboarding_posidex_service_second_call_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_onboarding_posidex_service_second_call_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_onboarding_posidex_second_call_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_qde_factiva_service_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_qde_factiva_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.FactivaConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_qde_factiva_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_qde_internal_dedupe_service_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_qde_internal_dedupe_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.InternalDedupeConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_qde_internal_dedupe_retry_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_qde_multi_bureau_service_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_qde_multi_bureau_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.MultiBureauConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_qde_multi_bureau_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_qde_posidex_service_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_qde_posidex_service_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_qde_posidex_service_retry_` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `jlgdl_qde_borrower_qde_posidex_service_second_call_retry_`
- **Topic name (exact in config):** `jlgdl_qde_borrower_qde_posidex_service_second_call_retry_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexSecondCallConsumer` | methods ``computeRecords``
- **Consumer config:** group `jlgdl_qde_borrower_qde_posidex_service_second_call_retry_` | threads `1` | pollTime `6000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class; ⚠️ producer unresolved in-repo

### `los_lms_data_sync_`
- **Topic name (runtime):** `los_lms_data_sync_<tenant>[_env]` — `LoanClosureKafkaProducer` (`LoanClosureKafkaProducer.java` L22-L29); prefix from `LMSLOSSyncConstants.LOS_LMS_SYNC_TOPIC` (`los_lms_data_sync_`).
- **Direction:** accounting **PRODUCES** (closure) → LOS **CONSUMES**.
- **Producer:** `PushLoanAccountClosureDetailsProcessor` | JSON: `external_ref_id`, `entity_type` (`INDIVIDUAL`|`GROUP`), `event_type` (`CLOSURE`) | `PushLoanAccountClosureDetailsProcessor.java` L37-L41.
- **Consumer:** `LmsDataSyncConsumer` → `LmsDataSyncService.syncData` | reads `event_type`, `entity_type`, `external_ref_id` | `LmsDataSyncService.java` L27-L37.
- **Consumer config:** group `los_lms_data_sync_` | threads `2` | pollTime `5000` | maxPollRecords `2` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Contract match (Wave 2):** **ALIGNED** — producer includes `entity_type`; consumer requires it for branch.
- **Null-checked on consumer:** **Partial** — try/catch in service.
- **Publish failure handled:** **N** (**GAP-019**).
- **Dead letter:** **N** | **Consumer idempotent:** **Partial**
- **Gap reference:** none new for this topic.
- **Error handling:** Y (service)
- **Risk flags:** LOS parses `external_ref_id` as `Long` — must be numeric.

### `los_lms_disbursement_sync`
- **Wave 3 (2026-04-17):** Payload keys re-verified: `external_ref_number`, `status`, `tenant_code`, `timestamp`, optional `error_code` / `error_message` — **no `entity_type`** (`LmsMessageBrokerConsumer.java` L192-L207). LOS requires `entity_type` (`DisbursementSyncService.java` L33-L37). **CONFIRMED OPEN** mismatch.
- **Topic name (runtime):** `los_lms_disbursement_sync<tenantCode>[_<environment>]` — `AccountingKafkaProducer` suffix (`AccountingKafkaProducer.java`); producer uses prefix string `"los_lms_disbursement_sync"` (`LmsMessageBrokerConsumer.java` L210).
- **Direction:** accounting **PRODUCES** → LOS **CONSUMES**.
- **Producer:** `LmsMessageBrokerConsumer.sendResultMessageToKafka` | JSON: `external_ref_number`, `status`, `tenant_code`, `timestamp`; on failure adds `error_code`, `error_message` | **no `entity_type` key** (`LmsMessageBrokerConsumer.java` L226-L247). **Correlation:** payload does **not** include `stan` (present in LOS `DisburseLoanAPIUtil.getHeaders` L111).
- **Consumer:** `DisbursementSyncConsumer` → map → `DisbursementSyncService.handleDisbursementSyncRecord` | requires non-blank `entity_type` (`DisbursementSyncService.java` L33-L37) + `external_ref_number`, `status`, `error_code`/`error_message` for failure path.
- **Consumer config:** group `los_lms_disbursement_sync` | threads `3` | pollTime `5000` | maxPollRecords `3` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Contract match (Wave 2):** **MISMATCH** — **`entity_type` absent** in accounting payload, **required** by LOS service (existing summary-table gaps).
- **Null-checked on consumer:** **Partial** — early return on blank ref/entity_type.
- **Publish failure handled:** logs in producer catch (`LmsMessageBrokerConsumer.java` L219-L221).
- **Dead letter:** **N** | **Consumer idempotent:** **Partial**
- **Gap reference:** summary rows **Accounting → LOS sync** + **LOS no-op**; **GAP-019**, **GAP-070**, **GAP-071**.
- **Error handling:** Y
- **Risk flags:** **entity_type**; Redis `dl` TTL (related gaps).

### `meeting_center_details_`
- **Topic name (exact in config):** `meeting_center_details_`
- **Producer (best-effort, literal reference):**
  - `./novopay-mfi-los/src/main/java/in/novopay/los/processor/GetMeetingCenterListProcessor.java`:123 → `executionContext.put("meeting_center_details_list", lastList);`
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/custom/mfi/processor/GetMeetingCentersByLevelProcessor.java`:63 → `executionContext.put("meeting_center_details_list", meetingCenterDetailsList);`
- **Consumer:** service `novopay-platform-payments` | class `in.novopay.payments.collections.mfi.consumer.PopulateMeetingCenterDetailsConsumer` | methods ``computeRecords``
- **Consumer config:** group `collection_meeting_center_details_` | threads `1` | pollTime `100` | maxPollRecords `1` | XML `novopay-platform-payments/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `address_line_1`, `address_line_2`, `address_line_3`, `address_line_4`, `city`, `created_on`, `geocoded_lat_long`, `landmark`, `locality`, `meeting_center_code`, `meeting_center_id`, `meeting_center_name`, `office_id`, `pincode`, `state`, `user_id`, `vtc_id`, `vtc_name`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `notification_email_`
- **Topic name (exact in config):** `notification_email_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-lib/infra-notifications/src/main/java/in/novopay/infra/notifications/producer/NotificationEmailKafkaProducer.java`:14 → `private static final String EMAIL_TOPIC_PREFIX = "notification_email_";`
- **Consumer:** service `novopay-platform-notifications` | class `in.novopay.notifications.broker.NotificationEmailConsumer` | methods ``computeRecords``
- **Consumer config:** group `notification_email_consumer_` | threads `1` | pollTime `1000` | maxPollRecords `10` | XML `novopay-platform-notifications/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `notification_fcm_`
- **Topic name (exact in config):** `notification_fcm_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-lib/infra-notifications/src/main/java/in/novopay/infra/notifications/producer/NotificationFCMKafkaProducer.java`:15 → `private static final String FCM_TOPIC_PREFIX = "notification_fcm_";`
- **Consumer:** service `novopay-platform-notifications` | class `in.novopay.notifications.broker.NotificationFCMConsumer` | methods ``computeRecords``
- **Consumer config:** group `notification_fcm_consumer_` | threads `1` | pollTime `1000` | maxPollRecords `10` | XML `novopay-platform-notifications/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `notification_sms_`
- **Topic name (exact in config):** `notification_sms_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-lib/infra-notifications/src/main/java/in/novopay/infra/notifications/producer/NotificationSMSKafkaProducer.java`:15 → `private final static String SMS_TOPIC_PREFIX = "notification_sms_";`
- **Consumer:** service `novopay-platform-notifications` | class `in.novopay.notifications.broker.NotificationSMSConsumer` | methods ``computeRecords``
- **Consumer config:** group `notification_sms_consumer_` | threads `1` | pollTime `1000` | maxPollRecords `10` | XML `novopay-platform-notifications/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `offline_data_bet_`
- **Topic name (exact in config):** `offline_data_bet_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.OfflineDataConsumer` | methods ``computeRecords``
- **Consumer config:** group `offline_data_bet_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** Y
- **Risk flags:** ⚠️ producer unresolved in-repo

### `offline_data_pd_`
- **Topic name (exact in config):** `offline_data_pd_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.OfflineDataConsumer` | methods ``computeRecords``
- **Consumer config:** group `offline_data_pd_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** Y
- **Risk flags:** ⚠️ producer unresolved in-repo

### `offline_data_td_`
- **Topic name (exact in config):** `offline_data_td_`
- **Producer (best-effort, literal reference):**
  - `./novopay-mfi-los/src/main/java/in/novopay/los/offline/service/CreateOfflineDataProducerService.java`:49 → `String finalTopic = "offline_data_td_";`
  - `./novopay-mfi-los/src/main/java/in/novopay/los/offline/service/CreateOfflineDataProducerService.java`:63 → `String finalTopic = "offline_data_td_";`
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.EtbLanIdConsumer` | methods ``computeRecords``
- **Consumer config:** group `offline_data_td_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `tenant`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `offline_data_test_`
- **Topic name (exact in config):** `offline_data_test_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.OfflineDataConsumer` | methods ``computeRecords``
- **Consumer config:** group `offline_data_test_` | threads `1` | pollTime `3000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** Y
- **Risk flags:** ⚠️ producer unresolved in-repo

### `posidex_actor_inbound_`
- **Topic name (exact in config):** `posidex_actor_inbound_`
- **Producer (best-effort, literal reference):**
  - `./trustt-platform-reporting/src/main/java/in/novopay/batch/posidex_daily/tasklet/ConsumePosidexDailyExtractFileTasklet.java`:34 → `static final String POSIDEX_ACTOR_INBOUND_TOPIC_NAME = "posidex_actor_inbound_";`
- **Consumer:** service `novopay-platform-actor` | class `in.novopay.actor.posidex.PosidexInboundActorConsumer` | methods ``computeRecords``
- **Consumer config:** group `posidex_inbound_actor_consumer` | threads `1` | pollTime `5000` | maxPollRecords `` | XML `novopay-platform-actor/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class

### `posidex_los_inbound_`
- **Topic name (exact in config):** `posidex_los_inbound_`
- **Producer (best-effort, literal reference):**
  - `./trustt-platform-reporting/src/main/java/in/novopay/batch/posidex_daily/tasklet/ConsumePosidexDailyExtractFileTasklet.java`:35 → `static final String POSIDEX_LOS_INBOUND_TOPIC_NAME = "posidex_los_inbound_";`
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/bulk/ucic/writer/SGToUCICUpdateIWriter.java`:43 → `static final String POSIDEX_LOS_INBOUND_TOPIC_NAME = "posidex_los_inbound_";`
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexInboundLosConsumer` | methods ``computeRecords``
- **Consumer config:** group `posidex_inbound_los_consumer` | threads `1` | pollTime `3000` | maxPollRecords `` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `posidex_los_outbound_`
- **Topic name (exact in config):** `posidex_los_outbound_`
- **Producer (best-effort, literal reference):**
  - `./trustt-platform-reporting/src/main/java/in/novopay/batch/posidex_daily/tasklet/CreatePosidexDailyExtractFileTasklet.java`:46 → `static final String POSIDEX_LOS_OUTBOUND_TOPIC_NAME = "posidex_los_outbound_";`
- **Consumer:** service `novopay-mfi-los` | class `in.novopay.los.kafka.PosidexOutboundLosConsumer` | methods ``computeRecords``
- **Consumer config:** group `posidex_outbound_los_consumer` | threads `1` | pollTime `3000` | maxPollRecords `` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class

### `save_mmi_request_response_`
- **Topic name (exact in config):** `save_mmi_request_response_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-lib/infra-transaction-hdfc/src/main/java/in/novopay/infra/api/service/impl/MapMyIndiaReverseGeoCode.java`:78 → `private String mmiTopic = "save_mmi_request_response_mfi";`
  - `./novopay-platform-lib/infra-transaction-hdfc/src/main/java/in/novopay/infra/api/service/impl/MapMyIndiaCloudRoutesFromLatLong.java`:113 → `private String mmiTopic = "save_mmi_request_response_mfi";`
- **Consumer:** service `novopay-mfi-los` | class `UNKNOWN` | methods ``computeRecords``
- **Consumer config:** group `save_mmi_request_response` | threads `1` | pollTime `5000` | maxPollRecords `1` | XML `novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** UNKNOWN
- **Risk flags:** ⚠️ consumer class unresolved

### `session_activity_login_`
- **Topic name (exact in config):** `session_activity_login_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/custom/mfi/employee/processor/LoginPostProcessingProcessor.java`:57 → `actorKafkaProducer.pushDataToKafkaQueue(message.toString(), "session_activity_login_");`
- **Consumer:** service `novopay-platform-actor` | class `in.novopay.actor.utility.SessionActivityLoginConsumer` | methods ``computeRecords`, `processSynchronously``
- **Consumer config:** group `session_activity_` | threads `1` | pollTime `100` | maxPollRecords `1` | XML `novopay-platform-actor/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `data_for_approval`, `new_data`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `session_activity_logout`
- **Topic name (exact in config):** `session_activity_logout`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/custom/mfi/employee/processor/LogoutPostProcessingProcessor.java`:38 → `actorKafkaProducer.pushDataToKafkaQueue(message.toString(), "session_activity_logout");`
- **Consumer:** service `novopay-platform-actor` | class `in.novopay.actor.utility.SessionActivityLogoutConsumer` | methods ``computeRecords``
- **Consumer config:** group `session_activity_` | threads `1` | pollTime `100` | maxPollRecords `1` | XML `novopay-platform-actor/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `task_user_tat_`
- **Topic name (exact in config):** `task_user_tat_`
- **Producer:** `UNKNOWN` (no literal topic reference found in this repo; likely constructed dynamically via framework producerId)
- **Consumer:** service `novopay-platform-task` | class `in.novopay.common.TaskUserTatKafkaConsumer` | methods ``computeRecords``
- **Consumer config:** group `task_user_tat_` | threads `8` | pollTime `3000` | maxPollRecords `1` | XML `novopay-platform-task/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `holiday_list`, `new_task_status`, `task_activity_time`, `task_id`
- **Error handling:** Y
- **Risk flags:** ⚠️ producer unresolved in-repo

### `telemetry_perf_log_`
- **Topic name (exact in config):** `telemetry_perf_log_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/RequestResponseLogFilter.java`:212 → `reqResMessageKafkaProducer.pushDataToKafkaQueue(new JSONObject(telemetryParams).toJSONString(), "telemetry_perf_log_");`
- **Consumer:** service `novopay-platform-audit` | class `in.novopay.audit.consumer.TelemetryConsumer` | methods ``computeRecords``
- **Consumer config:** group `telemetry_perf_log_` | threads `1` | pollTime `5000` | maxPollRecords `50` | XML `novopay-platform-audit/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields):** `UNKNOWN` (consumer code does not use explicit key literals; likely raw string / delegated parser)
- **Error handling:** N
- **Risk flags:** ⚠️ no catch blocks detected in consumer class

### `update_collection_task_details_`
- **Topic name (exact in config):** `update_collection_task_details_`
- **Producer (best-effort, literal reference):**
  - `./novopay-platform-task/src/main/java/in/novopay/task/mfi/consumer/FinnoneCollectionTaskCreationConsumer.java`:141 → `taskKafkaProducer.pushDataToKafkaQueue(taskDetails.toString(), "update_collection_task_details_");`
  - `./novopay-platform-task/src/main/java/in/novopay/task/mfi/consumers/CollectionTaskCreationConsumer.java`:57 → `taskKafkaProducer.pushDataToKafkaQueue(taskDetails.toString(),"update_collection_task_details_");`
- **Consumer:** service `novopay-platform-payments` | class `in.novopay.payments.collections.mfi.consumer.UpdateCollectionTaskDetailsConsumer` | methods ``computeRecords``
- **Consumer config:** group `update_collection_task_details_consumer_` | threads `1` | pollTime `1000` | maxPollRecords `1` | XML `novopay-platform-payments/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `collection_id`, `task_id`
- **Error handling:** Y
- **Risk flags:** none detected by static scan

### `update_customer_loan_details`
- **Topic name (exact in config):** `update_customer_loan_details`
- **Producer (best-effort, literal reference):**
  - `./novopay-mfi-los/src/main/java/in/novopay/los/util/ActorUtil.java`:483 → `losMessageKafkaProducer.pushDataToKafkaQueue(message.toString(), "update_customer_loan_details");`
  - `./novopay-platform-actor/src/main/java/in/novopay/actor/customer/util/UpdateCustomerLoanDetailsConsumer.java`:81 → `actorKafkaProducer.pushDataToKafkaQueue(message.toString(), "update_customer_loan_details_failed");`
- **Consumer:** service `novopay-platform-actor` | class `in.novopay.actor.customer.util.UpdateCustomerLoanDetailsConsumer` | methods ``computeRecords``
- **Consumer config:** group `loan_details_` | threads `1` | pollTime `100` | maxPollRecords `1` | XML `novopay-platform-actor/deploy/application/messagebroker/MessageBroker.xml`
- **Payload schema (key fields, code-evidenced):** `customer_id`, `failure_reason`, `function_sub_code`, `group_created_on`, `group_id`, `is_active`, `is_signatory_one`, `is_signatory_three`, `is_signatory_two`, `loan_account`, `meeting_center_id`, `origination_employee_id`
- **Error handling:** Y
- **Risk flags:** none detected by static scan
