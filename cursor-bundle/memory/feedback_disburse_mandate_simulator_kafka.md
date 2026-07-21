# Local INDL disburse — mandate + simulator + Kafka Redis (2026-07-20)

## Mandate fixture (DIRDR/ACH)
- Validator needs ACTIVE/REGISTRATION_PENDING `repayment_mandate_details` **linked** to `repayment_account_details` whose `account_number` matches request `REP_ACCT`.
- Null `repayment_account_details_id` fails before loan create (134348 path).
- Suite: `disburse_loan_sanity._seed_repayment_mandate_for_loan_app_id` + reset SQL vars `repayment_account_*` from request JSON. Fail closed if link/CASA mismatch.

## Simulator
- `localhost:8018` required: GST SOAP during postTransaction before schedule/dues. Preflight `simulator_tcp` is mandatory (not optional).

## Kafka Redis (TDPQA-54)
- Topic `disburse_loan_api_mfi_local`, group `disburse_loan_api_consumer_mfi_local`.
- Redis DB 5 keys `localmfi_<cacheKey>` (producer) / `localmfi_dl<cacheKey>` (consumer), TTL ~600000ms.
- Direct HTTP Accounting `disburseLoan` does **not** take these locks — Kafka consumer path does.
- **E2E:** `bash scripts/bin/disburse-indl-kafka-quick.sh` (ensures los+accounting+sim; fail-closed preflight).
- Message: `disburseLoan|{json}|disburseLoan{productId}_{INDL|JLG|SHG}_{extRef}|{ownerToken}`.
- See also `feedback_disburse_kafka_e2e_los_ensure.md`.
