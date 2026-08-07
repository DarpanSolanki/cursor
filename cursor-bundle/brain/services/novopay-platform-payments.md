# `novopay-platform-payments` — Loan Collection System (LCS)

> Owns the field/branch/digital collection lifecycle: capture, allocation (primary/secondary), batch (cash deposit), supervisory review, PTP (Promise-to-Pay) calendars, and integration with **Finnone** (legacy LMS via file interface) and **VYMO** (collections handoff at DPD > 30). Posts settled collections back to accounting via `collectionLoanRepayment`.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.payments` |
| DB schema | `mfi_payments` (inferred — entities use unqualified `@Table`) |
| Repo | [`novopay-platform-payments/`](../../novopay-platform-payments/) |
| Service .cursorrules | [`trustt-platform-payments/.cursorrules`](../../trustt-platform-payments/.cursorrules) |
| Code | 37 core entities; ~258 Requests |

## API surface — orchestration XMLs

| XML | Lines | Requests | Purpose |
|---|---:|---:|---|
| `orc_mfi.xml` | 3 635 | 178 | MFI collection flows (record attempts, payment-link, schedule push, batch generation, bulk Finnone/VYMO/NACH jobs, Razorpay/Easebuzz, portfolio transfer, demand list, PTP calendar) |
| `orc_collections.xml` | 1 521 | 71 | Core collection: `createCollection`, `updateCollection`, `doCollections`, `doMfiCollections`, `doMfiBranchCollection`, `doMfiFieldCollection`, allocation primary/secondary, batch, attempt, payment, recon, MIS reports |
| `orc_mfi_cross_schema.xml` | 300 | 7 | Cross-schema reads: `getCollectionsList`, `getCollectionCountForCollectorV2`, `getIndividualCollectionDetailsV2`, `getGroupCollectionDetailsV2`, `getPriorityCollectionDetails`, `getPriorityCountForCalendar`, `getCollectionInfoList` |
| `product_accounting.xml` | 18 | 2 | **The bridge to accounting** — `collectionLoanRepayment`, `recurringPayment` |

Top requests per .cursorrules (line 76):
`createOrUpdateRecordAttempt1`, `generatePaymentLink`, `checkPaymentStatus`, `updatePaymentStatus`, `fetchLMSUpdate`, `getScheduleDetails`, `updateSchedulePayment`, `pushPendingLMSUpdates`, `generateBatch`, `getScheduledBatchList`, plus the 13 bulk-file pairs (Finnone static/dynamic/reverse/correction, VYMO sync, NACH).

## Kafka

Producer: `producer_id_payments`.

| Consumer | Topic prefix | Purpose |
|---|---|---|
| `populateCollectionCustomerDetailsConsumer` | `collection_customer_details_*` | Customer details cache for collection |
| `populateMeetingCenterDetailsConsumer` | `meeting_center_details_*` | Meeting-centre cache |
| `createOrUpdateBulkCollectionConsumer` | `bulk_collection_data_*` | **High-priority bulk ingest** (poll 1500 ms) |
| `collectionOfficeDetailsConsumer` | `collection_office_details_*` | Office details cache |
| `updateCollectionTaskDetailsConsumer` | `update_collection_task_details_*` | Task sync from task service |
| `primaryAllocateCollectionConsumer` | `collection_primary_allocation_*` | Async primary allocation |
| `secondaryAllocateCollectionConsumer` | `collection_secondary_allocation_*` | Async secondary allocation |
| `collectionTaskProcessingConsumer` | `collection_task_processing_*` | Task processing |

There is **no inbound Kafka from accounting/LOS** — collection-posting → accounting is a sync HTTP call (`product_accounting.xml`).

## Outbound HTTP

| Service | Calls |
|---|---|
| accounting | `collectionLoanRepayment`, `recurringPayment`, `loanRepayment`, `loanPrepayment`, `loanAccountPartPrepayment`, `loanDisbursementCancellation` |
| actor | `getEmployeeDetails`, `getEmployeeData`, `getCustomerDetailsForCollection`, `getOfficeDetails`, `getBasicGroupDetails`, `getRoleFromAdid`, `getEmployeeHierarchyDetails` |
| notifications | reminder templates, receipt notifications, PTP calendar messages (Redis NOTIFICATION DB 2) |
| task | `createOrUpdateTaskForCollectionBatch`, `createOrUpdateCollectionLeadTask`, `createTaskForNewMfiCollections` |
| masterdata | config + code/value lookups |

How collections post to accounting: `MfiCollectionsDAOService` → `PushLMSUpdateProcessor` → `callInternalAPI()` → `product_accounting.xml::collectionLoanRepayment`.

## DB clusters

| Cluster | Tables |
|---|---|
| Collections core | `collection`, `collection_history`, `collection_office_info`, `collection_meeting_center_info`, `collection_payment_tracking_details`, `collection_visit_details`, `collection_activity` |
| Attempts / audit | `collection_attempts`, `collection_attempt_activity_mapping`, `collection_attempt_history`, `trial_visit_place`, `trial_person_contacted`, `trial_outcome`, `collection_consent_info` |
| Finnone | `collection_finnone_loan_info`, `collection_finnone_reference`, `collection_finone_extention`, `collection_finone_reverse`, `collection_finnone_addresses`, `collection_group_casa_cds_details` |
| VYMO | `collection_vymo_np_agency_extract`, `collection_vymo_np_coll_report`, `collection_vymo_np_hand_off_file`, `collection_vymo_np_rac_cases`, `collection_vymo_np_reverse_hand_off`, `collection_vymo_status` |
| Reconciliation / CDS | `batch_denominations_recon_details`, `cash_denominations_serial_numbers`, `cds_rectification_details`, `collection_rectification_details` |
| File staging (bulk) | `file_staging_*` (confirm_payment, static_dt_type, dynamic_one/two, excel_agency, np_*, finnone_loan_correction, etc.) |
| Supervisory | `supervisory_dashboard_review_details`, `collection_sup_review_task_mapping` |
| Other | `collection_customer_contact_details`, `collection_employee_info`, `collection_external_info`, `bulk_upload_file_details`, `foreclosure_customer_interaction_state`, `priority_calendar_loan_details` |

## Batch jobs (~48 scheduled)

Three patterns, all triggered by the batch service:

- **`bulkFileToSG…`** — file → staging (ingest). Examples: `bulkFileToSGConfirmPaymentJob`, `bulkFileToSGFinoneReverseJob`, `bulkFileToSGNpHandoffJob`, `bulkFileToSGPriorityCalendarJob`.
- **`bulkSGTo…`** — staging → core (apply). Examples: `bulkSGToConfirmPaymentJob`, `bulkSGToFinoneReverseJob`, `bulkSGToNpHandoffJob`.
- **Outbound / sync to vendors** — `bulkOutboundNpAgencyExtractJob`, `bulkOutboundNpHandOffFileJob`, `bulkOutboundNpRacCasesJob`, `collToStagNpAgencyExtractJob`, etc.
- **Reminders** — `reminderForPtpCalenderCustomerJob`, `reminderForPtpCalenderUserJob(Rm)`, `collectNowGenerateReceiptNotificationJob` (+ `RM`, `CH` variants).
- **Cash deposit** — `cashDepositCutoffTimeElapsedForCollectorJob`.
- **Finnone inbound** — `runInboundFinoneJob`, `runInboundStaticFinoneJob`, `runFinoneReverseJob`, `runInboundNpHandoffJob`, `runInboundNpRevTrailsJob`.

`BatchJobPlaceholderConfig.java` is the registry.

## External integrations

- **Razorpay / Easebuzz** — payment gateway: `createRazorpayOrder`, `updateRazorpayOrderStatus`, `initiateEasebuzzPayment`. Receipt-no logic skips re-generation if Razorpay-issued.
- **NACH / Mandate** — handled as collection mode/reference (no dedicated NACH table here; mandate presentation/representation lives in **accounting**).
- **NEFT / UPI / Bank** — UPI in `collection_payment_tracking_details.payer_upi_id`; NEFT via bank-deposit batches.
- **Finnone (legacy LMS)** — file interface inbound (static 0/1, dynamic 0/1, reverse, correction, handoff) + outbound (agency extract, coll report, RAC, trial history, reverse handoff). Heavy Redis cache (DB 0; 10 h TTL on `finnone_static_product_list`, employee/office mappings, formatted-id maps).
- **VYMO** — outbound when DPD > 30: handoff, RAC, reverse, trial history. Async file feed.

## Concepts owned

- **Collection** = one repayment attempt against a loan (or group of loans). Has lifecycle states (recorded → confirmed → settled → reversed).
- **Allocation** — primary (assigned to a collector) and secondary (re-assigned). Async via Kafka.
- **Batch (cash deposit)** — collector aggregates cash collected → deposits at branch → batch created → reconciled with denominations.
- **Supervisory review** — `forwardSupervisoryReview → reassignSupervisoryReview → submitSupervisoryReview → updateSupervisoryReviewStatus`. Separate task entity + approval.
- **PTP calendar** — Promise-to-Pay tracking, reminders to customer + RM.
- **Portfolio transfer (LCS side)** — `executeLCSPortfolioTransfer` validates via actor + LCS checks (`validateLCSRestrictedActivitiesForPTrfr`).

## Known gotchas

1. **Data-heavy schema** — 37+ tables, many relationships. Performance is a recurring concern.
2. **Finnone cache dependency** — jobs degrade if Redis keys cleared mid-run; fallback is empty-data, which can silently drop records.
3. **258 Requests across 4 XMLs** — same names can appear in >1 XML; load order matters.
4. **Heavy actor usage** — actor latency cascades to collections + batch jobs.
5. **No NACH-specific table here** — mandate flows live in accounting (`enach_*`, `si_*`).
