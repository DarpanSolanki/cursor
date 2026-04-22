# Test coverage map (rebuilt)

**Workspace:** sliProd. **Date:** 2026-04-10. **Method:** `**/src/test/**/*.java` grep for class/API names; static workspace only.

**Legend:** COVERED | PARTIAL | NOT COVERED

## 1) Money-path flows (cross-service)

| Flow | Status | Evidence / gap pointer |

|------|--------|-------------------------|

| Disbursement HTTP + Kafka (`disburseLoan`, `LmsMessageBrokerConsumer`) | NOT COVERED | No `LmsMessageBrokerConsumer` in `src/test`; LOS util tests partial/commented |
| Disbursement LOS sync (`DisbursementSyncConsumer`, `entity_type`) | NOT COVERED | Consumer untested; contract gaps in `gaps-and-risks.md` |
| Repayment (`loanRepayment` + nested `postTransaction`) | PARTIAL | Processor/service unit tests; no full ORC chain integration |
| Collections bulk pipeline (`bulk_collection_data_*`, failed consumer) | NOT COVERED | `BulkCollectionFailedRecordConsumer` no test |
| Interest accrual / billing batches | PARTIAL | Processor tests; batch service CREF/idempotency not asserted |
| GL trial balance / zeroisation (`trialBalanceZeroisationJob`, `glBalanceZeroisation`) | NOT COVERED | grep no test hits for API name |
| Manual JE / reversal (`postManualJournalEntry`, `reverseTransaction`) | NOT COVERED | No `src/test` references |
| Death / foreclosure / insurance inbound-outbound jobs | NOT COVERED | Writers/consumers lack dedicated tests |
| Proactive excess refund / reverse staging | NOT COVERED | High gap on writer behaviour |
| NEFT / bank disburse (`CallBankAPIForDisbursementProcessor`) | PARTIAL | Some processor tests; bank leg mocked inconsistently |
| Portfolio transfer (accounting + actor + task) | PARTIAL | Fragment tests across modules |
| ENACH / SI presentation jobs | NOT COVERED | No job-level integration in accounting `src/test` scan |
| Multi-bureau / Posidex LOS consumers | NOT COVERED | All LOS Kafka consumers: N |
| Approval maker-checker target API execution | PARTIAL | Infra approval tests in lib; cross-service sparse |
| Gateway auth + forward (`AuthorizationCheckFilter`, `RequestForward*`) | NOT COVERED | GAP-059..060 |

## 2) Every `NovopayMessageBrokerConsumer` — automated test?

| # | Service | Consumer class | `src/test` reference? |

|---|---------|----------------|----------------------|

| 1 | novopay-mfi-los | `BpmnResponseConsumer` | N |
| 2 | novopay-mfi-los | `CkycApiKafkaConsumer` | N |
| 3 | novopay-mfi-los | `DisbursementSyncConsumer` | N |
| 4 | novopay-mfi-los | `EtbLanIdConsumer` | N |
| 5 | novopay-mfi-los | `FactivaConsumer` | N |
| 6 | novopay-mfi-los | `GenerateConsentDocumentConsumer` | N |
| 7 | novopay-mfi-los | `GenerateSpecificLoanDocumentConsumer` | N |
| 8 | novopay-mfi-los | `GeoTrackerAuditConsumer` | N |
| 9 | novopay-mfi-los | `GeoTrackerLoginLogoutAuditConsumer` | N |
| 10 | novopay-mfi-los | `InternalDedupeConsumer` | N |
| 11 | novopay-mfi-los | `LmsDataSyncConsumer` | N |
| 12 | novopay-mfi-los | `LosMessageBrokerConsumer` | N |
| 13 | novopay-mfi-los | `MMIRequestResponseLogConsumer` | N |
| 14 | novopay-mfi-los | `MultiBureauConsumer` | N |
| 15 | novopay-mfi-los | `OfflineDataConsumer` | N |
| 16 | novopay-mfi-los | `PosidexConsumer` | N |
| 17 | novopay-mfi-los | `PosidexInboundLosConsumer` | N |
| 18 | novopay-mfi-los | `PosidexOutboundLosConsumer` | N |
| 19 | novopay-mfi-los | `PosidexSecondCallConsumer` | N |
| 20 | novopay-platform-accounting-v2 | `BulkCollectionFailedRecordConsumer` | N |
| 21 | novopay-platform-accounting-v2 | `LmsMessageBrokerConsumer` | N |
| 22 | novopay-platform-actor | `PosidexInboundActorConsumer` | N |
| 23 | novopay-platform-actor | `SessionActivityLoginConsumer` | N |
| 24 | novopay-platform-actor | `SessionActivityLogoutConsumer` | N |
| 25 | novopay-platform-actor | `UpdateCustomerLoanDetailsConsumer` | N |
| 26 | novopay-platform-api-gateway | `RequestMessageBrokerConsumer` | N |
| 27 | novopay-platform-api-gateway | `ResponseMessageBrokerConsumer` | N |
| 28 | novopay-platform-audit | `AuditMessageBrokerConsumer` | N |
| 29 | novopay-platform-audit | `ExternalServiceAuditConsumer` | N |
| 30 | novopay-platform-audit | `RequestMessageBrokerConsumer` | N |
| 31 | novopay-platform-audit | `ResponseMessageBrokerConsumer` | N |
| 32 | novopay-platform-audit | `TelemetryConsumer` | N |
| 33 | novopay-platform-notifications | `NotificationEmailConsumer` | N |
| 34 | novopay-platform-notifications | `NotificationFCMConsumer` | N |
| 35 | novopay-platform-notifications | `NotificationMessageBrokerConsumer` | N |
| 36 | novopay-platform-notifications | `NotificationSMSConsumer` | N |
| 37 | novopay-platform-notifications | `NotificationsBrokerConsumer` | N |
| 38 | novopay-platform-payments | `CollectionOfficeDetailsConsumer` | N |
| 39 | novopay-platform-payments | `CollectionTaskProcessingConsumer` | N |
| 40 | novopay-platform-payments | `CreateOrUpdateBulkCollectionConsumer` | N |
| 41 | novopay-platform-payments | `PopulateCollectionCustomerDetailsConsumer` | N |
| 42 | novopay-platform-payments | `PopulateMeetingCenterDetailsConsumer` | N |
| 43 | novopay-platform-payments | `PrimaryAllocateCollectionConsumer` | N |
| 44 | novopay-platform-payments | `SecondaryAllocateCollectionConsumer` | N |
| 45 | novopay-platform-payments | `UpdateCollectionTaskDetailsConsumer` | N |
| 46 | novopay-platform-task | `CollectionTaskCreationConsumer` | N |
| 47 | novopay-platform-task | `FinnoneCollectionTaskCreationConsumer` | N |
| 48 | novopay-platform-task | `TaskUserTatKafkaConsumer` | N |

**Summary:** 48 consumer classes scanned; **0** have a test-file string hit.

## 3) Batch jobs — Spring `@Bean(name=...)` placeholders

### novopay-platform-accounting-v2

**Count:** **101** job beans. **Full-job integration test:** NOT EVIDENCED.

- `loanRecurringPaymentBatchApi` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGRefundMarkingJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToRefundMarkingJob` — NOT COVERED (naming grep in `src/test`)

- `generateEnachPresentationFile` — NOT COVERED (naming grep in `src/test`)

- `generateEnachRepresentationFile` — NOT COVERED (naming grep in `src/test`)

- `processingEnachPresentationResponseFiles` — NOT COVERED (naming grep in `src/test`)

- `processingEnachRepresentationResponseFiles` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGForeclosureChargeUpdateJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToForeclosureChargeUpdateJob` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGEnachRepresentationJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToEnachRepresentationJob` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGSecNpaReverseFeedFileJob` — NOT COVERED (naming grep in `src/test`)

- `runSecNpaBulkUploadJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToSecNpaReverseFeedFileJob` — NOT COVERED (naming grep in `src/test`)

- `bulkOutboundSecNpaReverseFeedFileJob` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGManualJournalEntriesJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToManualJournalEntriesJob` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGNocBlockUnblockJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToNocBlockUnblockJob` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGDispatchDetailsJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToDispatchDetailsJob` — NOT COVERED (naming grep in `src/test`)

- `generateNocFileJob` — NOT COVERED (naming grep in `src/test`)

- `updateLoanAccountDerivedFieldsJob` — NOT COVERED (naming grep in `src/test`)

- `updateLoanAccountDerivedFieldsMonthlyJob` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGFinsallRepaymentJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToFinsallRepaymentJob` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGTransactionReversalJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToTransactionReversalJob` — NOT COVERED (naming grep in `src/test`)

- `bulkFileToSGAssetCriteriaGroupUpdateJob` — NOT COVERED (naming grep in `src/test`)

- `bulkSGToAssetCriteriaGroupUpdateJob` — NOT COVERED (naming grep in `src/test`)

- `inboundReverseExcessAmountRefundJob` — NOT COVERED (naming grep in `src/test`)

- `runInboundReverseExcessAmountRefundJob` — NOT COVERED (naming grep in `src/test`)

- `loanAccountDpdCalcJob` — NOT COVERED (naming grep in `src/test`)

- `loanAccountAssetCriteriaJob` — NOT COVERED (naming grep in `src/test`)

- `loanAccountAssetClassificationJob` — NOT COVERED (naming grep in `src/test`)

- `loanAccountBillingJob` — NOT COVERED (naming grep in `src/test`)

- `childLoanEventProcessingBatchJob` — NOT COVERED (naming grep in `src/test`)

- `loanInstallmentDueNotificationJob` — NOT COVERED (naming grep in `src/test`)

- `loanInstallmentBounceNotificationJob` — NOT COVERED (naming grep in `src/test`)

- `outboundDeathForeclosureInsuranceJob` — NOT COVERED (naming grep in `src/test`)

- … **61** additional names in same config — same classification.

### trustt-platform-reporting

**Count:** **103** job beans — NOT COVERED (default).

## 4) Orchestration XML — integration test per file?

**Total XML files:** **60**.

**Criterion:** test loads XML + runs `ServiceOrchestrator` with fixture context.

**Result:** NOT FOUND — processor unit tests dominate; XML files are not asserted individually.

| Path fragment | Files | IT per XML? |

|---------------|-------|-------------|

| accounting-v2 | 9 | NO |
| actor | 29 | NO |
| api-gateway | 1 | NO |
| approval | 2 | NO |
| audit | 1 | NO |
| authorization | 2 | NO |
| batch | 1 | NO |
| dms | 1 | NO |
| masterdata-management | 1 | NO |
| mfi-los | 1 | NO |
| notifications | 4 | NO |
| payments | 4 | NO |
| reporting | 1 | NO |
| task | 3 | NO |

## 5) Critical path score by service (approximate)

| Service | Est. critical-path test % | Rationale |

|---------|---------------------------|-----------|

| novopay-platform-accounting-v2 | 25% | Processor tests exist; async disburse, GL zeroisation, batch e2e missing |
| novopay-mfi-los | 15% | All Kafka consumers untested in grep pass |
| novopay-platform-payments | 20% | Consumers untested |
| novopay-platform-actor | 30% | Breadth of tests; async notification path weak |
| novopay-platform-task | 20% | Finnone consumer untested |
| novopay-platform-batch | 10% | Scheduler tests sparse |
| novopay-platform-api-gateway | 5% | Filters untested |
| novopay-platform-authorization | 25% | Partial processor coverage |
| novopay-platform-approval | 20% | Partial |
| novopay-platform-audit | 15% | Consumers untested |
| novopay-platform-notifications | 20% | Consumers untested |
| novopay-platform-masterdata-management | 25% | Varies |
| novopay-platform-dms | 20% | Sparse |
| trustt-platform-reporting | 10% | Extract jobs |

## 6) Processor-level tests (examples)

- `novopay-platform-accounting-v2/src/test/.../LoanAdvanceRepaymentServiceTest.java`

- `.../InterestAccrualBookingProcessorTest.java`

- `.../CustomCallPostTransactionProcessorTest.java`

- `novopay-mfi-los/src/test/.../PostDisbursementProcessServiceTest.java`


## 7) Recommended next tests (prioritised)

1. `JobLauncherTestUtils` golden path: disburse + repayment.

2. Testcontainers: `LmsMessageBrokerConsumer`, `BulkCollectionFailedRecordConsumer`.

3. MockMvc: `AuthorizationCheckFilter` + `RequestForwardProcessor`.

4. SI/ENACH: one inbound file processing job with staging assertions.


## 8) Glossary: what NOT COVERED means here

- **NOT COVERED:** no `src/test` reference to the consumer class, job bean name, or orchestration file.

- **PARTIAL:** unit tests cover helpers/processors but not end-to-end money movement.


## 9) Remaining accounting batch bean names (rows 41–101) — all NOT COVERED unless proven

`BatchJobPlaceholderConfig.java` registers: `outboundDisbursementBajajErgoHealthInsuranceJob`, `outboundDisbursementHdfcLifeLifeInsuranceJob`, `outboundDisbursementHdfcErgoHealthInsuranceJob`, `inboundDisbursementHdfcErgoHealthInsuranceJob`, `inboundDisbursementBajajErgoHealthInsuranceJob`, `inboundDisbursementHdfcLifeLifeInsuranceJob`, `runInboundDisbursementHdfcErgoHealthInsuranceJob`, `runInboundDisbursementBajajErgoHealthInsuranceJob`, `runInboundDisbursementHdfcLifeLifeInsuranceJob`, `deleteAccountingTaskUsingCode`, `extractCasaBalanceFor180ProductCode`, `extractCasaBalanceFor182ProductCode`, `proactiveExcessAmountRefundStaging`, `proactiveExcessAmountRefund`, `proactiveReverseTransaction`, `penalInterestAccrualCalculation`, `penalInterestAccrualBooking`, `loanAccountClosure`, `interestAccrualCalculation`, `interestAccrualPosting`, `loanAdvanceRepayment`, `generateSIPresentationFiles`, `processingSIReverseFeedFiles`, `generateSIAutoHoldRemovalPresentationFiles`, `processingSIAutoHoldRemovalReverseFeedFiles`, `generateFinnoneSILienPresentationFiles`, `generateSIManualHoldRemovalPresentationFiles`, `processingSIManualHoldRemovalReverseFeedFiles`, `generateSIManualHoldMarkingPresentationFiles`, `processingSIManualHoldMarkingReverseFeedFiles`, `generateSIManualPresentationFiles`, `processingSIManualPresentationReverseFeedFiles`, `expirePendingMandatesBatchJob`, `siFileTransferBatchJob`, `siFileEnquiryBatchJob`, `siFileDownloadBatchJob`, `bulkFileToSGManualHoldRemovalJob`, `bulkFileToSGManualHoldMarkingJob`, `bulkSGToManualHoldRemovalJob`, `bulkSGToManualHoldMarkingJob`, `generatePostEODReports`, `generateTBZeroisationReport`, `trialBalanceCalculation`, `accountingBankServiceRetryJob`, `trialBalanceZeroisationJob`, `retrySIJob` — **none** matched in `src/test` by bean name grep (2026-04-10).

## 10) `novopay-platform-lib` — shared orchestration / HTTP

| Area | Tests? | Note |
|------|--------|------|
| `NovopayInternalAPIClient` / `NovopayHttpAPIClient` | PARTIAL | Some partner-specific tests (e.g. CCAvenue); **no** resilience suite |
| Navigation / orchestrator | PARTIAL | Framework tests sparse; behaviour validated indirectly in services |
| Message broker builder | NOT COVERED | Tenant topic suffix logic untested at lib level |

## 11) Waves 1–4 mined risks vs automated regression

| GAP | Theme | Test expectation |
|-----|-------|------------------|
| GAP-031..034 | platform-lib cache/logging | NOT COVERED |
| GAP-035..037 | accounting batch / consumer / NOC | NOT COVERED / PARTIAL |
| GAP-038..045 | LOS + payments Kafka / bulk | NOT COVERED |
| GAP-046..053 | task + batch scheduler | NOT COVERED |
| GAP-054..060 | gateway + auth + forward | NOT COVERED |

## 12a) Evidence commands (reproducible)

```bash
# Consumers vs tests
grep -r "implements NovopayMessageBrokerConsumer" --include="*.java" novopay-* trustt-* | wc -l
grep -r "LmsMessageBrokerConsumer" --include="*.java" */src/test | wc -l

# Orchestration XML count
find . -path "*/deploy/application/orchestration/*.xml" | wc -l

# Batch job beans
grep -c '@Bean(name' novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/config/BatchJobPlaceholderConfig.java
```

## 12) `trustt-platform-reporting` job name sample (first 40 of 103)

`nrlmClaimAmountReportJob`, `generatePosReportExtractJob`, `generateMergeReportExtractJob`, `generateLoanCardIndividualReportExtractJob`, `generateRepaymentScheduleExtractJob`, `generateDisbursementAdviceReportExtractJob`, `loanAppAdditionalDetailsJob`, `generateNrlmNonRegisteredGroupReportJob`, `nrlmMasterDataReportJob`, `loanAppStageJob`, `generateCustomerLevelDumpExtractJob`, `generateGroupLevelDumpExtractJob`, `dpdBucketJob`, `posidexDailyReverseHandoffJob`, `inboundPosidexDailyExtractJob`, `posidexDailyWeeklyReconcilationJob`, `outboundPosidexDailyExtractJob`, `generateEmployeeRoleHierarchyExtractJob`, `generateGroupDataExtractJob`, `generateInsuranceReportJob`, `generateAPYBaseNetDataExtractJob`, `generateVillageCreationTrailReportJob`, `villageDetailsAooJob`, `generateOnePlusExtractJob`, `generatePosidexBadFileExtractJob`, `generatePosidexGoodFileExtractJob`, `generatePosidexRejectFileExtractJob`, `generateCreditBaseIndvLoanDataJob`, `generateCreditBaseGroupDataJob`, `generateUAMLoginLogoutExtractJob`, `generateUAMAdminActivityExtractJob`, `generateUAMRoleRightExtractJob`, `generateUAMPopulationExtractJob`, `bulkOutboundCoborrowerSummJob`, `bulkOutboundConsumerBaseFileJob`, `bulkOutboundCoBorrowerFileJob`, `assetBaseFileSyncJob`, `bulkOutboundAssetBaseFileJob`, `bulkOutboundAssetBaseSummCntJob`, `generateCustomerLevelDataExtractJob` — **NOT COVERED** (static scan).

## 13) Disbursement cancellation, waiver, charges (accounting)

| Flow | Status | Note |
|------|--------|------|
| Disbursement cancellation preprocessors | PARTIAL | `ValidateDataForDisbursementCancellationTest` and related |
| Cancellation + `postTransaction` LOAN_DISB_CNCL end-to-end | NOT COVERED | No ledger assertion suite |
| Waiver / charges update | PARTIAL | Processor-only tests |
| Write-off posting | PARTIAL | `LoanProvisioningPostingServiceTest` slice |

## 14) Payments money-adjacent paths

| Flow | Status |
|------|--------|
| Primary/secondary allocation consumers | NOT COVERED |
| Collection task processing consumer | NOT COVERED |
| Finnone task utility publish path | NOT COVERED (integration) |

## 15) `novopay-platform-batch` scheduler

| Area | Status |
|------|--------|
| `SchedulerCommonService` / `DirectJobExecutor` | NOT COVERED (see multi-node gaps) |
| Bulk upload orchestration | PARTIAL possible — grep target classes |

---

*Rebuild 2026-04-10.*
