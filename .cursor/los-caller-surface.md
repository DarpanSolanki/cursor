# LOS as caller — the cross-service surface into accounting, payments, actor

Scope: `trustt-platform-los` is **out of scope as a test target** in this workspace (no registry
cases are being added for LOS's own APIs). This document is about LOS **as caller** — every place
LOS Java code reaches into another service, because that is a contract boundary this workspace
does track (`api-contract-safety.md`). Read-only research; no source, registry, or KG was touched.

**Everything here runs correctly in production.** Every "fragile" flag below is a structural risk
— a pattern that would break if a producer response shape changed, the same way
`fetchLoanAccountChargeDetails` already did once (`.cursor/rules/api-contract-safety.mdc`) — not a
live defect, unless stated otherwise with direct evidence.

## Provenance

- `grep -rln "callInternalAPI" trustt-platform-los/src/main/java` → 132 files; regex-extracted
  every `callInternalAPI(...)` call (279 total in LOS, across **all** target services). Filtered
  to the 132 call sites whose resolved `apiName` maps to `trustt-platform-accounting` (31),
  `trustt-platform-payments` (1) or `trustt-platform-actor` (100 direct + 8 indirect via the
  `ActorUtil.internalCallForActorApi(ctx, apiName)` wrapper).
- apiName → owning repo resolved against `cursor-bundle/flow-test/platform_api_map.jsonl`
  (1955 APIs, one JSON object per line).
- Prior session's `scripts/scratch/internal-caller-map/REPORT.md` already covers the
  LOS→accounting edge in depth (23 of 24 accounting call targets, response fields, coverage
  verdicts) — reused and cited directly for that slice rather than re-derived, then supplemented
  here with the actor and payments edges it did not cover, plus fresh fragile-pattern evidence.
- No `WebClient` / `RestTemplate` direct calls to accounting/payments/actor endpoints were found
  in LOS outside the `NovopayInternalAPIClient.callInternalAPI` pattern —
  `grep -rln "WebClient\|RestTemplate" trustt-platform-los/src/main/java` returns hits only for
  LOS's own bank/e-sign/DMS integrations (JTF/bank templates), not internal service calls.

## 1. Full LOS call-site inventory

`method` is the nearest enclosing method above the call site (`?` where the regex heuristic could
not resolve it — always verifiable by opening the file at that line). Rows marked "via
`ActorUtil.internalCallForActorApi`" call a **generic actor-call wrapper**
(`trustt-platform-los/src/main/java/in/novopay/los/util/ActorUtil.java:222-234`) that itself calls
`callInternalAPI(ctx, apiName, "v1", "getActorApi_response", -1, -1, false)` with the literal
`apiName` string the caller passed — the file:line cited is the caller of the wrapper, which is
where the target API is actually chosen.

### trustt-platform-accounting — 31 call sites, 22 distinct apiNames

| file:line | method | apiName | response handling |
|---|---|---|---|
| `los/repository/KeyFactSheetDataService.java:276` | `calculateAPR` | `calculateAnnualPercentageRate` | response captured via `getAPIResponse`; downstream handling not individually re-derived here (see REPORT.md for consumed fields) |
| `los/util/AccountingUtil.java:326` | `callCalculateStampDutyCharges` | `calculateStampDutyCharges` | response captured via `getAPIResponse`; feeds e-sign/KFS stamp-duty display (REPORT.md #12) |
| `los/util/AccountingUtil.java:271` | `checkInsuranceGeoEligibility` | `checkInsuranceProductGeoEligibility` | response captured via `getAPIResponse` |
| `los/util/CreateMandateAPIUtil.java:69` | `createRepaymentMandate` | `createRepaymentMandateDetails` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:361` | `getProcessingFee` | `fetchLoanAccountChargeDetails` | response captured via `getAPIResponse` — feeds `GetPreDisbursementSummaryProcessor.getProcessingFee()` → `charges_details` in shared context (§3 finding #1) |
| `los/util/AccountingUtil.java:255` | `callGenerateRepaymentSchedule` | `generateRepaymentSchedule` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:377` | `callGetBulkAccountDetails` | `getBulkLoanAccountDetails` | whole response map read via `getAPIResponse("getBulkLoanAccountDetails_response")` (REPORT.md #9) |
| `los/util/AccountingUtil.java:399` | `callGetBulkAccountDetails` | `getChildLoanAccountList` | response captured via `getAPIResponse` |
| `los/util/CommonUtil.java:556` | `getAccountDerivedDataList` | `getCustomerLoanAccountBounces` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:485` | `callUpdateChildLoanDisbursementStatus` | `getEffectiveInterestRateForInterestSetupCode` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:520` | `callHolidayListAPI` | `getHolidayList` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:224` | `callGetInsurancePremiumAmount` | `getInsurancePremiumAmount` | response captured via `getAPIResponse` |
| `los/util/LoanAccountStatusEnquiryAPIUtil.java:37` | `callLoanStatusEnquiryAPI` | `getLoanAccountDetails` | response captured via `getAPIResponse`; primary consumer is `GenerateLARPreProcessor` (§3 finding #2) |
| `los/util/AccountingUtil.java:209` | `callGetLoanAccountList` | `getLoanAccountList` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:150` | `callLmsApiForRepaymentDate` | `getLoanAccountOverviewDetails` | response captured via `getAPIResponse` |
| `los/processor/GetEligibilitySummaryDetailsProcessor.java:198` | `getBorrowerBasicAndCreditReportDetails` | `getLoanProductDetails` | response captured via `getAPIResponse` |
| `los/repository/GroupMembersDetailsDaoService.java:768` | `updateGroupLoansRateOfInterest` | `getLoanProductDetails` | reads `installment_type` (REPORT.md #3) |
| `los/repository/KeyFactSheetDataService.java:529` | `getKfsDetailsFromRepaymentShedule` | `getLoanProductDetails` | response captured via `getAPIResponse` |
| `los/repository/jasper/ScheduleCumKeyFactSheetDataService.java:205` | `getInstallmentFrequency` | `getLoanProductDetails` | reads `repayment_frequency_value` (REPORT.md #3) |
| `los/util/AccountingUtil.java:51` | `?` | `getLoanProductDetails` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:69` | `?` | `getLoanProductDetails` | response captured via `getAPIResponse` |
| `los/util/CommonUtil.java:888` | `setExpectedAndRepaymentDate` | `getLoanProductDetails` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:105` | `?` | `getLoanProductList` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:166` | `callGetLoanProductList` | `getLoanProductList` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:196` | `getLoanProductList` | `getLoanProductList` | response captured via `getAPIResponse` |
| `los/repository/OriginationCardsListDAOService.java:56` | `?` | `getProductSchemeDetails` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:501` | `callWorkingDaysAPI` | `getWorkingDays` | response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:428` | `callUpdateChildLoanDisbursementStatus` | `updateChildLoanDisbursementStatus` | mutating; response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:178` | `callUpdateLoanAccountPreDisbursementDetailsApi` | `updateLoanAccountPreDisbursementDetails` | mutating; response captured via `getAPIResponse` |
| `los/util/AccountingUtil.java:461` | `callUpdateChildLoanDisbursementStatus` | `updateLoanAccountPreDisbursementDetails` | mutating; response captured via `getAPIResponse` |
| `los/util/UpdateMandateAPIUtil.java:42` | `updateMandateStatus` | `updateMandateStatus` | mutating; response captured via `getAPIResponse` |

### trustt-platform-payments — 1 call site, 1 apiName

| file:line | method | apiName | response handling |
|---|---|---|---|
| `los/processor/pan/CreateOrUpdatePanDetailsProcessor.java:124` | `updatePanDetails` region (see lines 100-144) | `updateCustomerPan` | **well-guarded** — `response == null` throws `LOS-0579` (line 136), then `status` field checked for `"SUCCESS"` before proceeding (line 139-142). The one LOS→payments internal-API call site in the codebase. |

### trustt-platform-actor — 100 direct + 8 indirect (via `ActorUtil.internalCallForActorApi`) call sites, 58 distinct apiNames

| file:line | method | apiName | response handling |
|---|---|---|---|
| `los/util/ActorUtil.java:1127` | `callCheckExternalIdExists` | `checkExternalIdExists` | response captured via `getAPIResponse` |
| `los/processor/CreateBorrowerProcessor.java:193` | `saveBorrowerDetails` | `createMfiCustomer` | mutating; response captured via `getAPIResponse` |
| `los/processor/CreateOrUpdateGroupCustomerProcessor.java:187` | `saveCustomerDetails` | `createMfiCustomer` | mutating; response captured via `getAPIResponse` |
| `los/processor/CreateCustomerProcessor.java:74` | `process` | `createOrUpdateCustomer` | mutating; response captured via `getAPIResponse` |
| `los/util/ActorAPIUtil.java:92` | `getEmployeeUserIdsByEmployeeIds` | `getActorBasicDetails` | response captured via `getAPIResponse` |
| `los/util/ActorAPIUtil.java:105` | `getEmployeeUserIdsByEmployeeIds` | `getActorHomeAndOfficeLocation` | response captured via `getAPIResponse` |
| `los/repository/jasper/GroupLevelInterSeAgreementFinalDataService.java:236` | `setPincode` | `getAddressFromVtc` | response captured via `getAPIResponse` |
| `los/repository/jasper/SignatoryLevelMasterAgreementReportDataService.java:208` | `setAddressDetails` | `getAddressFromVtc` | response captured via `getAPIResponse` |
| `los/repository/jasper/SignatoryLevelMasterAgreementReportDataService.java:357` | `setPincodeDetails` | `getAddressFromVtc` | response captured via `getAPIResponse` |
| `los/audit/report/GetActivityDetailsFromAuditProcessor.java:45` | `process` (via `ActorUtil.internalCallForActorApi`) | `getAuditDetails` | response object read; downstream not individually traced |
| `los/audit/report/GetAuditDataProcessor.java:47` | `process` (via `ActorUtil.internalCallForActorApi`) | `getAuditDetails` | response object read; downstream not individually traced |
| `los/audit/report/GetLoanDemographicsHistoryProcessor.java:38` | `process` (via `ActorUtil.internalCallForActorApi`) | `getAuditEsDataByUserStory` | `response.get("data")` cast to `List`, iterated with no null/empty guard (§3 finding #3) |
| `los/util/ActorUtil.java:341` | `callGetEmployeeDetails` | `getBankEmployeeDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:1000` | `getBankEmployeeDetailsFromUserId` | `getBankEmployeeDetails` | response captured via `getAPIResponse` |
| `los/processor/GetCMDetailsProcessor.java:90` | `processCuMemberEntityList` | `getBulkUserDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:932` | `callGetBulkUserDetails` | `getBulkUserDetails` | response captured via `getAPIResponse` |
| `los/processor/CreateAndCompleteTaskProcessor.java:1278` | `?` | `getCensusVillageDetails` | response captured via `getAPIResponse` |
| `los/processor/CreateAndCompleteTaskProcessor.java:1431` | `createEsignTask` | `getCensusVillageDetails` | response captured via `getAPIResponse` |
| `los/processor/CreateAndCompleteTaskProcessor.java:2919` | `setVillageDetailsInPrintLoanDocumentTask` | `getCensusVillageDetails` | response captured via `getAPIResponse` |
| `los/processor/GetLoanAppListProcessor.java:248` | `setVtcAddress` | `getCensusVillageDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:847` | `setVtcAddress` | `getCensusVillageDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:1093` | `callGetCustomerAddressDetails` | `getCustomerAddressDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:285` | `callGetCustomerAndOfficeDetails` | `getCustomerAndOfficeDetailsFromId` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:128` | `callBehaviourScore` | `getCustomerBehaviourScore` | response captured via `getAPIResponse` |
| `los/processor/GetBorrowerContactDetailsByLanProcessor.java:67` | `process` | `getCustomerContactNumbers` | response captured via `getAPIResponse` |
| `los/processor/GetDDEBorrowerDetailsProcessor.java:102` | `process` | `getCustomerDetails` | response captured via `getAPIResponse` |
| `los/repository/OriginationCardsListDAOService.java:70` | `?` | `getCustomerDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:399` | `callgetEmployeeActorUserIds` | `getCustomerDetails` | response captured via `getAPIResponse` |
| `los/util/ActorAPIUtil.java:36` | `?` | `getCustomerDetailsForCollection` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:85` | `callGetUserDetails` | `getCustomerDetailsList` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:196` | `callGetDistanceBetweenOffice` | `getCustomerDistanceFromMeetingCenter` | response captured via `getAPIResponse` |
| `los/util/ActorAPIUtil.java:150` | `getVTCDetails` | `getDetailsFromVtcId` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:257` | `getDistanceBetweenAusAndGroupMembers` | `getDistanceBetweenCustomers` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:756` | `callGetDistanceBetweenMeetingCenterAndOffice` | `getDistanceBetweenMeetingCenterAndOffice` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:377` | `callgetEmployeeActorUserIds` | `getEmployeeActorUserIds` | response captured via `getAPIResponse` |
| `los/batch/bulkupload/processor/BulkFileToStagingTableJobProcessor.java:135` | `setEmployeeDetails` | `getEmployeeDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:629` | `callGetUserBasicDetails` | `getEmployeeDetails` | response captured via `getAPIResponse` |
| `los/processor/GetCoListMappedToSoBranchProcessor.java:40` | `process` | `getEmployeeListByRoleAndOffice` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:479` | `callGetEmployeeListByRoleAndOffice` | `getEmployeeListByRoleAndOffice` | response captured via `getAPIResponse` |
| `los/getrenewalgroupsdashboard/GetRenewalGroupsProcessor.java:159` | `getSourcingEmployee` (via `ActorUtil.internalCallForActorApi`) | `getEmployeeNameList` | response object read; downstream not individually traced |
| `los/util/ActorAPIUtil.java:73` | `?` | `getEmployeeNameList` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:359` | `callGetEmployeeNameList` | `getEmployeeNameList` | response captured via `getAPIResponse` |
| `los/processor/GetLoanAppCUDetailsProcessor.java:219` | `getEmployeeParentIdsApiCall` | `getEmployeeParentIds` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:720` | `getEmployeeParentUserIdsApiCall` | `getEmployeeParentIds` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:737` | `getEmployeeParentIdsApiCall` | `getEmployeeParentIds` | response captured via `getAPIResponse` |
| `los/portfoliotransfer/service/LOSPortfolioTransferService.java:884` | `getUserIdToOfficeIdsFromActor` | `getEmployeeServiceableOffices` | response captured via `getAPIResponse` |
| `los/repository/GroupAdvancedFilterRowMapper.java:251` | `getEmployees` (via `ActorUtil.internalCallForActorApi`) | `getEmployeesIdListUnderUserId` | response object read; downstream not individually traced |
| `los/util/ActorAPIUtil.java:56` | `?` | `getEmployeesIdListUnderUserId` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:776` | `callGetDistanceBetweenMeetingCenterAndOffice` | `getEmployeesIdListUnderUserId` | response captured via `getAPIResponse` |
| `los/processor/consent/GetLanguageBasedOnUserIdService.java:22` | `getLanguage` | `getLanguageByUserId` | response captured via `getAPIResponse` |
| `los/processor/CreateAndCompleteTaskProcessor.java:1284` | `?` | `getMeetingCenterDetails` | response captured via `getAPIResponse` |
| `los/processor/CreateAndCompleteTaskProcessor.java:1439` | `createEsignTask` | `getMeetingCenterDetails` | response captured via `getAPIResponse` |
| `los/processor/CreateAndCompleteTaskProcessor.java:2893` | `setMeetingCenterDetailsInPrintLoanDocumentTask` | `getMeetingCenterDetails` | response captured via `getAPIResponse` |
| `los/processor/GetPdcGroupLoanDetailsProcessor.java:63` | `process` | `getMeetingCenterDetails` | **unguarded double chain** — see §3 finding #4 |
| `los/util/ActorUtil.java:180` | `callGetDistanceBetweenOffice` | `getMeetingCenterDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:704` | `callMeetingCenterDetailsList` | `getMeetingCenterDetailsList` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:537` | `callGetMeetingCenterLists` | `getMeetingCenterLists` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:655` | `callGetVtcListByOfficeIdAndEmployeeId` | `getMfiVtcListForOfficeIdAndEmployeeId` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:642` | `callGetOfficeByVtcId` | `getOfficeByVtcId` | response captured via `getAPIResponse` |
| `los/getrenewalgroupsdashboard/GetRenewalGroupsProcessor.java:127` | `getBranchNameAndVillageName` (via `ActorUtil.internalCallForActorApi`) | `getOfficeCodeAndNameByIds` | response object read; downstream not individually traced |
| `los/util/ActorUtil.java:1065` | `getBasicOfficeInfoByList` | `getOfficeCodeAndNameByIds` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:212` | `callGetDistanceBetweenOffice` | `getOfficeFromEmployeeId` | response captured via `getAPIResponse` |
| `los/processor/CheckCustomerMobileDedupeProcessor.java:303` | `constructErrorMessage` | `getOfficeNameByEmployeeId` | response captured via `getAPIResponse` |
| `los/repository/jasper/BorrowerLevelMemberEnrollmentLifeInsuranceFormDataService.java:132` | `setEmployOfficeDetails` | `getOfficeNameByEmployeeId` | response captured via `getAPIResponse` |
| `los/repository/jasper/TermsAndConditionsFormDataService.java:83` | `getPlaceName` | `getOfficeNameByEmployeeId` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:947` | `callGetBulkUserDetails` | `getOfficeNameByEmployeeId` | response captured via `getAPIResponse` |
| `los/processor/CreateLoanAppProcessor.java:120` | `callActorApi` | `getPromoCodeDetails` | response captured via `getAPIResponse` |
| `los/repository/jasper/GroupLevelLoanApplicationFormDataService.java:168` | `prepareDataForResponse` | `getPromoCodeDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:273` | `callGetPromoCodeDetailApi` | `getPromoCodeDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:686` | `callPromocodeDetailsByPromocodeList` | `getPromoCodeDetailsList` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:858` | `getAssigneeContributorForReAllocationTask` | `getSoAllocationDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:1108` | `callGetStateDistrictVtcList` | `getStateDistrictVtcList` | **guarded** — `MapUtils.isNotEmpty(apiResponse)` checked before `apiResponse.get("vtc_details")` cast (line ~1114-1117) |
| `los/util/ActorAPIUtil.java:173` | `getUserBasicDetails` | `getUserBasicDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:612` | `callGetUserBasicDetails` | `getUserBasicDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:69` | `callGetUserDetails` | `getUserDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:886` | `getUserDetailsByHandleValue` | `getUserDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:906` | `getVillageDetailsByCensusCode` | `getVillageDetails` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:550` | `callGetVillageListForOfficeIds` | `getVillageListForOfficeIds` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:98` | `callVrmCategory` | `getVillageRiskMapping` | response captured via `getAPIResponse` |
| `los/batch/ckyc/writer/CkycInputDataItemWriter.java:280` | `getVillageNamesByVtcList` | `getVillageRiskMappingForVtcList` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:670` | `callVillageDetailsByVtcList` | `getVillageRiskMappingForVtcList` | response captured via `getAPIResponse` |
| `los/util/ActorAPIUtil.java:117` | `getVtcByEmployeeId` | `getVtcByEmployeeId` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:115` | `callVrmCategory` | `getVtcDetailsById` | response captured via `getAPIResponse` |
| `los/processor/GetVtcListBasedOnPincodeProcessor.java:22` | `process` | `getVtcList` | response captured via `getAPIResponse` |
| `los/processor/GetLeadsListProcessor.java:35` | `process` | `getVtcListForOfficeId` | response captured via `getAPIResponse` |
| `los/getrenewalgroupsdashboard/GetRenewalGroupsProcessor.java:137` | `getBranchNameAndVillageName` (via `ActorUtil.internalCallForActorApi`) | `getVtcNameListBasedOnIds` | response object read; downstream not individually traced |
| `los/processor/GetGroupCustomerDetailsProcessor.java:542` | `setRmReviewFinalizationSpecficDetails` (via `ActorUtil.internalCallForActorApi`) | `getVtcNameListBasedOnIds` | response object read; downstream not individually traced |
| `los/processor/GetRenewalSummaryListProcessor.java:343` | `fillLanToVtcMappingMap` | `getVtcNameListBasedOnIds` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:581` | `setAssigneeContributorBasedOnOfficeId` | `getWorkAreaByEmployeeId` | response captured via `getAPIResponse` |
| `los/processor/CheckCustomerDedupeProcessor.java:42` | `process` | `performInternalDedupe` | response captured via `getAPIResponse` |
| `los/processor/CheckCustomerMobileDedupeProcessor.java:281` | `constructErrorMessage` | `performInternalDedupe` | response captured via `getAPIResponse` |
| `los/util/ActorUtil.java:441` | `callgetEmployeeActorUserIds` | `saveReKycDetailsOnDisbursement` | mutating; response object read, downstream not individually traced |
| `los/processor/CreateOrUpdateGroupCustomerProcessor.java:191` | `saveCustomerDetails` | `updateMFICustomerDetails` | mutating; response captured via `getAPIResponse` |
| `los/processor/UpdateEditDemographicsProcessor.java:349` | `?` | `updateMFICustomerDetails` | mutating; response captured via `getAPIResponse` |
| `los/repository/LoanAppDaoService.java:1509` | `findAllIndividualNTBLoanAppIdByEmployeeId` | `updateMFICustomerDetails` | mutating; response object read, downstream not individually traced |
| `los/repository/LoanAppDaoService.java:1537` | `findAllIndividualNTBLoanAppIdByEmployeeId` | `updateMFICustomerDetails` | mutating; response object read, downstream not individually traced |
| `los/repository/LoanAppDaoService.java:1569` | `setBusinessAddressInActor` | `updateMFICustomerDetails` | mutating; response object read, downstream not individually traced |
| `los/util/ActorUtil.java:594` | `callUpdateMFICustomerDetails` | `updateMFICustomerDetails` | mutating; response object read, downstream not individually traced |
| `los/batch/bulkupload/salespromocode/iwriter/SGToSalesPromocodeItemWriter.java:85` | `write` | `verifyNRLMStateCode` | response captured via `getAPIResponse` |
| `los/batch/shgcode/tasklet/ShgCodeBulkUploadDuplicateCheckTasklet.java:72` | `execute` | `verifyNRLMStateCode` | response captured via `getAPIResponse` |

All `file:line` above are program-generated from a balanced-paren scan of every
`callInternalAPI(...)` invocation in `trustt-platform-los/src/main/java` (regex + arg-splitter,
not a fixed-width grep), so they are exact call-site lines — verify any row with
`sed -n '<line-5>,<line+5>p' <file>`. Rows tagged "response object read; downstream not
individually traced" are ones this pass captured the `getAPIResponse(...)` call for but did not
walk the full consuming method body for — the file:line is exact, the risk classification is not
claimed beyond what §3 states explicitly.

## 2. Cross-reference against accounting's coverage state

**`.cursor/accounting-coverage-map.md` exists but does not have per-apiName verdicts for the
APIs in this list.** Its scope is the 351-apiName live surface graded into **loan transactions**
(Tier A/B money-write worklist: `loanDisbursementCancellation`, `reverseTransaction`,
`loanAccountExcessAmountRefund`, `childLoanTransactionReversal`, `childLoanForeclosure`,
`childLoanDisbursementCancellation`, `childWaiveLoanAccountCharges`, `loanAccountRestructuring`,
`loanAdvanceRepayment`, `loanAccountClosure`) and the 15-placeholder list. **None of the 22
accounting apiNames LOS calls appear in either list** — they are read-inquiry / config / write-ops
APIs (`getLoanProductDetails`, `getLoanProductList`, `fetchLoanAccountChargeDetails`,
`updateLoanAccountPreDisbursementDetails`, …), which is a different denominator from
`accounting-coverage-map.md`'s money-transaction focus. Rather than guess, per-API verdicts below
are cited from `scripts/scratch/internal-caller-map/REPORT.md`, an apiName-indexed coverage table
built the same way (joined against `scripts/testing/registry.json` on the case's `api`/`apis`
field, never the case id) that does cover this exact set.

| LOS-called accounting API | covered/uncovered | source |
|---|---|---|
| `getLoanProductList` | UNCOVERED (no case) — 35 total callers across 7 services | REPORT.md table 1, row 1 |
| `getLoanProductDetails` | UNCOVERED (no case) — 12 total callers, LOS is 8 of them | REPORT.md table 1, row 2 |
| `getLoanAccountOverviewDetails` | UNCOVERED (case exists, no `verify_mode`) `dpic.overview_api` | REPORT.md table 1, row 5 |
| `getBulkLoanAccountDetails` | UNCOVERED (no case) | REPORT.md table 1, row 13 |
| `calculateStampDutyCharges` | UNCOVERED (no case) | REPORT.md table 1, row 16 |
| `getLoanAccountDetails` | UNCOVERED (no case) — 3 backend + 16 webapp refs | REPORT.md table 1, row 19 |
| `fetchLoanAccountChargeDetails` | UNCOVERED (no case) — **the incident API** (`charges_configured`) | REPORT.md table 1, row 22 / §3 "the incident API" |
| `getWorkingDays` | UNCOVERED (no case) | REPORT.md table 1, row 24 |
| `updateLoanAccountPreDisbursementDetails` | UNCOVERED (3 cases exist, **all missing `verify_mode`**) | REPORT.md table 1, row 29 |
| `getHolidayList` | UNCOVERED (no case) | REPORT.md table 1, row 30 |
| `getProductSchemeDetails` | UNCOVERED (no case) | REPORT.md table 1, row 14 |
| `getLoanAccountList` | UNCOVERED (no case) | REPORT.md table 1, row 15 |
| `generateRepaymentSchedule` | UNCOVERED (no case) | REPORT.md table 1, row 37 |
| `getEffectiveInterestRateForInterestSetupCode` | UNCOVERED (no case) | REPORT.md table 1, row 39 |
| `checkInsuranceProductGeoEligibility` | UNCOVERED (no case) | REPORT.md table 1, row 40 |
| `updateChildLoanDisbursementStatus` | UNCOVERED (no case) | REPORT.md table 1, row 41 |
| `updateMandateStatus` | UNCOVERED (no case) | REPORT.md table 1, row 42 |
| `getChildLoanAccountList` | UNCOVERED (no case) | REPORT.md table 1, row 43 |
| `getInsurancePremiumAmount` | UNCOVERED (no case) | REPORT.md table 1, row 44 |
| `getCustomerLoanAccountBounces` | UNCOVERED (no case) | REPORT.md table 1, row 45 |
| `createRepaymentMandateDetails` | UNCOVERED (sim only) `disbursement.clb_mandate_match_sim` | REPORT.md table 1, row 47 |
| `calculateAnnualPercentageRate` | UNCOVERED (no case) | REPORT.md table 1, row 33 |

**All 22 of the 22 accounting apiNames LOS calls are uncovered or sim-only.** Zero are in
REPORT.md's `**covered** (runtime)` set — `getLoanForeclosureDetails`, `disburseLoan`,
`loanRepayment`, `loanPrepayment`, `loanAccountPartPrepayment` are the five runtime-covered
accounting APIs, and LOS calls only one of them: `disburseLoan` (row 35, called from
`DisburseLoanProcessor` / `DisburseGroupLoanProcessor` per the Kafka-producer path documented in
`.cursor/rules/los.mdc`, not via the synchronous `callInternalAPI` scan above — that is the
Kafka `disburse_loan_api_*` topic, a separate contract already covered by
`disbursement.quick,disbursement.jlg,disbursement.redis_inflight_lock_sim`).

No equivalent apiName-indexed coverage table exists for LOS→payments or LOS→actor at the time of
this pass — REPORT.md's scope was accounting only. `updateCustomerPan` (payments) and the 58
actor apiNames above have no coverage-verdict source to cite; this is stated as a gap, not
answered by inference.

## 3. Fragile response-parsing flags

Ranked by (blast radius if the producer response shape changes) × (how little guard stands
between the response and a dereference). All four are read directly from source in this pass —
not inherited from REPORT.md's prior findings, though #4 restates the incident REPORT.md already
named to keep the two documents consistent.

| # | file:line | pattern | why fragile | producer API this depends on |
|---|---|---|---|---|
| 1 | `los/processor/ProcessLoanAppIdForDisbursementAuditPreProcessor.java:46,48` | bare `Map` cast on a shared-context field, no null check before `putAll` | `Map<String,Object> chargeDetails = (Map<String, Object>) executionContext.get("charges_details");` then immediately `disbursementAuditDataMap.putAll(chargeDetails);` — `Map.putAll(null)` throws `NullPointerException`. `charges_details` is populated upstream by `GetPreDisbursementSummaryProcessor.getProcessingFee()` → `AccountingUtil.getProcessingFee()` (`los/util/AccountingUtil.java:361`) which calls `fetchLoanAccountChargeDetails`, but nothing in this class checks the key was actually set before reading it. Note the shape mismatch already flagged by REPORT.md: `PrepareDisburseLoanAPIRequestService.java:210` and `PrepareDisburseGroupLoanAPIRequestService.java:747` cast the **same context key** to `List<Map<String,Object>>`, while this file casts it to a bare `Map` — two callers disagree on the type of the same field | `fetchLoanAccountChargeDetails` (accounting) |
| 2 | `los/processor/disbursement/GenerateLARPreProcessor.java:76,80,95` | unguarded `for`-each over a response-derived `List` | `List<Map<String, Object>> childLoanAccountDetails = (List<Map<String, Object>>) getLoanAccountDetailsResp.get("child_loan_account_details");` is only gated on the outer response being non-empty and `status == SUCCESS` (lines 71-73) — nothing checks `child_loan_account_details` itself is present. It is passed straight into `prepareDataForLARDocument(childLoanAccountDetails)` (line 80), whose body is `for (Map<String, Object> childLoanAccountDetail : childLoanAccountDetails)` (line 95) — a `null` list throws `NullPointerException` on the group LAR generation path | `getLoanAccountDetails` (accounting, via `LoanAccountStatusEnquiryAPIUtil.callLoanStatusEnquiryAPI`) |
| 3 | `los/audit/report/GetLoanDemographicsHistoryProcessor.java:38-40` | unguarded `for`-each over `response.get("data")` | `List<Map<String, Object>> auditDataList = (List<Map<String, Object>>) response.get("data");` immediately followed by `for (Map<String, Object> hitObject : auditDataList)` with no null/empty check between them — same NPE shape as #2, on the audit-history report path | `getAuditEsDataByUserStory` (actor, via `ActorUtil.internalCallForActorApi`) |
| 4 | `los/processor/GetPdcGroupLoanDetailsProcessor.java:63-67` | double unguarded `Map` chain | `Map<String, Object> meetingCenterResponse = executionContext.getAPIResponse("getMeetingCenterDetails_response");` → `Map<String, Object> meetingCenterDetail = (Map<String, Object>) meetingCenterResponse.get(MEETING_CENTER_DETAILS);` → `String meetingCenterName = (String) meetingCenterDetail.get(NAME);` — three chained dereferences with zero null checks between them, on the PDC (post-dated cheque) group-loan flow. Contrast with the properly-guarded sibling at `ActorUtil.java:1108-1117`, which wraps the equivalent pattern in `if (MapUtils.isNotEmpty(apiResponse))` before the inner `.get()` | `getMeetingCenterDetails` (actor) |

**Not flagged, checked and found safe:**
- `los/processor/pan/CreateOrUpdatePanDetailsProcessor.java:124-144` (`updateCustomerPan`,
  payments) — `response == null` is checked before any field access, then `status` is validated
  against `"SUCCESS"` before the borrower record is updated. The one LOS→payments call site is
  also the best-guarded one in this survey.
- `los/util/ActorUtil.java:1108-1117` (`getStateDistrictVtcList`, actor) —
  `MapUtils.isNotEmpty(apiResponse)` guards the inner `.get("vtc_details")` cast.

## Counts

| | |
|---|---|
| Total LOS `callInternalAPI` call sites (all targets, incl. dms/masterdata/task/authorization/etc.) | 279 |
| Of those, targeting accounting / payments / actor | 132 (31 + 1 + 100 direct) |
| — accounting | 31 sites, 22 distinct apiNames |
| — payments | 1 site, 1 apiName |
| — actor | 100 direct + 8 indirect (via `ActorUtil.internalCallForActorApi`), 58 distinct apiNames |
| Fragile-flagged (verified by reading source, not heuristic-only) | 4 |
| Checked and found well-guarded | 2 |

## The single highest-value next action

**`los/processor/ProcessLoanAppIdForDisbursementAuditPreProcessor.java:46,48`** (finding #1). It
sits on the **disbursement audit path** — the same family as the original `charges_configured`
incident (`fetchLoanAccountChargeDetails` returning an empty/absent `charges_details` broke a
different caller that assumed non-empty). Two things make this the top pick over the other three
findings:

1. It is the **second, independently-discovered caller** of the exact API that already broke
   production once, and it disagrees on the response field's *type* with the two callers that
   already got the `List<Map<...>>` fix (`PrepareDisburseLoanAPIRequestService.java:210`,
   `PrepareDisburseGroupLoanAPIRequestService.java:747` use `List`; this one uses bare `Map`) —
   evidence that the earlier fix was not propagated to every consumer of the same field.
2. `fetchLoanAccountChargeDetails` is itself confirmed **UNCOVERED (no case)** (§2), so there is no
   registry case that would catch a regression here today — a producer-side change to
   `charges_details` shape or nullability would surface as an NPE in disbursement audit logging
   with no test in between.

Concretely: add a null-guard before `disbursementAuditDataMap.putAll(chargeDetails)` (and its
`insuranceDetails` / `loanDetails` neighbors on the same lines, which have the identical pattern),
and — since this document's brief is analysis, not LOS code changes — file the unification of
`charges_details`'s type across its three known consumers (bare `Map` here vs `List<Map<...>>` in
the two disbursement-prep services) as the concrete follow-up for whoever owns that contract.

## Caveats

- LOS is out of scope as a test target; nothing here proposes or implies adding LOS registry
  cases. The findings are about the **accounting/payments/actor contract surface** LOS happens to
  exercise.
- The 279→132 filter keeps only calls whose apiName resolved to accounting/payments/actor via
  `platform_api_map.jsonl`. 18 call sites had an apiName that did not resolve in that map (dynamic
  per-call-site names inside further-generic helpers, or literals not present in the 1955-API
  index) and were excluded rather than guessed into a service.
- "Response object read; downstream not individually traced" rows are honestly incomplete, not
  silently assumed safe — they were not walked far enough to classify, and are not counted in the
  fragile-flagged total.
- `los/processor/disbursement/DisburseLoanProcessor.java` / `DisburseGroupLoanProcessor.java`
  reach accounting via the **Kafka** `disburse_loan_api_*` topic (`DisburseLoanAPIUtil`), not
  `callInternalAPI` — out of this document's grep scope by construction, already covered by
  `.cursor/rules/los.mdc` and `.cursor/rules/events.mdc`'s disbursement sync contract section.
