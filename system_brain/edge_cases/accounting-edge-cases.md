# novopay-platform-accounting-v2 — Wave 1 edge cases (mining)

**Date:** 2026-04-10  
**Scope:** `src/main/java` — additive to `novopay-platform-accounting-v2-edge-cases.md` and `.cursor/gaps-and-risks.md` table (disburse Redis, Lms consumer, batch writers, etc.).  
**This file:** New findings **GAP-035..037** plus cross-references to unchanged known patterns.

---

## Edge case: Installment due / bounce SMS writers swallow per-row errors

- **Trigger:** `LoanInstallmentDueNotificationWriter#write` or `LoanInstallmentBounceNotificationWriter#write` hits Kafka/customer-detail failure for one DTO.
- **Current behavior:** `catch (Exception)` logs and continues; chunk can complete without failing the step.
- **Expected behavior:** Skip policy with persisted failures, metrics, or fail chunk for retry.
- **Gap reference:** GAP-035
- **Files:**  
  `batchnew/notifications/loaninstallmentduenotificationjob/LoanInstallmentDueNotificationWriter.java`  
  `batchnew/notifications/loaninstallmentbouncenotificationjob/LoanInstallmentBounceNotificationWriter.java`

## Edge case: Bulk collection failed-record consumer is append-only with no guardrails

- **Trigger:** Message on `bulk_collection_data_failed_` consumed.
- **Current behavior:** Each record value persisted as a new `BulkCollectionLog` row; no validation, dedupe, or exception handling.
- **Expected behavior:** Schema validation, idempotency (offset/partition or business key), DLQ for poison, metrics on failure rate.
- **Gap reference:** GAP-036; `.cursor/event-registry.md` risk flags for same topic
- **File:** `loan/recurring/entity/BulkCollectionFailedRecordConsumer.java`

## Edge case: NOC generation continues with blank pincode after silent customer API failure

- **Trigger:** `getCustomerPincodeFromCustomerId` fails in `getPincode` wrapper path.
- **Current behavior:** Broad `catch`, INFO log with constant message, returns original `pincode` (possibly empty) → file path may omit pincode directory.
- **Expected behavior:** Fail row or use explicit fallback policy with audit.
- **Gap reference:** GAP-037
- **File:** `batchnew/bulknoc/dispatch/generatenocfilejob/GenerateNocFileItemWriter.java`

---

## Already documented elsewhere (do not duplicate as new gaps)

| Topic | Where |
|--------|--------|
| `entity_type` missing on `los_lms_disbursement_sync` | Table + `disbursement_sync_entity_type_missing.md` |
| Redis `dl` + in-flight no TTL on disburse consumer | Table + `LmsMessageBrokerConsumer.java` |
| Time-based `client_reference_number` in batches / multiple writers | Table + `batch_time_based_client_reference_number_replay_risk.md` |
| Proactive excess refund writer swallows exceptions | Table + `proactive_excess_refund_writer_swallow_exceptions.md` |
| Auto-closure writer log-and-continue | Table |
| Death-foreclosure insurance `Pending for FR` partial progress | `death_foreclosure_insurance_pending_fr_partial_progress_blocks_batch.md` |
| CRR lock recovery vs `disbursement_status` | `disbursement_lock_recovery_does_not_set_disbursement_status.md` |
| NEFT stage-2 gate vs context `disbursement_status` | `neft_stage2_initiation_sensitive_to_disbursement_status_context.md` |

Additional **synchronous** posting paths using `new Date().getTime()` / `currentTimeMillis` in `client_reference_number` (same **replay/dedupe class** as table row — extend regression tests if touched):  
`LoanProvisioningPostingService`, `ExecuteLoanAccountRebookingProcessor`, `LoanAccountClosureService`, `LoanProvisioningPostingService`, `ExecuteExcessAmountRefundProcessor`, `PopulateDisbursementCancellationParentAccountDetailsProcessor`, `PenalInterestAccrualBookingServiceBackUp`, `InterestAccrualBookingService`, `LoanAccountBillingService`, `LoanAccountAssetCriteriaProcessor`, `PennyDropUtil`, etc.
