# `novopay-mfi-los` — Loan Origination System (LOS)

> The "front of the loan" — captures every loan application from lead through underwriting through disbursement-trigger. Disbursement *execution* lives in accounting; LOS just publishes the trigger event. This is the largest service by surface area: **471 Requests** in a single 10 435-line orchestration XML.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.los` |
| DB schema | `mfi_los` |
| Server port | `8013` |
| Code stats | 130 entities, 530 processors, 308 DAOs, 48 services |
| Repo | [`novopay-mfi-los/`](../../novopay-mfi-los/) |
| Service CLAUDE.md | [`trustt-platform-los/CLAUDE.md`](../../trustt-platform-los/CLAUDE.md) |

## API surface — orchestration XML

| File | Lines | Requests |
|---|---:|---:|
| `deploy/application/orchestration/ServiceOrchestrationXML.xml` | 10 435 | 471 |

That single file holds everything. Branching inside Requests is by `function_code` (e.g. `ONBOARDING`, `CONDUCT_BET`, `CONDUCT_PD`, `CM_DASHBOARD`) and `function_sub_code`.

Domains it covers (sample of 60):
- **Lead/loan-app**: `getLeadsByEmployee`, `createOrUpdateLead`, `createOrUpdateLoanApp`, `updateLoanAppStatus`, `updateLoanAppAssignee`
- **KYC/personal**: `createOrUpdateBorrowerKycDetails`, `panValidation`, `voterIdAuthentication`, `eSignInitiateRequest`
- **Bureau/dedup** (async via Kafka): `performInternalMobileDedupe`, `triggerMultiBureauRequest`, `executePostBureauServices`, `getBureauDetails`
- **Eligibility**: `processEligibilityRules`, `processBetEligibilityRules`, `processGroupFormationEligibilityRules`, `getDeviatedRules`, `rejectLoanApplication`
- **Household / financial**: `createOrUpdateFinancialDetails`, `createOrUpdateHouseholdProfile`, `addOrUpdateBorrowerIncomeDetails`
- **Group / FLCC** (SHG/JLG specific): `createOrUpdateGroup`, `getGroupDetails`, `updateGroupSignatories`, `getGroupFlccDetails`, `getGroupSavingAccountDetails`
- **BET / underwriting**: `getBETDetails`, `submitScheduleBet`, `submitGroupConductBet`, `submitGroupConductPdc`, `submitCreditUnderwriting`
- **Documents/dispatch**: `uploadLoanOriginationDocument`, `generateLoanDocuments`, `createOrUpdateDocDispatchTask`, `createEStamp`, `documentVerification`
- **Disbursement-trigger**: `triggerDisburseLoan`, `processLoanAppIdForDisbursementAfterPDC`, `createUpdateOpsTask`
- **Bulk uploads**: `bulkFileToSGSalesPromocodeJob`, `bulkSGToSalesPromocodeJob`, `bulkFileToSGShgCodeJob`, `bulkFileToSGIrrJob`, `bulkFileToSGRiskProfileJob`, `bulkFileToSGReKycDetailsJob`, `amlRiskProfileFile`

## Lifecycle stages — the loan journey

`StageConstants.java` (`/home/darpan/Documents/sliProd/trustt-platform-los/src/main/java/in/novopay/los/constant/StageConstants.java`) defines:

`ONBOARDING` → `QUICK_DATA_ENTRY` (QDE) → `ELIGIBILITY_SUMMARY` (ES) → `LOAN_DETAILS`

CLAUDE.md (line 114) shows the full operational journey:

```
QDE → ES → HHIE (HouseHold Income & Expense) → AD (Address) → DDE (Detailed Data Entry)
    → GFM (Group Formation, SHG/JLG only) → BET (Borrower Engagement Tool)
    → CUWRTR (Credit Underwriting) → Document Management → CPDC (Credit Policy Doc Check)
    → Disbursement-trigger
```

Loan-type variants (`PslTypeRuleStageEnum`):
- `LOAN_JLG` — Joint Liability Group
- `LOAN_SHG` — Self-Help Group
- `LOAN_IND` — Individual

Per-stage status enums live under [`src/main/java/in/novopay/los/enums/`](../../novopay-mfi-los/src/main/java/in/novopay/los/enums/) — `LeadDetailsStatusEnum`, `RuleStatusEnum`, `FlccStatusEnum`, `GroupStatusTypeEnum`, etc.

## Kafka

Producer: `producer_id_los`. Disbursement is published by [`DisburseLoanAPIUtil`](../../trustt-platform-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java) onto topic `disburse_loan_api_<tenant>` with format `disburseLoan|<json>|disburseLoan{productId}_{externalRefNumber}`. Result event is consumed back from accounting.

Consumer landscape (17 bean types, ~20 topic prefixes — full list in `MessageBroker.xml`, lines 1–994):

| Consumer bean | Topic prefix(es) | Purpose |
|---|---|---|
| `disbursementSyncConsumer` | `los_lms_disbursement_sync` | **Inbound from accounting** — disbursement result. Critical path; 3 threads |
| `lmsDataSyncConsumer` | `los_lms_data_sync_` | LOS↔LMS data sync |
| `factivaConsumer` | `indl_qde_borrower_*_factiva_*`, `jlgdl_*` | Bureau eligibility (Factiva) |
| `posidexConsumer` / `posidexSecondCallConsumer` | `indl_qde_borrower_*_posidex_*` | Posidex bureau (2-call) |
| `multiBureauConsumer` | `indl_qde_borrower_*_multi_bureau_*` | Multi-bureau merge |
| `internalDedupeConsumer` | `indl_qde_*_internal_dedupe_*` | Internal mobile dedupe |
| `offlineDataConsumer` / `etbLanIdConsumer` | `offline_data_bet_`, `offline_data_pd_`, `offline_data_td_` | Offline data ingest (BET/PD/TD) |
| `ckycApiKafkaConsumer` | `ckyc_preprocess_api_` | CKYC preprocessing |
| `geoTrackerAuditConsumer` / `geoTrackerLoginLogoutAuditConsumer` | `geo_tracking_*` | Geo audit |
| `posidexInboundLosConsumer` / `posidexOutboundLosConsumer` | `posidex_los_*` | Posidex sync |
| `generateConsentDocumentConsumer` / `generateSpecificLoanDocumentConsumer` | `generate_consent_doc_`, `generate_specific_loan_doc_` | Async doc generation |
| `mmiRequestResponseLogConsumer` | `save_mmi_request_response_` | MMI request/response logging |

Pattern: `indl_*` for Individual loans, `jlgdl_*` for JLG/SHG group loans, `qde`/`conduct_pd`/`conduct_bet`/`cm_dashboard` per stage, `_retry` suffix for retry topics.

## Outbound HTTP — what LOS calls

Hot path (per loan application):

| Service | What it calls |
|---|---|
| accounting | `disburseLoan` (Kafka path), `getScheduleDetails`, `getLoanAccountDerivedData`, `getCustomerLoanAccountBounces`, product/scheme lookups |
| approval | `submitApplication` (CU + disbursement maker-checker) |
| actor | `getCustomerDetails`, `getEmployeeDetails`, `getOfficeDetails`, hierarchy resolution |
| task | `createAndCompleteTask`, `getRoleCodesByTaskIds` |
| BPMN | `startProcess`, status checks |
| dms | upload/download |
| masterdata | `masterDataValidator`, code masters |
| consents | Aadhaar / loan consent |

Occasional / batch: authorization (role checks), notifications (alerts), batch (bulk CKYC, reKYC, IRR, SHG code, Udyam).

## DB clusters (~48 core tables)

| Cluster | Representative tables |
|---|---|
| Loan-app core | `loan_app`, `loan_app__customer_details`, `loan_app__declaration_details`, `loan_app_process`, `loan_app__disbursement_tracking` |
| BET / DDE | `loan_app__bet_details`, `mapped_questionnaire`, `mapped_question`, `question_master`, `follow_up_question_master` |
| Group / FLCC | `group_details`, `group__member_details`, `group__process`, `group__signatory_change_reason`, `loan_app__flcc_group(_member)` |
| Borrower / KYC | `borrower_reference`, `borrower_stability`, `aadhaar_ref_mapping`, `aadhaar_redaction_status`, `re_kyc_details` |
| Bureau / Posidex | `posidex_status_log`, `multi_bureau_obligation_master`, `multi_bureau_amount_tenure_obligation_master`, `credit_promocode_details` |
| Documents / dispatch | `doc_generation_status`, `document_dispatch`, `estamp_details`, `estamp_charge_details` |
| Disbursement | `disburse_loan_process`, `disbursement_failure_history` |
| Workflow / audit | `entity__step_sub_step_status`, `entity__step_sub_step_status_history`, `activity_sub_category`, `ops_rejected_reason_history` |
| Bulk staging | `file_staging_migration_data`, `migration_data`, `udyam_failure_history` |

## Caching (Redis)

| Where | Index | Why |
|---|---|---|
| Disbursement idempotency | ACCOUNTING (DB 5) | `dl<…>` key set in `DisburseLoanAPIUtil`; cleared post-completion. **No TTL — open gap (see [`../gaps-and-risks.md`](../gaps-and-risks.md))** |
| KYC OTP / Aadhaar | DEFAULT | `CreateOrUpdateBorrowerKycDetailsProcessor` |
| Product config | service-specific (`losCacheManager`) | `LosProductConfigDaoService` `@Cacheable` |

## Batch jobs (placeholders, no `@Scheduled`)

`BatchJobPlaceholderConfig.java` declares: `posidexFinnoneBatch`, `updatePosidexExtBatch`, `triggerCkycApiCallBatch`, `ckycInputDataBatch`, `ckycRejectedDataBatch`, `ckycSuccessDataBatch`, `bulkFileToSGSalesPromocodeJob`, `bulkFileToSGShgCodeJob`, `bulkFileToSGIrrJob`, `bulkFileToSGRiskProfileJob`, `bulkFileToSGReKycDetailsJob`, `triggerRejectConductBetTask`, `triggerRejectGroupBetTask`, `triggerRejectIndividualBetTask`, `triggerRejectPdcTask`. All triggered by `novopay-platform-batch` (no in-process cron).

## Known gotchas / invariants

1. **Single 10k-line orchestration XML** — when grepping for `<Request name="…"`, the match is in this one file. Heavy use of `Control` branching on `function_code`/`function_sub_code`.
2. **Many `explicitTxnMgmt="true"` Requests** — examples: `createOrUpdateFamilyMemberDetails`, `submitScheduleBet`, `submitAcceptBetTask`, `createEStamp`. Multi-step flows span multiple txn boundaries.
3. **Kafka consumer matrix is large** — same bean reused across many topics (per stage × per loan-type × per retry/non-retry).
4. **Heavy inter-service dependency chain** — actor, accounting, approval, task, BPMN. Latency in any of those cascades.
5. **Disbursement Redis dedup key has no TTL** — a crashed disburseLoan attempt leaves a permanent in-progress key blocking retries. Documented in [`../gaps-and-risks.md`](../gaps-and-risks.md).
6. **LOS error codes** — standard mandatory `130001-130099`, pattern `132001-132099`, plus LOS-specific via `mfi_notifications` (service_name = 'LOS').

## When you're working on this service

- A **new stage** → look at `StageConstants.java` + the stage-specific Requests in `ServiceOrchestrationXML.xml` + the corresponding Kafka topics (per-stage retry pattern).
- A **disbursement issue** → see [`../runbooks/disbursement-stuck.md`](../runbooks/disbursement-stuck.md) and [`../accounting/05-flows.md`](../accounting/05-flows.md) §1 — LOS-side ends at the Kafka publish; everything after is in accounting.
- A **group/SHG/JLG flow** → cross-link to [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md) for the LMS view of the same loan.
- A **bureau call** → consumers + retry topic per bureau provider; failure semantics are async retry, not user-facing block.
