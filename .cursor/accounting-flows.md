# Accounting service (`novopay-platform-accounting-v2`) — flow maps

**Deep reference**: `.cursor/rules/accounting.mdc` (Module reference section: transaction types, column semantics, NEFT/MFT/CLMT). **Curated money-path runbooks**: `system_brain/flows/*.md` (indexed in `.cursor/architecture.md` §12). **Posting engine notes**: `system_brain/accounting/posting_engine.md`.

**Implementation patterns / tests**: `.cursor/docs/patterns-and-examples.md`, `anti-patterns.md`, `testing-patterns.md`, `faq.md`.

## `system_brain/flows/` — what to open for which symptom

| Symptom or task | Open first |
|-----------------|------------|
| Async disburse, Redis `dl` key, LOS sync missing updates | `flows/disbursement.md` + `flows/accounting_async_events_money_state.md` |
| Repayment GL wrong / NPA reverse leg | `flows/repayment_posting.md` |
| Foreclosure, write-off, disb cancellation API, excess refund, rebooking posting | `flows/prepayment_foreclosure_writeoff_refund_rebooking_posting.md` |
| NEFT callback vs inquiry, UTR, CLMT queue | `flows/bank_callbacks_inquiries.md` |
| Insurance file inbound → DCF or disb-cancel posting | `flows/insurance_inbound_posting.md` |
| Disb-cancel batch + GST reversal flags | `flows/disbursement_cancellation_tax_reversal.md` |
| Year-end / GL zeroisation missing lines | `flows/gl_balance_zeroisation_posting.md` |
| `reverseTransaction`, manual JE, `134067` | `flows/reversals_manual_journal_transaction_engine.md` |

## Runtime entry points (verified)

### 1. HTTP (synchronous)

- **Controller**: **`ServiceGatewayController`** in `novopay-platform-lib/infra-service-gateway` — `POST /api/{apiVersion}/{apiName}` (not re-declared in accounting-v2).
- **Dispatch**: `RequestProcessorImpl` → `ServiceOrchestrator` for the tenant’s orchestration XML.
- **Spring scan**: `Application.java` uses `@ComponentScan("in.novopay")` so accounting processors under `in.novopay.accounting.*` and infra beans under `in.novopay.infra.*` load together.

### 2. Kafka (asynchronous) — beans wired in `MessageBroker.xml`

Only **two** `NovopayMessageBrokerConsumer` implementations exist under `novopay-platform-accounting-v2/src/main/java` (repo grep):

| Class | Topic prefix (XML) | Bean name in XML |
|-------|-------------------|------------------|
| `in.novopay.accounting.consumers.LmsMessageBrokerConsumer` | `disburse_loan_api_` | `lmsMessageBrokerConsumer` |
| `in.novopay.accounting.loan.recurring.entity.BulkCollectionFailedRecordConsumer` | `bulk_collection_data_failed_` | `bulkCollectionFailedRecordConsumer` |

Disburse message shape and Redis lock semantics: `system_brain/system_overview.md`, `system_brain/events/kafka_topics.md`.

### 3. Spring Batch

- Job config and writers live under `in.novopay.accounting.batchnew.*` and related packages; **inventory** with posting call-sites: `system_brain/batch_jobs/batch_inventory.md`.

---

## Orchestration files (do not skip)

Under `deploy/application/orchestration/`:

- `ServiceOrchestrationXML.xml` — product/GL/master utilities + bulk jobs (largest Request count).
- `loans_orc.xml` — loan servicing APIs including **`disburseLoan`**, repayment, foreclosure, billing, cancellation, etc.
- `product_transaction_orc.xml` — **`postTransaction`**, statements, reversals, manual JE, portfolio transfer.
- `mfi_orc.xml`, `group_mfi_orc.xml` — MFI/group variants.
- `loans_insurance_orc.xml`, `insurance_orc.xml` — insurance-related requests.
- `product_transaction_accounting_definition_orc.xml` — catalogue/definition style requests.
- `loans_notification.xml` — notification hooks.

**Request counts** for this repo snapshot: see table in `.cursor/architecture.md` §3.

---

## Ledger spine: `postTransaction` (XML-verified processor order)

Source: `deploy/application/orchestration/product_transaction_orc.xml` — Request opens at **line 3**.

```3:34:novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml
	<Request name="postTransaction">
		<Processors>
			<Processor bean="validateTransactionDataProcessor" />
			<Processor bean="populateAdditionalInformationProcessor" />
			<Processor bean="populateAndValidateAccountDetailsProcessor" />
			<Processor bean="populateAdditionalAmountProcessor" />
			<Processor bean="clientReferenceNumberDedupProcessor" />
			<Processor bean="getTransactionCatalogueIdProcessor" />
			<Processor bean="getTransactionRuleListProcessor" />
			<Processor bean="executeTransactionRulesProcessor" />
			<Control method="regExp" pattern="${run_mode}" condition="=" value="TRIAL">
				<Processor bean="populateLimitRequestProcessor" />
				<Processor bean="validateActorAccountBalanceProcessor" />
				<Processor bean="createTransactionResponseProcessor" />
				<Processor bean="validateLimitProcessor" />
			</Control>
			<Control method="regExp" pattern="${run_mode}" condition="=" value="REAL">
				<Processor bean="generateTransactionReferenceNumberProcessor" />
				<Processor bean="createTransactionMasterProcessor" />
				<Processor bean="createTransactionMetadataProcessor" />
				<Processor bean="createTransactionPartitionDetailsProcessor" />
				<Processor bean="createTransactionDetailsProcessor" />
				<Processor bean="createTransactionResponseProcessor" />
			</Control>
		</Processors>
	</Request>
```

**Plain English**: validate → expand placeholders → dedupe client ref → load catalogue/rules → execute engines → TRIAL (limits) or REAL (persist master/partitions/details + response).

Java classes live under `in.novopay.accounting.transaction.processor` (see `accounting.mdc` for narrative).

---

## `disburseLoan` — where it starts in XML (verified)

`deploy/application/orchestration/loans_orc.xml` — `<Request name="disburseLoan">` at **line 580** (validators + long processor chain; includes nested `<API>` to `getLoanAccountDetails` at line 607+).

Trace the full chain with:

`grep -n 'Request name="disburseLoan"' loans_orc.xml` then read until the closing `</Request>`.

---

## Representative flows (summary)

| Flow | Entry | Ledger | Notes |
|------|--------|--------|--------|
| Disbursement | HTTP / `LmsMessageBrokerConsumer` | Often via posting in flow | Bank leg + CRR + Redis; sync to LOS |
| Repayment | `loanRepayment` in `loans_orc.xml` | `postTransaction` | Dues, excess |
| EOD accrual | Batch → internal API | `postTransaction` INTEREST/* | See batch_inventory |
| DCF | Batch writers | `postTransaction` DEATH_FORECLOSURE* | Insurance staging |
| Disb cancel | API + batch | `postTransaction` LOAN_DISB_CNCL | Tax reversal processors |

## Flow ↔ orchestration ↔ code (from `system_brain/flows`)

- **Disbursement**: ORC `disburseLoan` (`loans_orc.xml` ~L580+). Kafka: `DisburseLoanAPIUtil` → `disburse_loan_api_` → `LmsMessageBrokerConsumer` → sync topic `los_lms_disbursement_sync` (payload **without** `entity_type`; LOS requires it for some paths). Status: `CallBankAPIForDisbursementProcessor` (orchestrates; parent MFT/NEFT bank + inquiry via `ParentDisbursementBankCallService` (`loan.disbursement.bank.parent`: MFT / NEFT v1 / NEFT v2 collaborators) + `DisbursementBankCallTypeUtil`), `CallBankAPIForIndividualChildLoanDisbursementProcessor` + `ChildDisbursementBankCallService` (`loan.disbursement.bank.child`: MFT / NEFT v1 / NEFT v2 + CLMT queue sync helpers), `DoGenericSyncSTPBankNeftCallBackProcessor`, lock recovery gap per `flows/disbursement.md`. **Payment reinit (`REINITIATE_BANK`, NEFT `OTHBACCT` / `mfi_orc.xml`)**: `LmsMessageBrokerConsumer` does **not** treat `ACTIVE` + `disbursement_status=COMPLETED` as skip when `function_sub_code` parsed from the Kafka body is `REINITIATE_BANK`; NEFT v2 persists CRR with `DISBURSEMENT_NEFT_NEF` / `DISBURSEMENT_NEFT_NEI` + `DISBURSEMENT_NEFT_CRR_REINIT_SUFFIX` (`_REINIT`); `ExternalReferenceNoUtil` multi-type lookup keeps the **`03`** external-ref counter aligned across original + reinit rows; STP NEF callback parent resolution tries NEF then NEF+`_REINIT` by client ref. **Child CLMT NEFT v2 inquiry**: `CallBankAPIForIndividualChildLoanDisbursementProcessor.performNEFTTransactionInquiry` matches parent when a NEF CRR already exists — if `disbursement_status` is still `DTFC_SUCCESS`, `DO_TRANSACTION=false` so batch replay does not re-fire duplicate `ST_NEF`; only `NEFT_STAGE_1_SUCCESS` / `NEFT_STAGE_2_PENDING` allow the next leg (`ST_NEI`). **ST_NEI**: duplicate initiation is skipped when a successful child-scoped `..._NEFT_NEI` CRR exists, for both `NEFT_STAGE_1_SUCCESS` and `NEFT_STAGE_2_PENDING`.
- **Parent payment reinit validation snapshot (2026-04-22):** scenario reruns on parent MFT + NEFT confirmed CRR lane typing on `DISBURSEMENT_MFT_REINIT` / `DISBURSEMENT_NEFT_REINIT`, forward reference progression per attempt, and acceptance of explicit second reinit after fresh mode update; replay/idempotency suppression remains a separate targeted verification track.
- **L1 recovery gate (2026-04-15):** for child NEFT lanes where queue status remains `DTFC_SUCCESS` but a prior child-scoped `..._NEFT_NEF` CRR exists with non-success state (`FAIL`/`UNKNOWN`/blank), retry runs stage-1 **inquiry** (`NeftStage1InquiryGate` / shared rule) instead of hard-skipping, so bank state is reconciled before a controlled ST_NEF re-init when appropriate.
- **Parent NEFT v2 inquiry parity (2026-04-16):** `CallBankAPIForDisbursementProcessor.performNEFTTransactionInquiry` uses the same `NeftStage1InquiryGate` as child (`DTFC_SUCCESS` + non-success NEF CRR → run inquiry), aligning JLG recovery with SHG/CLMT semantics.
- **ST_NEF double-debit guard (2026-04-16):** parent and child `doNEFTTransaction` paths skip initiating ST_NEF when `client_request_response_log` already has **`status=SUCCESS`** for the same scoped `transaction_type` (same deterministic ref family).
- **Parent ST_NEI idempotency parity (2026-04-16):** `CallBankAPIForDisbursementProcessor` skips ST_NEI when a **SUCCESS** CRR exists for the orchestration-scoped `…_NEFT_NEI` `transaction_type`, for **both** `NEFT_STAGE_1_SUCCESS` and `NEFT_STAGE_2_PENDING` (child already did); `doNEFTTransaction` re-checks before `neftPaymentV2Stage2`.
- **Child NEFT v2 CRR `transaction_type` (2026-04-16):** `PostNEFTChildLoanBankDisbursementProcessor` resolves child-scoped `…_EXTREF{n}_NEFT_NEF` / `…_NEFT_NEI` when the WebClient callback context omits `transactionIdentifier`, so every child NEFT v2 bank response row persists a non-blank `transaction_type` for callbacks and forensics.
- **L0 deterministic lane selection (2026-04-15):** child bank-retry CRR selection is now lane-scoped by mode/type (`MFT` vs child `..._NEFT_NEF` first, then `..._NEFT_NEI` fallback for NEFT) instead of picking the latest row from a mixed type list. This reduces timing-driven inquiry variance when callbacks and parent retries overlap.
- **CRR response-fidelity invariant (2026-04-14 brain sync):** In WebClient callback flows, CRR `status` and CRR `response` must come from the same callback payload source-of-truth. Child NEFT and child MFT post-processors follow this (callback `apiResponse` or explicit null-envelope); historical child MFT mismatch was tracked as `GAP-061` and is now resolved.
- **Repayment**: `loanRepayment` + nested **`postTransaction`** (TRIAL/REAL/NPA reverse); group: `childLoanRepayment` in `group_mfi_orc.xml` — see `flows/repayment_posting.md`.
- **Foreclosure / write-off / cancel / refund / rebooking**: Request names and `postTransaction` IParam shapes — `flows/prepayment_foreclosure_writeoff_refund_rebooking_posting.md`.
- **GL zeroisation**: Request `glBalanceZeroisation` — **not** the generic `postTransaction` chain; dedicated processors through `createTransactionDetailsProcessor` — `flows/gl_balance_zeroisation_posting.md`.
- **Reversal / manual JE**: `reverseTransaction`, `postManualJournalEntry`, `reverseManualJournalEntry` — `flows/reversals_manual_journal_transaction_engine.md`.
- **Insurance pipelines**: `runInbound*` / `inbound*` / `deathForeclosureInsuranceJob` / `bulkSGToDisbursementCancellationJob` / `bulkSGToPostDisbursementInsuranceUpdateJob` (**last has no ledger posting**) — `flows/insurance_inbound_posting.md`.

---

## Integrations

- **Actor / Payments / Task / Approval / Masterdata**: orchestration `<API>` steps or `NovopayInternalAPIClient` from processors.
- **Bank**: JTF + `infra-transaction-hdfc` (and other partners) — templates under `deploy/application/templates/`.

## Data model & constraints (mfi_accounting)

**Datasource discovery (local defaults used by services):**

- Accounting-v2 points the **platform master registry** to Yugabyte YSQL on `127.0.0.1:5433`, db `yugabyte` (used by `ServiceRegistry` / api_master lookups):  
  `novopay-platform-accounting-v2/src/main/resources/application.properties` L22-L28.
- The accounting domain schema is **`mfi_accounting`** (table definitions captured in codegen artifact dump):  
  `trustt-platform-ai-codegen-artifacts/sli/schema_structure/schema_structure_dump/mfi_accounting_structure.sql` L25.

**Constraints (codegen schema dump; representative “hard” invariants):**

- **`mfi_accounting.loan_account` primary key**: `PRIMARY KEY((account_id) HASH)`  
  `.../mfi_accounting_structure.sql` L11281-L11353.
- **`mfi_accounting.loan_account.external_ref_number` is NOT NULL** (key idempotency/correlation field):  
  `.../mfi_accounting_structure.sql` L11315-L11317.
- **`mfi_accounting.transaction_master.client_reference_number` is NOT NULL** (dedupe key used by `ClientReferenceNumberDedupProcessor`):  
  `.../mfi_accounting_structure.sql` L29123-L29128.
- **`mfi_accounting.client_request_response_log` is write-audit critical** (`partner`, `client_reference_number`, `request`, `response`, `status` are NOT NULL; PK on `id`):  
  `.../mfi_accounting_structure.sql` L2387-L2404.

**Entity surface (accounting-v2 code):**

- Accounting-v2 contains **166** `*Entity.java` classes under `src/main/java` (JPA mapping layer). DB-level constraints are primarily enforced in the **schema** (dump above) + processor/service validations (not via `@UniqueConstraint` annotations).

## Error handling / idempotency

- **NovopayFatalException** → rollback (implicit txn) → FAIL response.
- **NovopayNonFatalException** → undo processors when configured.
- **Idempotency**: Redis + `disburseLoan` cache key; `clientReferenceNumberDedupProcessor` on `postTransaction`; bank CRR status machine (UNKNOWN vs FAIL vs SUCCESS) — detail in `accounting.mdc`.

---

*When editing accounting: grep the `Request` in XML, list every `Processor` and nested `API`, then grep each bean for ExecutionContext keys.*

---

## 2026-04-14 CLB field propagation note

- `CLB` queue payload (`ChildLoanBookingEventsQueueDataPopulator`) forwards `loan_details` fields `vtc_id`, `sourcing_emp_id`, and `servicing_emp_id` into child `createOrUpdateLoanAccount` requests.
- Source precedence is member-first: values are read from each `member_details` item when present; fallback is parent-level execution context.
- Result: child loan creation path (`CreateLoanAccountProcessor`) persists `vtc_id` in `loan_account.filler_11` and employee ids on child rows with member-level correctness.

---

## 2026-04-14 incident response signature memory (CRR-focused)

- **Purpose:** quick differentiation between NEFT-v2 STP callbacks and MFT payloads seen in `client_request_response_log.response` during RCA.
- **NEFT-v2 STP response shape (expected for child NEFT legs):**
  - Top markers: `root.responseString`, `root.status.replyCode`, `root.status.externalReferenceNo`
  - Template family: `doGenericSyncSTPNEF` / NEFT-v2
- **MFT response shape (different API family):**
  - Top markers: `status.replyCode`, `status.externalReferenceNo`, `accountBalanceInfoDTO.*`
  - Template family: `miscFundTransfer`
- **RCA rule:** if CRR row `transaction_type` is NEFT leg but `response` shape is MFT (or external reference doesn’t match row correlators), treat as response-fidelity mismatch candidate and verify callback transport error path.
- **Retry-time expected CRR progression (child NEFT under `PARENT_SUCCESS`):**
  1. Existing `..._NEFT_NEF` row remains historical (`FAIL`/`UNKNOWN`/`SUCCESS` as persisted).
  2. On retry with `disbursement_status=NEFT_STAGE_1_PENDING`, system writes inquiry row: `transaction_type=NEFT_TRANSACTION_INQUIRY` (client ref usually same as prior NEF leg).
  3. If inquiry confirms stage-1 success, system initiates stage-2 and writes new `..._NEFT_NEI` row.
  4. Final CLMT/account status updates come from callback/post-processor paths after stage decision.

---

## ENTRY POINT REGISTRY [2026-04-17]

**Scope note (Wave 1):** HTTP `apiName` values are the `<Request name="…">` identifiers in tenant orchestration XML. Entry is **`ServiceGatewayController`** → **`RequestProcessorImpl`** → **`ServiceOrchestrator`** (platform-lib); accounting-v2 contributes processors + XML only. **No `@KafkaListener`** in accounting-v2 — consumers implement **`NovopayMessageBrokerConsumer`** (`computeRecords`). **No `@Scheduled`** in accounting-v2 `src/main/java`; schedules live in **novopay-platform-batch** (cron in batch job metadata / internal API with `function_sub_code=BATCH`). **Batch:** real `Job` wiring uses **`ParallelCommonBatchJob`** in `in.novopay.accounting.batchnew.*`; **`BatchJobPlaceholderConfig`** supplies `@Bean(name="…")` placeholders when the concrete config is absent.

| Type | Trigger | Class | Method | File | Already documented? |
|------|---------|-------|--------|------|---------------------|
| HTTP | `POST /api/{version}/{apiName}` | `ServiceGatewayController` | (Spring MVC handler) | `novopay-platform-lib/infra-service-gateway/.../ServiceGatewayController.java` | Yes (Runtime entry points) |
| HTTP | Orchestration dispatch | `RequestProcessorImpl` | `processRequest` (typical) | `novopay-platform-lib/infra-navigation/.../RequestProcessorImpl.java` | Yes |
| Kafka | Topic prefix `disburse_loan_api_` | `LmsMessageBrokerConsumer` | `computeRecords` → `processConsumerRecord` | `novopay-platform-accounting-v2/.../consumers/LmsMessageBrokerConsumer.java` | Yes |
| Kafka | Topic prefix `bulk_collection_data_failed_` | `BulkCollectionFailedRecordConsumer` | `computeRecords` | `novopay-platform-accounting-v2/.../BulkCollectionFailedRecordConsumer.java` | Yes (table + **GAP-036**) |
| Scheduled | *(none in accounting-v2)* | — | — | — | N/A |
| Batch | Scheduler → internal API / job name | Various `*BatchConfigService` + `ParallelCommonBatchJob` | `setUpJobAdvanceV2` (pattern) | `novopay-platform-accounting-v2/.../batchnew/**` | Partial (`system_brain/batch_jobs/batch_inventory.md`) |
| Batch | Placeholder beans | `BatchJobPlaceholderConfig` | `*Placeholder()` factory methods | `novopay-platform-accounting-v2/.../config/BatchJobPlaceholderConfig.java` | New (this registry) |

**Orchestration XML → HTTP `apiName`:** Every `<Request name="X">` is invokable as `apiName=X` when that XML is on the tenant orchestration classpath. **362** `<Request>` nodes across **9** files; **348** unique names. **14** names appear in **more than one** XML (always verify **which** XML the tenant uses — e.g. `disburseLoan` in `loans_orc.xml` vs `mfi_orc.xml`).

---

## ORCHESTRATION REQUEST INDEX [2026-04-17]

Total **362** requests, **348** unique `apiName`s. **14** `apiName`s appear in **two** orchestration files (typically **`ServiceOrchestrationXML.xml`** + **`mfi_orc.xml`**, or **`loans_orc.xml`** + **`mfi_orc.xml`** for shared loan APIs): `createOrUpdateGeneralLedger`, `createOrUpdateLoanAccount`, `createOrUpdateProductScheme`, `disburseLoan`, `getEffectiveInterestRateForProductScheme`, `getEntryLookupCodesOfTransaction`, `getGeneralLedgerDetails`, `getLoanAccountDetails`, `getLoanProductDetails`, `getLoanProductList`, `getProductSchemeDetails`, `getProductSchemeList`, `loanRepayment`, `updateGeneralLedgerStatus`.

### ServiceOrchestrationXML.xml (138 requests)

`createOrUpdateGeneralLedger`, `deleteGeneralLedger`, `updateGeneralLedgerStatus`, `getGeneralLedgerList`, `getGeneralLedgerDetails`, `createOrUpdateInternalAccountDefinition`, `deleteInternalAccountDefinition`, `getInternalAccountDefinitionList`, `getInternalAccountDefinitionDetails`, `createOrUpdateTaxComponent`, `getTaxComponentList`, `getTaxComponentDetails`, `deleteTaxComponent`, `createOrUpdateTaxGroup`, `getTaxGroupList`, `getTaxGroupDetails`, `deleteTaxGroup`, `createOrUpdateInternalAccount`, `deleteInternalAccount`, `getInternalAccountList`, `getInternalAccountDetails`, `createOrUpdatePriceMaster`, `getPriceMasterDetails`, `getPriceMasterList`, `deletePriceMaster`, `createOrUpdatePriceSetup`, `getPriceSetupDetails`, `getPriceSetupList`, `deletePriceSetup`, `createOrUpdateStampDutyMaster`, `getStampDutyMasterDetails`, `getStampDutyMasterList`, `deleteStampDutyMaster`, `createOrUpdateBaseInterestRate`, `deleteBaseInterestRate`, `getBaseInterestRateList`, `getBaseInterestRateDetails`, `createOrUpdateInterestSetup`, `getInterestSetupDetails`, `getInterestSetupList`, `deleteInterestSetup`, `getEffectiveInterestRateForInterestSetupCode`, `createOrUpdateAssetClassificationMaster`, `getAssetClassificationMasterList`, `getAssetClassificationMasterDetails`, `deleteAssetClassificationMaster`, `createOrUpdateAssetCriteriaMaster`, `getAssetCriteriaMasterDetails`, `getAssetCriteriaMasterList`, `deleteAssetCriteriaMaster`, `createOrUpdateLoanProduct`, `getLoanProductDetails`, `getLoanProductList`, `createOrUpdateProductScheme`, `getProductSchemeDetails`, `getProductSchemeList`, `getEffectiveInterestRateForProductScheme`, `getEntryLookupCodesOfTransaction`, `getCurrencyMasterList`, `getFinancialTransactionPlaceholderList`, `createOrUpdateSavingsProduct`, `getSavingsProductDetails`, `getSavingsProductList`, `getProductList`, `createOrUpdateSavingsAccount`, `getSavingsAccountDetails`, `getAccountDetails`, `getTransactionCategoryList`, `createOrUpdateWorkingDay`, `deleteWorkingDay`, `getWorkingDayList`, `getWorkingDayDetails`, `createOrUpdateHoliday`, `getHolidayDetails`, `getHolidayList`, `deleteHoliday`, `getTaskDataFromLMS`, `getServerClockDetails`, `generateUniqueReferenceNumber`, `createRepaymentMandateDetails`, `updateSIPresentationDetails`, `fetchFailedSIPresentationList`, `fetchMandateDetails`, `fetchMandateDetailsHistory`, `generateSIPresentationFiles`, `processingSIReverseFeedFiles`, `generateSILienPresentationFiles`, `generateFinnoneSILienPresentationFiles`, `processingSILienReverseFeedFiles`, `generateSIAutoHoldRemovalPresentationFiles`, `processingSIAutoHoldRemovalReverseFeedFiles`, `generateSIManualHoldMarkingPresentationFiles`, `processingSIManualHoldMarkingReverseFeedFiles`, `generateSIManualHoldRemovalPresentationFiles`, `processingSIManualHoldRemovalReverseFeedFiles`, `bulkFileToSGManualHoldRemovalJob`, `bulkSGToManualHoldRemovalJob`, `bulkSGToManualHoldMarkingJob`, `bulkFileToSGManualHoldMarkingJob`, `updateMandateDetailsTask`, `expirePendingMandatesBatchJob`, `viewBulkManualHoldRemovalFileStatus`, `viewBulkManualHoldMarkingFileStatus`, `downloadManualHoldRemovalUploadedFile`, `downloadManualHoldMarkingUploadedFile`, `getPresentationDetailsForLoanAccount`, `siFileDownloadBatchJob`, `siFileEnquiryBatchJob`, `siFileTransferBatchJob`, `generateEnachPresentationFile`, `processingEnachPresentationResponseFiles`, `generateEnachRepresentationFile`, `processingEnachRepresentationResponseFiles`, `viewBulkEnachRepresentationFileStatus`, `downloadEnachRepresentationUploadedFile`, `bulkSGToEnachRepresentationJob`, `bulkFileToSGEnachRepresentationJob`, `updateMandateStatus`, `bulkFileToSGRefundMarkingJob`, `bulkSGToRefundMarkingJob`, `proactiveExcessAmountRefundStaging`, `proactiveExcessAmountRefund`, `viewBulkRefundMarkingFileStatus`, `downloadRefundMarkingUploadedFile`, `generateOnDemandDocument`, `checkMandateStatusForUpdate`, `deleteAccountingTaskUsingCode`, `runInboundReverseExcessAmountRefundJob`, `bulkFileToSGAssetCriteriaGroupUpdateJob`, `bulkSGToAssetCriteriaGroupUpdateJob`, `viewBulkAssetCriteriaGroupUpdateFileStatus`, `downloadAssetCriteriaGroupUpdateUploadedFile`, `inboundReverseExcessAmountRefundJob`, `proactiveReverseTransaction`, `generateSIManualPresentationFiles`, `processingSIManualPresentationReverseFeedFiles`, `getWorkingDays`, `retrySIJob`

### group_mfi_orc.xml (19 requests)

`childLoanBooking`, `getChildLoanAccountList`, `childLoanRepayment`, `childWaiveLoanAccountCharges`, `childLoanRestructuring`, `childLoanReopening`, `childLoanForeclosure`, `individualChildLoanForeclosure`, `childLoanTransactionReversal`, `childLoanPartPrepayment`, `parentLoanAccountPartPrepayment`, `childLoanDisbursementCancellation`, `childLoanDisbursementCancellationParentRescheduling`, `childLoanAccountExcessAmountRefund`, `childLoanDisbursement`, `childLoanEventProcessingBatchJob`, `childLoanRebooking`, `childLoanRebookingAdjustmentTransaction`, `updateChildLoanDisbursementStatus`

### insurance_orc.xml (12 requests)

`createOrUpdateInsuranceProduct`, `deleteInsuranceProduct`, `createOrUpdatePremiumCalculationMatrixDetails`, `deletePremiumCalculationMatrixDetails`, `getInsuranceProductList`, `getInsuranceProductDetails`, `getPremiumCalculationMatrixList`, `getPremiumCalculationMatrixDetails`, `getInsurancePremiumAmount`, `getUniquePremiumCalculationCodeAndName`, `checkInsuranceProductGeoEligibility`, `getInsuranceDetailsForServicingEmployee`

### loans_insurance_orc.xml (26 requests)

`outboundDeathForeclosureInsuranceJob`, `inboundDeathForeclosureInsuranceJob`, `outboundDisbursementCancellationBajajErgoHealthInsuranceJob`, `outboundDisbursementCancellationHdfcLifeLifeInsuranceJob`, `outboundDisbursementCancellationHdfcErgoHealthInsuranceJob`, `inboundDisbursementCancellationHdfcErgoHealthInsuranceJob`, `inboundDisbursementCancellationBajajErgoHealthInsuranceJob`, `inboundDisbursementCancellationHdfcLifeLifeInsuranceJob`, `runInboundDisbursementCancellationHdfcErgoHealthInsuranceJob`, `runInboundDisbursementCancellationBajajErgoHealthInsuranceJob`, `runInboundDisbursementCancellationHdfcLifeLifeInsuranceJob`, `bulkSGToDisbursementCancellationJob`, `validateInsurance`, `runInboundDeathForeclosureInsuranceJob`, `deathForeclosureInsuranceJob`, `outboundDisbursementBajajErgoHealthInsuranceJob`, `outboundDisbursementHdfcLifeLifeInsuranceJob`, `outboundDisbursementHdfcErgoHealthInsuranceJob`, `inboundDisbursementHdfcErgoHealthInsuranceJob`, `inboundDisbursementBajajErgoHealthInsuranceJob`, `inboundDisbursementHdfcLifeLifeInsuranceJob`, `runInboundDisbursementHdfcErgoHealthInsuranceJob`, `runInboundDisbursementBajajErgoHealthInsuranceJob`, `runInboundDisbursementHdfcLifeLifeInsuranceJob`, `bulkSGToPostDisbursementInsuranceUpdateJob`, `getLoanAccountInsuranceList`

### loans_notification.xml (2 requests)

`loanInstallmentDueNotificationJob`, `loanInstallmentBounceNotificationJob`

### loans_orc.xml (82 requests)

`createOrUpdateLoanAccount`, `updateLoanAccountPreDisbursementDetails`, `getLoanAccountDetails`, `getBulkLoanAccountDetails`, `generateRepaymentSchedule`, `getLoanMaturityDateAndNumberOfInstallments`, `getLoanUpfrontInterestAmount`, `disburseLoan`, `interestAccrualCalculation`, `interestAccrualPosting`, `loanRepayment`, `loanWriteoff`, `loanPrepayment`, `getLoanForeclosureDetails`, `cancelLoanForeclosure`, `getLoanAccountList`, `getLoanAccountOverviewDetails`, `getLoanAccountBasicDetails`, `getLoanAccountSummaryDetails`, `getLoanAccountRepaymentScheduleDetails`, `loanProvisioningPosting`, `loanAccountDpdCalcJob`, `loanAccountAssetCriteriaJob`, `loanAccountAssetClassificationJob`, `penalInterestAccrualCalculation`, `penalInterestAccrualBooking`, `loanAccountClosure`, `getLoanAccountDisbursmentTransactions`, `loanAdvanceRepayment`, `registerLoanAccountRescheduleEvent`, `rescheduleLoanAccountRescheduleBatch`, `fetchPartPrepaymentRepaymentSchedule`, `getLoanAccountPartPrepaymentDetails`, `loanAccountPartPrepayment`, `loanAccountBillingJob`, `loanRecurringPaymentBatchApi`, `getPartPrepaymentBPIAmount`, `waiveLoanAccountCharges`, `fetchLoanForeclosureSimulationDetails`, `updateCollectionBatchDetails`, `loanAccountReopening`, `loanAccountTransactionReversal`, `fetchDisbursementCancellationSimulationDetails`, `loanDisbursementCancellation`, `getDisbursementCancellationDetails`, `loanAccountExcessAmountRefund`, `getLoanAccountExcessAmountRefundDetails`, `getLoanAccountExcessAmountRefundList`, `getLoanAccountCASADetails`, `validateCustomerAccountDetails`, `fetchLoanAccountChargeDetails`, `getManualJournalEntryList`, `getLoanAccountDpdCount`, `getManualJournalEntryDetails`, `loanDeathForeclosure`, `getDeathForeclosureDetails`, `loanAccountRebooking`, `individualLoanAccountRebooking`, `groupLoanAccountRebooking`, `getLoanAccountRebookingDetails`, `loanAccountRestructuring`, `fetchRestructuringRepaymentSchedule`, `getLoanAccountRestructuringList`, `getLoanAccountRestructuringDetails`, `getLoanAccountBPIAmount`, `getCustomerAccountList`, `validateLoanAccountTransaction`, `calculateStampDutyCharges`, `bulkFileToSGTransactionReversalJob`, `viewBulkTransactionReversalFileStatus`, `downloadTransactionReversalUploadedFile`, `bulkSGToTransactionReversalJob`, `loanAccountServicingDocumentEventsJob`, `getActiveLoansForCustomer`, `getLoanAccountGenericDetails`, `getLoanAccountReopeningDetails`, `getCasaBalanceDetails`, `calculateAnnualPercentageRate`, `generatePreEMIRepaymentSchedule`, `getCustomerLoanAccountBounces`, `validateLMSRestrictedActivitiesForPTrfr`, `getVillageAccountingPortFolioSummary`

### mfi_orc.xml (59 requests)

`disburseLoan`, `createOrUpdateProductScheme`, `getLoanProductDetails`, `getProductSchemeDetails`, `getProductSchemeList`, `getEffectiveInterestRateForProductScheme`, `getEntryLookupCodesOfTransaction`, `createOrUpdateGeneralLedger`, `getGeneralLedgerDetails`, `updateGeneralLedgerStatus`, `createOrUpdateLoanAccount`, `getLoanAccountDetails`, `getLoanProductList`, `runBODJobs`, `runEODJobs`, `trialBalanceCalculation`, `generatePostEODReports`, `trialBalanceZeroisationJob`, `generateTBZeroisationReport`, `getLoanAccountApplicableCharges`, `getLoanAccountAppliedCharges`, `bulkFileToSGForeclosureChargeUpdateJob`, `bulkSGToForeclosureChargeUpdateJob`, `viewBulkForeclosureChargeUpdateFileStatus`, `downloadForeclosureChargeUpdateUploadedFile`, `getForeclosureChargeDetails`, `fetchLoanAccountsForCustomer`, `bulkFileToSGManualJournalEntriesJob`, `bulkSGToManualJournalEntriesJob`, `viewBulkManualJournalEntriesFileStatus`, `downloadManualJournalEntriesUploadedFile`, `updateDisbursementAccountDetails`, `bulkFileToSGNocBlockUnblockJob`, `bulkSGToNocBlockUnblockJob`, `viewBulkNocBlockUnblockFileStatus`, `downloadNocBlockUnblockUploadedFile`, `bulkFileToSGDispatchDetailsJob`, `bulkSGToDispatchDetailsJob`, `viewBulkDispatchDetailsFileStatus`, `downloadDispatchDetailsUploadedFile`, `generateNocFileJob`, `getLoanAccountNocDetails`, `bulkFileToSGSecNpaReverseFeedFileJob`, `runSecNpaBulkUploadJob`, `bulkSGToSecNpaReverseFeedFileJob`, `bulkOutboundSecNpaReverseFeedFileJob`, `updateLoanAccountDerivedFieldsJob`, `updateLoanAccountDerivedFieldsMonthlyJob`, `extractCasaBalanceFor180ProductCode`, `extractCasaBalanceFor182ProductCode`, `viewBulkFinsallRepaymentFileStatus`, `downloadFinsallRepaymentUploadedFile`, `bulkFileToSGFinsallRepaymentJob`, `bulkSGToFinsallRepaymentJob`, `accountingBankServiceRetryJob`, `doGenericSyncSTPBankNEFNeftCallBack`, `doGenericSyncSTPBankNEINeftCallBack`, `loanRepayment`, `loanRepaymentInquiry`

### product_transaction_accounting_definition_orc.xml (12 requests)

`createOrUpdateTransactionCatalogue`, `getTransactionCatalogueList`, `deleteTransactionCatalogue`, `createOrUpdatePlaceholderMasterListForProductType`, `deletePlaceholderMasterListForProductType`, `createOrUpdatePlaceholderMaster`, `getPlaceholderMasterList`, `getPlaceholderMasterDetails`, `deletePlaceholderMaster`, `createOrUpdateAccountingRules`, `getAccountingRuleList`, `deleteAccountingRule`

### product_transaction_orc.xml (12 requests)

`postTransaction`, `getAccountBalances`, `getAccountStatement`, `getTransactionPartitionDetails`, `reverseTransaction`, `getCurrencyMasterDetails`, `getLoanAccountStatement`, `postManualJournalEntry`, `reverseManualJournalEntry`, `glBalanceZeroisation`, `executeLMSPortfolioTransfer`, `doGLTransfer`

---

## COMPLETE FLOW REGISTRY [2026-04-17]

**Wave 1 methodology:** A full per-processor matrix (every `get`/`put`, DB, HTTP, Kafka, Redis) for all **362** requests requires automated extraction or dedicated tranches; this registry adds **verified deep detail** where gaps were found and **pointers** for the rest. **`postTransaction`** chain is already captured above (XML snippet). **`DefaultExecutionContext.get`** resolves **`localMap` first**, then **`sharedMap`** (`novopay-platform-lib/.../DefaultExecutionContext.java`), so orchestration `scope="local"` `IParam` values are visible to `getValue` if `putLocal` was used for that key.

### FLOW: `loanWriteoff` (posting branch — `post_transaction=true`)

**Entry:** HTTP `apiName=loanWriteoff` → `loans_orc.xml`  
**Trigger:** HTTP  
**Orchestration XML:** `novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml` (`<Request name="loanWriteoff">`, ~L1382)

**Processor chain (subset — branch where ledger posts):**

1. **`validateLoanWriteOffDataProcessor`** — `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/writeoff/processor/ValidateLoanWriteOffDataProcessor.java`  
   - **EC reads:** `value_date`, `account_number`, `writeoff_amount`, `loan_account_id` (after set)  
   - **EC writes:** `loan_account_entity`, `product_id`, `loan_account_id`, `principal_amount`, `interest_amount`, `penalty_amount`, `field_name` (on errors)  
   - **DB:** `loan_account` — SELECT by account number; `loan_due_details` — aggregates (principal outstanding, interest due, penal due via DAO)  
   - **External / Kafka / Redis:** none  
   - **Exception:** `NovopayFatalException` (rethrow) on date/account/status/amount validation  

2. **`populateUserDetails`** — (standard user context; not expanded here)  

3. **Maker/checker controls** — `getMakerCheckerEnabledForUseCaseProcessor` / `dummyProcessor` set `post_transaction`, `responseCode`, etc.  

4. **`prepaymentApproppriationProcessor`** — `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/prepayment/processor/PrepaymentApproppriationProcessor.java`  
   - **EC reads:** `total_foreclosure_amount` (String), `principal_amount`, `interest_amount`, **`penal_amount`**, **`fee_amount`**, **`foreclosure_date`** (millis String), `loan_account_entity`  
   - **EC writes:** `principal_amount`, `interest_amount`, `penalty_amount`, `fee_amount`, `excess_amount`, `loan_due_details_list`, `product_id`  
   - **DB:** `loan_due_details` (via `LoanDueDetailsSuperListUtil.getDueDetails`); `loan_product` / asset criteria slab lookups  
   - **Exception:** propagates fatal/non-fatal from framework  
   - **Contract mismatch vs `loanWriteoff` XML (see GAP-062):** orchestration passes **`prepayment_amount`** (local) = `${writeoff_amount}`, not `total_foreclosure_amount`. Validator sets **`penalty_amount`** but processor reads **`penal_amount`**. Request uses **`value_date`**, not **`foreclosure_date`**. **`fee_amount`** is not populated by the validator before this processor.

5. **`populateAdditionalAmountDetailsProcessor`** (×4) — PRIN/INT/FEE/PENALTY lines from `${principal_amount}` etc.  

6. **`populateTransactionAccountDetailsProcessor`** — loan account placeholder for posting.  

7. **`<API name="postTransaction">`** — nested ledger (`transaction_type=LOAN_WRITE_OFF`, `transaction_sub_type=FINAL_WRITE_OFF`).  

8. **`updateLoanWriteOffStatusProcessor`**, **`updateLoanDueDetailsProcessor`**, **`updateLoanInstallmentDetailsProcessor`**, **`getLoanRepaymentModeDetailsProcessor`**, **`createLoanAccountPaymentsDetailsProcessor`**, **`deleteDraftProcessor`**

**Final output:** HTTP orchestration response (maker/checker codes path-dependent) + `postTransaction` OParams when REAL posting runs.  
**Error path:** Validator or posting failure → fatal → txn rollback per orchestration.  
**Idempotency:** `client_reference_number` = `${stan}` on nested `postTransaction` (dedupe in REAL mode).  
**Known gaps:** **GAP-062** (write-off vs `PrepaymentApproppriationProcessor` EC keys).

---

## DB Operation Registry — Accounting [2026-04-17]

**Inventory (Wave 1):**

| Metric | Count | Notes |
|--------|------:|-------|
| `*Entity.java` | 166 | JPA entities (`src/main/java`) |
| `*Repository.java` | 178 | Spring Data |
| `*DAOService.java` | 142 | Service layer over repos / native SQL |

**Concurrent / N+1 / index posture:** Full row-level “method → SQL → index” mapping is **not** duplicated here for every DAO (hundreds of methods). Use **`mfi_accounting_structure.sql`** for PK/unique/index truth; grep hot paths for `for (` + `DAO` calls for N+1; financial updates should be reviewed for optimistic version columns / `SELECT FOR UPDATE` where the schema allows — **not** asserted service-wide in Wave 1.

| Entity (representative) | Table | Method (representative) | Operation | Concurrent risk | Index | N+1 risk |
|-------------------------|-------|-------------------------|-----------|-----------------|-------|----------|
| `LoanAccountEntity` | `loan_account` | `LoanAccountDAOService.findOneByAccountNumber` | SELECT | Reader skew unless txn isolation documented | PK / `external_ref_number` indexed in schema | Low for single-key fetch |
| `LoanDueDetailsEntity` | `loan_due_details` | `LoanDueDetailsDAOService.getPrincipalOutStandingAmount` (and list loaders) | SELECT / aggregate | Multiple writers on servicing paths | Per schema | **Medium** if loaded in loops without batch fetch |
| `ValidateLoanWriteOffDataProcessor` path | `loan_due_details` | `getPenalDueAmountByDueDate`, `getInterestDueAmountByDueDate` | SELECT aggregate | Same | Per schema | Low (fixed calls per request) |
| `BulkCollectionFailedRecordConsumer` | `bulk_collection_*` (via `bulkCollectionLogDaoService`) | `save` per record | INSERT | **GAP-036** (no dedupe) | Verify unique keys | **High** — loop over Kafka batch without per-record error isolation |

**Action:** Extend this table incrementally when touching a flow (Wave 2+ contract pass).

---

## LOS ↔ Accounting Complete Contract [2026-04-17]

**Scope honesty:** This pass is **grep- and file-evidence-based** across `novopay-mfi-los` and accounting touchpoints — not a human line-by-line read of every LOS source file. Orchestration **inside** accounting `disburseLoan` after the consumer hands off to `ServiceOrchestrator` follows `loans_orc.xml` / Wave 1; this section focuses on **transport, EC/Kafka shape, and LOS-side behaviour**.

### MAP 1 — LOS → Accounting (HTTP via `NovopayInternalAPIClient`)

**Central hub:** `AccountingUtil` plus `LoanAccountStatusEnquiryAPIUtil`, `CommonUtil`, and disbursement-related processors.

| apiName (evidence) | Primary LOS surface | Payload source | Null / error handling (LOS) | If accounting slow/down |
|--------------------|---------------------|----------------|------------------------------|-------------------------|
| `getLoanProductDetails` | `AccountingUtil` | EC + `function_code` / `function_sub_code` | Fatal → `ERROR_WHILE_CALLING_ACCOUNTING` | `NovopayFatalException`; no client retry |
| `getLoanProductList` / `GET_LOAN_PRODUCT_LIST` | `AccountingUtil.getAvailableLoanProducts` | `search_criteria`, paging | Same | Same |
| `getLoanAccountOverviewDetails` | `AccountingUtil` | `account_number_list` | Same | Same |
| `getLoanAccountList` | `AccountingUtil` | EC | Same | Same |
| `getInsurancePremiumAmount` | `AccountingUtil` | function codes | Maps error codes → LOS-0401 / generic | Same |
| `generateRepaymentSchedule` | `AccountingUtil` | EC | Fatal with upstream code | Same |
| `checkInsuranceProductGeoEligibility` | `AccountingUtil` | DEFAULT/DEFAULT | Fatal | Same |
| `calculateStampDutyCharges` | `AccountingUtil` | amount, product, state from office | Fatal | Same |
| `fetchLoanAccountChargeDetails` | `AccountingUtil.getProcessingFee` | amount, product, office, event date | Fatal | Same |
| `getBulkLoanAccountDetails` | `AccountingUtil` | `account_number_list` | Fatal | Same |
| `getChildLoanAccountList` | `AccountingUtil` | `account_number`, paging | Fatal | Same |
| `updateChildLoanDisbursementStatus` | `AccountingUtil` | `external_ref_number`=group, `entity_type`=GROUP, child list | Fatal | Same |
| `updateLoanAccountPreDisbursementDetails` | `AccountingUtil` + direct call in `callUpdateLoanAccountPreDisbursementDetailsApi` | `external_ref_number`, `entity_type`, mode/status | Fatal | Same |
| `getEffectiveInterestRateForInterestSetupCode` | `AccountingUtil` | function codes | Fatal | Same |
| `getWorkingDays` | `AccountingUtil` | DEFAULT | Rethrow | Same |
| `getHolidayList` | `AccountingUtil` | paging/sort | Logs; may return null map | Same |
| `getLoanAccountDetails` | `LoanAccountStatusEnquiryAPIUtil` | merged EC + headers; **`function_sub_code`** from caller (e.g. ENQUIRY) | **N** on thrown fatal — catch logs only; **`apiResponse` may be null** | Callers must tolerate null map |
| `getLoanAccountDerivedData` | `CommonUtil` | EC copy | Fatal | Same |
| `getCustomerLoanAccountBounces` | `CommonUtil` | EC | Fatal | Same |
| `disburseLoanAudit` | `CommonUtil` | EC | Via internal API | Same |

**Count (distinct HTTP apiName to accounting):** **20** (see `AccountingUtil.java` call sites + `LoanAccountStatusEnquiryAPIUtil` + `CommonUtil` accounting calls above).

### MAP 2 — Accounting → LOS (HTTP)

**Code-verified:** No `NovopayInternalAPIClient.callInternalAPI` usage was found in `novopay-platform-accounting-v2` whose `apiName` targets the LOS module (accounting outbound calls are actor, masterdata, task, payments patterns, nested `postTransaction`, etc.). **Cross-boundary return path to LOS is Kafka-first** for disburse outcomes and loan closure (see MAP 4 and closure topic in `event-registry.md`).

### MAP 3 — LOS → Accounting (Kafka)

| Topic prefix | Producer | Message shape | `entity_type` in payload? |
|--------------|----------|---------------|---------------------------|
| `disburse_loan_api_` | `LosMessageKafkaProducer` via `DisburseLoanAPIUtil.callDisburseLoanAPI` | **`disburseLoan|{json}|{cacheKey}`** where JSON = JTF merge of **shared + local** `ExecutionContext` for apiName `disburseLoan` | **Y** — `PrepareDisburseLoanAPIRequestService` sets `external_ref_number` and **`entity_type`** on the context before formatting (`PrepareDisburseLoanAPIRequestService.java` L148-L149). |

**Redis (LOS producer):** `novopayCacheClient.set(tenant, cacheKey, "in_progress", ACCOUNTING db)` — **no TTL** (`DisburseLoanAPIUtil.java` L72-L83). Duplicate request: if key already present → skip Kafka (**`DISBURSEMENT_REQUEST_IN_REDIS_CACHE`**).

**If accounting / broker down:** Exception path removes key (`DisburseLoanAPIUtil.java` L86-L94); caller sees FAILED.

### MAP 4 — Accounting → LOS (Kafka): `los_lms_disbursement_sync`

| Producer field | Evidence | LOS consumer read | Notes |
|----------------|----------|-------------------|-------|
| `external_ref_number` | `LmsMessageBrokerConsumer.sendResultMessageToKafka` L193 | `DisbursementSyncService` L27 | Required non-blank |
| `status` | L194–195 (`SUCCESS` / `FAILED`) | L39–42 | **If `SUCCESS` → early return (no DB update)** — sync is for **failure signalling** |
| `error_code` | L202 (failed only) | `MFIConstants.CODE_ERROR` L61 | Matches key **`error_code`** |
| `error_message` | L203 | `ERROR_MESSAGE` L62 | Matches |
| `tenant_code` | L206 | (implicit tenant on consumer) | |
| `timestamp` | L207 | not used in service | |
| **`entity_type`** | **Not set** | **Required** L33–37 | **MISMATCH** — summary table + `event-registry.md` |

**LOS consumer:** `DisbursementSyncConsumer` deserializes JSON to map → `putAll` on `ExecutionContext` (`DisbursementSyncConsumer.java` L39-L43). Parse errors: logged, **no rethrow** (L46-L48). **`CannotAcquireLockException`:** rethrown for retry (L44-L45).

**Malformed message:** Missing `entity_type` / `external_ref_number` → **silent skip** (log + return). **LOS down when accounting publishes:** Kafka consumer lag / replay — no LOS-specific outbox; rely on broker retention and consumer recovery.

**Accounting producer Redis:** Consumer sets **`dl{cacheKey}`** without TTL (`LmsMessageBrokerConsumer.java` L110-L122) — see gaps table.

### MAP 5 — Disbursement distributed transaction (end-to-end spine)

| Step | Class.method | Data persisted | Inconsistency if step fails | Recovery | Redis key (TTL?) |
|------|--------------|----------------|----------------------------|----------|------------------|
| 1 | LOS gateway → orchestration → `DisburseLoanProcessor.process` | `disburse_loan_process` status IN_PROGRESS, retry | LOS shows in-flight vs reality | Scheduler retry | — |
| 2 | `PrepareDisburseLoanAPIRequestService.prepareDisburseLoanRequest` | (prepare EC only) | — | — | — |
| 3 | `DisburseLoanAPIUtil.callDisburseLoanAPI` | Redis **`disburseLoan{productId}_{externalRef}`** = `in_progress` | Stale skip if crash after set | Manual key delete / ops | **N** |
| 4 | `LosMessageKafkaProducer.pushDataToKafkaQueue` | Kafka log | Message lost if **GAP-019** | Replay from LOS / ops | — |
| 5 | `LmsMessageBrokerConsumer.processConsumerRecord` | Redis **`dl`+cacheKey**; orchestration runs `disburseLoan` | Partial accounting state | Kafka retry; skip rules | **N** |
| 6 | Accounting `disburseLoan` processors | `loan_account`, CRR logs, events, bank legs (NEFT/MFT) | Money vs book | Bank inquiry / ops | (various) |
| 7 | `sendResultMessageToKafka` | `los_lms_disbursement_sync` message | LOS never learns outcome | Consumer replay | — |
| 8 | `DisbursementSyncService.handleDisbursementSyncRecord` | `disburse_loan_process` failure_reason | **Skipped if `entity_type` missing** | Fix producer contract | — |

**Fully traced (this pass):** **Y** for **transport + LOS/consumer contract + Redis/Kafka spine**; **internal** accounting `disburseLoan` processor chain remains **`loans_orc.xml` + Wave 1**.

### Contract score (LOS ↔ Accounting)

| Metric | Value |
|--------|------:|
| HTTP contracts inventoried (LOS → accounting) | 20 |
| HTTP contracts (accounting → LOS) | 0 |
| Kafka contracts | 3 (`disburse_loan_api_` in, `los_lms_disbursement_sync` + `los_lms_data_sync_` out) |
| Mismatches | **1** (`entity_type` on disburse sync) |
| Drifts (platform) | HTTP no retry / 120s default; producer swallow **GAP-019** |

---

## Payments ↔ Accounting Complete Contract [2026-04-17]

**Scope honesty:** Evidence from `MfiCollectionsDAOService`, bulk collection consumers, `SGToNpHandoffIWriter`, and accounting batch writer for `bulk_collection_data_`. Not every payments Java file was read cover-to-cover.

### MAP 1 — Collection flow (payments → accounting LMS)

**Representative path:** collections persisted in payments DB → partner sync → internal API **`collectionLoanRepayment`** (and related) with **configurable retries** (`lms.payments.sync.*`) → on success, `PartnerSyncStatus` **SYNCED** / **PARTIAL_SYNCED** on reference rows + collection entity; on exhaustion, **SYNC_FAILED** + `CollectionExternalSystemUpdateStatusEntity` for retrigger (`MfiCollectionsDAOService.java` L1019-L1097).

**If accounting step fails:** Payment/collection rows **are not automatically reversed** by this snippet — they remain with **SYNC_FAILED** / partner sync flags for **batch re-push** (`PushPendingLMSUpdatesItemWriter`, `PushLMSUpdateProcessor`). **Not silent:** logs + retrigger entity.

### MAP 2 — `bulk_collection_data_` (Accounting → Payments)

| Layer | Evidence |
|-------|----------|
| **Producer** | `LoanRecurringPaymentItemWriter` builds JSON: `timestamp`, `client_code`, **`collection_list`** (array of collection objects) (`LoanRecurringPaymentItemWriter.java` L190-L203). |
| **Consumer** | `CreateOrUpdateBulkCollectionConsumer.computeRecords` parses envelope; iterates `collection_list` (`CreateOrUpdateBulkCollectionConsumer.java` L81-94). |
| **Per-item shape** | Each element expects **`col_ext_ref_id`**, nested **`due_details`**, **`customer`**, **`group_detail`** — applied in `BulkCollectionExtractor.createCollectionEntity` / `updateCollectionEntity`. |
| **Unmatched / failures** | Failed creates/updates go to `failedRecords` → `CollectionCreationStageDetailsEntity` via `saveRecordForFailedRecords` (L224-L237). **Parse failure:** `parseData` returns null → main block skipped (**silent no-op** for that message) — **GAP-044**. **`collection_list` null → NPE risk** at log line — **GAP-064**. |

### MAP 3 — NEFT (payments involvement)

**Code-verified:** **No** `NEFT` / `neft` string matches under `novopay-platform-payments/src` (Java). **NEFT disburse legs live in accounting** (`CallBankAPIForDisbursementProcessor`, child NEFT processors, etc.). **Payments touchpoint:** only via **repayment / collection** APIs above, not NEFT file exchange.

### MAP 4 — Failure / reconciliation posture

| Scenario | Behaviour | Reconciliation |
|----------|-----------|----------------|
| Payments DB updated; `collectionLoanRepayment` fails after retries | `PartnerSyncStatus.SYNC_FAILED`, retrigger row | `PushPendingLMSUpdatesItemWriter` / manual retry |
| Bulk Kafka message invalid | Often **no DLQ** from consumer parse path | **GAP-044** / **GAP-064** |
| Accounting posting ahead of payments | Not fully modeled here | Ops / partner sync reports |

### Contract score (Payments ↔ Accounting)

| Metric | Value |
|--------|------:|
| HTTP apiNames (payments → accounting LMS) | **6** (`collectionLoanRepayment`, `loanPrepayment`, `loanAccountPartPrepayment`, `loanDisbursementCancellation`, `updateCollectionBatchDetails`, plus `loanRepayment` from `SGToNpHandoffIWriter`) |
| Kafka (`bulk_collection_data_`) | **1** producer (accounting batch) / **1** consumer (payments) |
| Mismatches | **0** new beyond known consumer robustness gaps |
| Drifts | Shared HTTP client resilience; **GAP-019** on any Kafka confirm |

---

## Batch → Accounting Complete Contract [2026-04-17]

**Critical architecture note:** `novopay-platform-batch` (**99** Java files) is the **scheduler / orchestration shell** — it does **not** host Spring Batch `ItemReader`/`ItemWriter` for LMS ledger jobs. It triggers work via **`NovopayInternalAPIClient.callInternalAPI(executionContext, jobName, version, jobName, …)`** (`SchedulerCommonService.callJobAPi` L276-L286, `DirectJobExecutor`). **`job_time`** is set from **`PlatformDateUtil.getBusinessDateInLong()`** after **invalidating** masterdata cache key `current.business.date` (`SchedulerCommonService.setJobTime` L291-L297).

**Accounting batch implementations** live under **`novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/`** (and related packages). **Inventory:** **71** `*BatchConfigService.java` files (glob count). Detailed money-path inventory: `system_brain/batch_jobs/batch_inventory.md`.

**Distributed lock (batch platform):** **N** (no leader election / Redis lock on schedule tick) — see `.cursor/multinode-batch.md` + gaps table **multi-node batch scheduler**.

### Representative template — how to read any LMS batch job

| Dimension | Typical pattern (accounting-v2) |
|-----------|----------------------------------|
| **Entry** | `*BatchConfigService` wires Spring Batch job + steps; remote start = HTTP internal API with same name as `jobName` from batch DB. |
| **Trigger** | **Scheduled** via batch service cron (`batch_schedule.cron_expression`) → `callJobAPi`; **manual** replay via same API with `op_code=RESTART` paths (`SchedulerCommonService.reTryForFailed`). |
| **Accounting HTTP from batch module** | **N** — batch only **invokes** accounting job endpoint; accounting job may call nested `postTransaction` / `loanRepayment` internally. |
| **Kafka** | Some writers publish (e.g. `bulk_collection_data_`); consumers are in accounting/payments, not in `novopay-platform-batch`. |

### BATCH JOB: `interestAccrualPosting` (interest accrual **booking** / ledger post)

| Field | Value |
|-------|--------|
| **Entry class** | `InterestAccrualBookingBatchConfigService` — `novopay-platform-accounting-v2/.../interestaccrualbooking/InterestAccrualBookingBatchConfigService.java` |
| **Trigger** | Scheduled (group **LMS-EOD-BOD**, cron `0 0 18 * * ?` per `batch_inventory.md`) |
| **Service invoked** | `InterestAccrualBookingBatchService` → internal **`postTransaction`** |
| **Accounting tables** | Reads **`loan_account`**, **`interest_accrual_details`**, due/installment joins (reader SQL); writer updates accrual posted amounts / posting dates |
| **`client_reference_number`** | **Time-based:** `accountId + "" + new Date().getTime()` (`InterestAccrualBookingBatchService.java` L251, L280) |
| **Idempotency** | In-service guards: skip when accrued == posted; date/eligibility checks (`batch_inventory.md`); **dedupe processor** can be bypassed on replay because **new** client ref each attempt |
| **Re-run same period** | **UNSAFE** for duplicate **ledger** if partial failure + retry — **existing gap row** (time-based CRR) |
| **ItemReader/Processor/Writer** | Pattern: JDBC cursor / processor / writer in `batchnew/interest/interestaccrualbooking/` — chunk/grid from `BatchConfig` + job params |
| **Distributed lock** | **N** at accounting job level; relies on single scheduler + Spring Batch instance semantics |

### BATCH JOB: `loanAccountClosure` (auto-closure)

| Field | Value |
|-------|--------|
| **Entry class** | `LoanAccountAutoClosureBatchConfigService` |
| **ItemReader** | `LoanAccountAutoClosureItemReader` — native SQL: `loan_account` **`loan_status = 'ACTIVE'`** + `batch_failure_audit` window + account_id partition (`LoanAccountAutoClosureItemReader.java` L25-L35) |
| **ItemWriter** | `LoanAccountAutoClosureItemWriter` — sets `CLOSED`, saves `loan_account`, pushes **`PushLoanAccountClosureDetailsProcessor`** (Kafka LOS sync) |
| **Double closure?** | **Prevented under normal replay:** once `loan_status` is **CLOSED**, reader **excludes** the row (**ACTIVE** filter). |
| **Residual risk** | Writer **`catch` logs only** (L114-L118) → partial chunk / inconsistent closure — **existing High** table row. **Not** “no guard against double close” — guard is **reader status**. |
| **Concurrent execution risk** | **Y** if duplicate job instances (multi-node scheduler gap) — two runs could race on same `ACTIVE` row before first commit |
| **Re-run safety** | **MOSTLY SAFE** for duplicate *closure* row selection; **UNSAFE** for operational correctness if writer swallows errors |

### Batch → Accounting scorecard

| Metric | Value |
|--------|------:|
| **Accounting `BatchConfigService` entry points** | **71** |
| **Batch platform Java files** | **99** (scheduler only) |
| **Jobs called out as high idempotency risk (time-based CRR / swallow)** | See gaps: interest accrual posting, billing batch, asset criteria `postTransaction`, death-foreclosure insurance writer, proactive excess refund, auto-closure writer |
| **Penal accrual booking** | **Strong** reader guard (`accrual_posting_date is null`) — reruns skip booked rows |

**Honesty:** This wave did **not** line-by-line audit all **71** configs; deep evidence is on **interest accrual posting**, **loan auto-closure**, and **`system_brain/batch_jobs/batch_inventory.md`** spine.

---

## Wave 1 read coverage (honesty)

- **Orchestration:** all **9** XML files under `deploy/application/orchestration/` enumerated; **362** `<Request>` nodes indexed.  
- **Java:** **2046** files under `src/main/java`; Wave 1 did **not** perform a human line-by-line read of every file — evidence-based deep reads targeted **entry consumers**, **ExecutionContext resolution**, **`loanWriteoff`** / **`PrepaymentApproppriationProcessor`** / **`ValidateLoanWriteOffDataProcessor`**, and **batch placeholder inventory**. Further waves should automate EC/DB extraction for remaining requests.

---

## Flow Completeness Verified [2026-04-17]

**Method:** Flow Sync Wave 6 — six-point observability/correctness checklist vs `.cursor/knowledge-graph.md` money paths (structured entry/exit+correlation, DB durability, completion event, explicit failure path, monitoring). **GAP-069** captures platform-wide partials.

| Money path (knowledge graph) | Status | Notes |
|------------------------------|--------|--------|
| Loan disbursement | **GAP-AFFECTED** | `entity_type` sync mismatch (summary rows); Redis TTL; GAP-066 correlation on sync topic; pipe contract GAP-067 |
| Loan repayment | **PARTIAL** | HTTP/batch entry; dedupe reliance on CRR; collections sync recon |
| Interest accrual (EOD posting) | **GAP-AFFECTED** | Time-based `client_reference_number` (High); batch multi-node |
| Loan closure | **GAP-AFFECTED** | Auto-closure writer swallow (High); Kafka producer visibility (GAP-019) |
| Bulk collection (Kafka) | **GAP-AFFECTED** | GAP-019 producer; GAP-064 consumer null list |
| Reversal / manual JE | **PARTIAL** | Gateway HTTP; **no** `src/test` coverage (GAP-059) |

**None** marked **COMPLETE** at platform observability bar — all are **PARTIAL** or **GAP-AFFECTED** pending closure of listed gaps.

---

## Disbursement 100% Audit Snapshot [2026-04-22]

This section is the latest evidence-backed disbursement audit checkpoint across accounting + LOS sync contracts.

### Canonical lane map (accounting ORC + processors)

| Lane | Trigger (`function_sub_code`) | Bank rail | Primary status progression |
|------|-------------------------------|-----------|----------------------------|
| Fresh disburse | `DEFAULT` | MFT / NEFT (v1 flag on) | `LAN_CREATED -> LOAN_BOOKED -> DTFC_SUCCESS -> (PARENT_SUCCESS for child path) -> COMPLETED` |
| Stage replay | `LAN_CREATED`, `LOAN_BOOKED`, `DTFC_SUCCESS`, `PARENT_SUCCESS` | stage-specific | Re-enters lane based on stored `loan_account.disbursement_status` + CRR inquiry guards |
| Reinit | `REINITIATE_BANK` | NEFT-focused | CRR `_REINIT` typing + deterministic external ref continuity |
| Callback settle | `ST_NEF`, `ST_NEI` callback APIs | NEFT callbacks | Stage transition or failure regression handling (parent/child variants) |

### Idempotency / replay guards confirmed in code

- LOS producer Redis in-flight guard (`disburseLoan{product}_{external}`) in `DisburseLoanAPIUtil`.
- Accounting consumer Redis lock guard (`dl+cacheKey`) + skip gate on `ACTIVE+COMPLETED` and `LOCK` in `LmsMessageBrokerConsumer`.
- Deterministic external reference continuation through CRR in `ExternalReferenceNoUtil` (including `_REINIT` lookup sets).
- Stage inquiry guards in parent/child disbursement processors before re-firing bank transactions.

### High-impact open issues from this audit

1. `los_lms_disbursement_sync` payload still misses `entity_type`, while LOS consumer requires it (`DisbursementSyncService`) -> sync no-op risk.
2. Same payload still omits `stan` correlation -> weaker RCA/replay traceability.
3. Accounting consumer skip branches (`LOCK`, `LOCK_CACHE_IN_PROGRESS`) do not publish LOS sync result.
4. Consumer payload parsing occurs before guarded `try/finally`; malformed pipe payload can fail before normal send/cleanup flow.
5. NEFT callback array branch UTR map key uses `referenceno` instead of `paymentrefno`, causing potential UTR drop on lookup.

Cross-links: `.cursor/gaps-and-risks.md` GAP-070..073, `.cursor/event-registry.md` (`los_lms_disbursement_sync`), `system_brain/flows/disbursement.md`.
