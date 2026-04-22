# Kafka / Async Events Intelligence (code-verified subset)

## Disbursement orchestration request topic
- Producer: `in.novopay.los.util.DisburseLoanAPIUtil`
- Topic prefix passed to producer:
  - `disburse_loan_api_`
- Payload format (pipe-separated):
  - `disburseLoan|<request_json>|<cacheKey>`

## Disbursement orchestration result/sync topic
- Publisher: `in.novopay.accounting.consumers.LmsMessageBrokerConsumer`
- Topic prefix passed to publisher:
  - `los_lms_disbursement_sync`
- Payload keys:
  - `external_ref_number`, `status`, `error_code`, `error_message`, `tenant_code`, `timestamp`
  - does NOT include `entity_type` (see edge case doc)

## Sync consumer and DB update behavior
- Consumer: `in.novopay.los.kafka.DisbursementSyncConsumer`
- It maps Kafka JSON record keys into ExecutionContext (`executionContext.putAll(clientMap)`)
- Service: `DisbursementSyncService#handleDisbursementSyncRecord(...)`
  - requires `external_ref_number` and `entity_type`
  - returns early if status == SUCCESS

## Closure sync to LOS (`los_lms_data_sync_`)
- Producer: `in.novopay.accounting.loan.closure.component.LoanClosureKafkaProducer`
  - calls `LoanClosureKafkaProducer#pushDataToKafkaQueue(...)`
  - topic prefix: `los_lms_data_sync_` (same as `LOS_LMS_SYNC_TOPIC` + tenant + optional env)
  - payload fields (code-verified by processor):
    - `external_ref_id` (loan external_ref_number)
    - `entity_type` (e.g. `INDIVIDUAL` vs `GROUP`)
    - `event_type` (CLOSURE)
- Consumer: `in.novopay.los.kafka.LmsDataSyncConsumer`
  - reads `event_type`, `entity_type`, `external_ref_id`
  - delegates updates to `LmsDataSyncService#syncData(...)`

## Collections allocation + task pipeline

### Topics produced/consumed (code-verified contracts)
- `bulk_collection_data_<tenantCode>[_<env>]`
  - Producer: `LoanRecurringPaymentItemWriter#write(...)`
  - Payload: `collection_list` + `timestamp` (and per item `col_ext_ref_id`, `due_details`, `customer`, `group_detail`)
  - Consumer: `CreateOrUpdateBulkCollectionConsumer#computeRecords(...)`

- `collection_primary_allocation_<tenantCode>[_<env>]`
  - Consumer: `PrimaryAllocateCollectionConsumer#computeRecords(...)`
  - Payload key: `allocation_data` (array)
  - Contract element uses `external_reference_id`

- `collection_secondary_allocation_<tenantCode>[_<env>]`
  - Consumer: `SecondaryAllocateCollectionConsumer#computeRecords(...)`
  - Contract element uses hardcoded key expectation: `external_id` when creating tasks

- `collection_task_processing_<tenantCode>[_<env>]`
  - Consumer: `CollectionTaskProcessingConsumer#computeRecords(...)`
  - Payload key: `task_creation_data` (array) + `collection_id` per element

- `collection_task_creation_<tenantCode>[_<env>]`
  - Consumer: `CollectionTaskCreationConsumer#computeRecords(...)`
  - Consumer sends internal API and emits `update_collection_task_details_...`

- `update_collection_task_details_<tenantCode>[_<env>]`
  - Consumer: `UpdateCollectionTaskDetailsConsumer#computeRecords(...)`
  - Payload keys: `collection_id`, `task_id`

## Notifications: Loan installment SMS
- Topic: `notification_sms_<tenantCode>[_<env>]`
- Consumer: `novopay-platform-notifications#NotificationSMSConsumer`
  - consumes JSON -> `executionContext.putAll(data)`
  - downstream expects fields like `msisdn`, `notification_code`, `locale` (and template parameters)
- Producer (accounting-v2): `LoanInstallmentDueNotificationWriter#write(...)` and bounce writer
  - pushes JSON fields:
    - `notification_code` = `LMS-LOAN-INSTLM-NOTI-001` (due) or `...-002` (bounce)
    - `account_number`, `due_date`, `due_amount`
    - `locale`, `msisdn`

## Confidence
- High for the contracts enumerated here (disbursement, closure sync, collections allocation pipeline, SMS notification payload keys).

