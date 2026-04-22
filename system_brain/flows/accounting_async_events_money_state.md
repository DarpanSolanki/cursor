# Accounting async events + money-state side effects (code-verified)

## Disbursement money movement Kafka contract
- Producer (LOS): `DisburseLoanAPIUtil#callDisburseLoanAPI`
  - topic: `disburse_loan_api_<tenantCode>[_<env>]`
  - payload format: `disburseLoan|<request_json>|<cacheKey>`
- Consumer (Accounting): `LmsMessageBrokerConsumer`
  - invokes orchestration request name derived from Kafka `apiName`
  - uses Redis in-flight lock semantics:
    - producer sets `<cacheKey>` marker to `"in_progress"` (no TTL)
    - consumer lock key = `"dl" + originalCacheKey`
  - publishes results to:
    - topic `los_lms_disbursement_sync_<tenantCode>[_<env>]`

## Disbursement sync side effect (LOS update)
- Consumer: `DisbursementSyncConsumer`
- Service: `DisbursementSyncService#handleDisbursementSyncRecord`
  - updates disbursement process failure reason only
  - returns early when `entity_type` missing

## Closure sync to LOS
- Producer (Accounting): `LoanClosureKafkaProducer`
  - topic: `los_lms_data_sync_<tenantCode>[_<env>]`
  - payload includes: `external_ref_id`, `entity_type`, `event_type=CLOSURE`
- Consumer (LOS): `LmsDataSyncConsumer` delegates to `LmsDataSyncService#syncData(...)`

## Collections allocation + task pipeline topics
- `bulk_collection_data_...`
- `collection_primary_allocation_...`
- `collection_secondary_allocation_...`
- `collection_task_processing_...`
- `collection_task_creation_...`
- `update_collection_task_details_...`

## Loan installment SMS notifications
- topic: `notification_sms_<tenantCode>[_<env>]`
- payload fields: `notification_code`, `account_number`, `due_date`, `due_amount`, `msisdn`, `locale`

## Confidence
- High for the contracts and payload keys described here.

