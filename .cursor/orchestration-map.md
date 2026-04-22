# Orchestration map — auto-extracted index

**Generated:** 2026-04-10. **Scope:** all `**/deploy/application/orchestration/**/*.xml` under sliProd workspace.

## How to use this artifact

| Section | Contents |
|---------|----------|
| **Per-file tables** | Each `<Request name=...>` → processor bean names, nested `<API name=...>` calls, `<Control>` branch summary |
| **ExecutionContext keys** | **Not** fully inlined here — keys are set inside each `*Processor.java` / API response. Use **processor class name** → `rg 'getStringValue|put\(|putLocal' processor.java` |
| **Conditional branching** | `Control` rows: `regExp` / `mandatoryFieldValidator` wrappers use `${function_code}`, `${function_sub_code}`, etc. |

## Inventory

| Metric | Value |
|--------|------:|
| XML files | 60 |
| `<Request>` nodes (parseable) | 1915 |

## `novopay-mfi-los/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-mfi-los` 
**Root element:** `los`  
**Requests:** 485

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `aadhaarConsentUrl` | getConsentTemplateUrlForAadhaar | — | — |
| `addOrUpdateBorrowerIncomeDetails` | validateIncomeDetailsProcessor → addOrUpdateIncomeDetailsProcessor | — | regExp(${is_earning})=true |
| `addUpdateExpenseDetails` | addUpdateExpenseDetailsProcessor → updateLoanAppStepsStatusProcessor → resetCUMemberDetailsProcessor → dummyProcessor → expenseDetailsForAuditPreProcessor → constructRequestDataForApproval | — | regExp(${function_code})!CM_DASHBOARD; regExp(${function_code})=CM_DASHBOARD |
| `addUpdateHouseholdProfile` | addHouseholdProfileProcessor → updateHouseholdProfileProcessor → householdProfilePreProcessor → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `addUpdateOtherLoanForBorrower` | addUpdateOtherLoanForBorrowerProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `amlRiskProfileFile` | amlRiskProfileFileJobProcessor | — | — |
| `amlRiskProfileOutboundFile` | amlRiskProfileFileOutboundJobProcessor | — | — |
| `apyRegistration` | apyRegistrationProcessor | — | — |
| `bulkAllocatePolicyEligibleGroup` | bulkAllocatePolicyEligibleGroupProcessor | — | — |
| `bulkFileToSGCalculateBlendedRoiJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGCustomerAllocationJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGIrrJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGPaymentReinitiationJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGPolicyEligibleCustomersJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGReKycDetailsJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGRiskProfileJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGSalesPromocodeJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGShgCodeJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGUpdateInterestSubventionJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkSGToCalculateBlendedRoiJob` | bulkSGToCalculateBlendedRoiJobProcessor | — | — |
| `bulkSGToCustomerAllocationJob` | bulkSGToCustomerAllocationJobProcessor | — | — |
| `bulkSGToIrrJob` | bulkSGToIRRJobProcessor | — | — |
| `bulkSGToPaymentReinitiationJob` | bulkSGToPaymentReinitiationJobProcessor | — | — |
| `bulkSGToPolicyEligibleCustomersJob` | bulkSGToPolicyEligibleCustomersJobProcessor | — | — |
| `bulkSGToReKycDetailsJob` | bulkSGToReKycDetailsJobProcessor | — | — |
| `bulkSGToRiskProfileJob` | bulkSGToRiskProfileJobProcessor | — | — |
| `bulkSGToSalesPromocodeJob` | bulkSGToSalesPromocodeJobProcessor | — | — |
| `bulkSGToShgCodeJob` | bulkSGToShgCodeJobProcessor | — | — |
| `bulkSGToUpdateInterestSubventionJob` | bulkSGToUpdateInterestSubventionJobProcessor | — | — |
| `calculateBlendedInterestRate` | calculateBlendedInterestRateProcessor | — | regExp(${function_code})=BY_LAN |
| `calculateEvaluationScore` | calculateEvaluationScoreProcessor | — | regExp(${function_code})=CONDUCT_SHG |
| `checkBpmnProcessStatus` | checkBpmnProcessStatusProcessor | — | — |
| `checkDotAccountNeeded` | checkDotAccountNeededProcessor | — | — |
| `checkDotAccountVerificationRequired` | checkDotAccountVerificationRequiredProcessor | — | — |
| `checkFactivaDedupe` | factivaForBorrowerProcessor | — | — |
| `checkIfCustomerCreated` | checkIfCustomerCreatedProcessor | — | — |
| `checkIfGroupStpOrNot` | checkIfGroupStpOrNotProcessor | — | — |
| `checkIsENachRequired` | checkIsENachRequiredProcessor | — | — |
| `checkIsENachSuccessful` | checkIsENachSuccessfulProcessor | — | — |
| `checkMandateStatus` | checkMandateStatusProcessor | — | — |
| `checkMultiBureauStatus` | checkMultiBureauStatusProcessor | — | — |
| `checkNetOffEligibilityAndSimulateForeClosure` | checkNetOffEligibilityAndSimulateForeClosureProcessor | — | — |
| `checkPhysicalSignOpted` | checkPhysicalSignOptedProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `checkSignerStatus` | checkSignerStatusProcessor | — | — |
| `ckycInputDataBatch` | ckycInputDataBatchProcessor | — | — |
| `ckycRejectedDataBatch` | ckycRejectedDataBatchProcessor | — | — |
| `ckycSuccessDataBatch` | ckycSuccessDataBatchProcessor | — | — |
| `createAndCompleteTask` | createAndCompleteTaskProcessor → dummyProcessor → dummyProcessor → emailNotificationProcessor → sendSmsForEsignProcessor → constructRequestDataForApproval | setFoirDetailsForAudit | regExp(${is_hold_for_clarification})=true; regExp(${is_notification_required})=true; regExp(${is_send_for_approval})=true; regExp(${is_sms_required})=true; regExp(${screen_name})=ELIGIBILITY_SUMMARY|SEND_FOR_REAPPROVAL|ESIGN|CREDIT_UNDERWRITTING|TA_DASHBOARD|HOLD_FOR_CLARIFICATION |
| `createBorrower` | createBorrowerProcessor → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${borrower_type})=BORROWER; regExp(${function_code})!CURL; regExp(${function_code})=DEFAULT |
| `createEStamp` | updateEStampStatusProcessor → createEStampProcessor | — | — |
| `createOfflineDataDump` | createOfflineDataProcessor | — | — |
| `createOrUpdateActivityDetails` | createOrUpdateActivityDetailsProcessor → preProcessCreateOrUpdateActivityDataForAudit → constructRequestDataForApproval | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE|DELETE |
| `createOrUpdateApyDetails` | createOrUpdateApyDetailsProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${product_code})=INDL_LOAN; regExp(${product_code})=JLGDL|SHGDL |
| `createOrUpdateAssetsAndAmenities` | createOrUpdateAssetsAndAmenitiesProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → dummyProcessor → assetsAndAmenitiesPreProcessor → constructRequestDataForApproval | — | regExp(${function_code})=CM_DASHBOARD; regExp(${function_code})=DEFAULT|CONDUCT_BET|CONDUCT_PD|CM_DASHBOARD; regExp(${function_sub_code})=ASSETS_AND_AMENITIES; regExp(${function_sub_code})=MACHINERY_DETAILS |
| `createOrUpdateBorrowerCoborrowerDetails` | createOrUpdateBorrowerCoborrowerDetailsProcessor → createOrUpdateHouseholdDetailsProcessor → createOrUpdateInsuranceNomineeAndAppointeeDetailsProcessor | — | regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT |
| `createOrUpdateBorrowerDDE` | borrowerDDEDetailsProcessor → preProcessBorrowerDDEDataForAudit → getFinancialDetailsProcessor → saveFOIRAndEIRProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → co... | — | regExp(${loan_product_category})!LOAN_IND; regExp(${loan_product_category})!LOAN_SHG; regExp(${loan_product_category})=LOAN_IND |
| `createOrUpdateBorrowerDetails` | createOrUpdateBorrowerDetailsProcessor | — | — |
| `createOrUpdateBorrowerKycDetails` | dummyProcessor → preValidationForDuplicateLoanAppCreationProcessor → validateDmsDocumentsProcessor → validateCoBorrowerExist → createOrUpdateBorrowerKycDetailsProcessor → createOrUpdateInsurancePol... | — | regExp(${borrower_type})=BORROWER; regExp(${borrower_type})=CO_BORROWER; regExp(${borrower_type}_{function_sub_code})=BORROWER_UPDATE; regExp(${consent_type})=physical; regExp(${customer_kyc_document})=VOTER_ID; regExp(${function_code})!CM_DASHBOARD; regExp(${function_code})=CM_DASHBOARD; regExp(${function_code})=DEFAULT|BIOMETRIC|QR_CODE … (+26) |
| `createOrUpdateBorrowerStability` | createOrUpdateBorrowerStabilityProcessor | — | regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT |
| `createOrUpdateBulkActiveLoansAndOtherLoans` | validateCreateOrUpdateExistingLoanProcessor → createOrUpdateBulkActiveLoansAndOtherLoansProcessor → updatePosidexActiveLoansForBorrowerProcessor → loanApplicationRTRTaggingProcessor → uniqueLoanTag... | — | regExp(${function_code})!CM_DASHBOARD; regExp(${function_sub_code})!DELETE; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DELETE; regExp(${function_sub_code})=UPDATE_COMPLETE |
| `createOrUpdateBulkActivityDetails` | createOrUpdateBulkActivityListProcessor | — | — |
| `createOrUpdateBulkIncomeDetails` | createOrUpdateBulkIncomeDetailsProcessor → calculateAndUpdateDivergencePercentageProcessor → incomeDetailsRequestForAuditPreProcessor → updateLoanAppStepsStatusProcessor → dummyProcessor → construc... | — | regExp(${function_code})=CM_DASHBOARD; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE |
| `createOrUpdateCreditBureauReport` | createCreditBureauReportProcessor → updateCreditBureauReportProcessor | — | regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT |
| `createOrUpdateDSADetails` | createOrUpdateDSADetailsProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `createOrUpdateDocDispatchTask` | validateFlccDocDispPermission → createOrUpdateDocDispatchTaskProcessor → constructRequestDataForApproval | — | regExp(${doc_dispatch_task_created})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=REJECTED|SUBMIT|APPROVE |
| `createOrUpdateExistingLoan` | validateCreateOrUpdateExistingLoanProcessor → createOrUpdateExistingLoanProcessor → updatePosidexActiveLoansForBorrowerProcessor → loanApplicationRTRTaggingProcessor → uniqueLoanTaggingProcessor → ... | — | regExp(${function_code})!CM_DASHBOARD; regExp(${function_code})=CM_DASHBOARD; regExp(${function_sub_code})!DELETE; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DELETE; regExp(${function_sub_code})=UPDATE_COMPLETE; regExp(${is_update})=true … (+1) |
| `createOrUpdateExpenseDetails` | createOrUpdateExpenseDetailsProcessor → saveFOIRAndEIRProcessor → updateLoanAppStepsStatusProcessor → dummyProcessor → constructRequestDataForApproval | — | regExp(${function_code})=CM_DASHBOARD; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE |
| `createOrUpdateFamilyMemberDetails` | saveBureauConsentDetailsProcessor → resetFamilyMemberStepProcessor → createOrUpdateFamilyMemberDetailsProcessor → createOrUpdateInsurancePolicyDetailsProcessor → initiateServiceCallProcessor → rese... | — | regExp(${bureau_consent_type})=DIGITAL_CONSENT_W_OTP_VERIFICATION; regExp(${bureau_consent_type})=PHYSICAL_CONSENT_WO_OTP_VERIFICATION; regExp(${family_member_id})!0; regExp(${function_code})=CREATE; regExp(${function_code})=UPDATE; regExp(${function_sub_code})=CM_DASHBOARD; regExp(${is_earning})=true; regExp(${kyc_document_code})=DRIVING_LICENSE … (+7) |
| `createOrUpdateFinancialDetails` | incomeDetailsProcessor → expenseDetailsProcessor | — | regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT |
| `createOrUpdateFinancialDetailsSHG` | createOrUpdateFinancialDetailsSHG → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${function_code})!CM_DASHBOARD |
| `createOrUpdateGroup` | validateMeetingCenterProcessor → createOrUpdateGroupProcessor → getGroupTypeProcessor → updateGroupTypeProcessor → processPromoCodeRulesProcessor → updateEntityStatusProcessor → createOrUpdateGroup... | — | regExp(${function_sub_code})!DISCARD_GROUP; regExp(${function_sub_code})=ADD_MEMBER|REMOVE_MEMBER|UPDATE|DISCARD_GROUP; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|MANAGE_MEMBERS; regExp(${function_sub_code})=MANAGE_MEMBERS; regExp(${group_details_changed})=true; regExp(${group_status})=Group Pending For Loan; regExp(${group_type})! … (+2) |
| `createOrUpdateGroupFlcc` | populateGroupDetailsProcessor → createOrUpdateFlccProcessor → createFlccforMembersProcessor → updateFlccForMemberProcessor → updateFlccLoanAppStatusProcessor → dummyProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `createOrUpdateHouseholdProfile` | createHHBasicAmenitiesProcessor → createHHBasicDetailsProcessor → createHHPhysicalAssetsProcessor → updateHHBasicAmenitiesProcessor → updateHHBasicDetailsProcessor → updateHHPhysicalAssetsProcessor... | — | regExp(${function_code})!CM_DASHBOARD; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `createOrUpdateIncomeDetails` | createOrUpdateIncomeDetailsProcessor → calculateAndUpdateDivergencePercentageProcessor → incomeDetailsRequestForAuditPreProcessor → updateLoanAppStepsStatusProcessor → resetCUMemberDetailsProcessor... | — | regExp(${function_code})=CM_DASHBOARD; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE_HOUSEHOLD; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE_HOUSEHOLD |
| `createOrUpdateIncomeSurrogate` | createOrUpdateIncomeSurrogateProcessor → incomeSurrogateDetailsRequestPreProcessor → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${function_code})=DEFAULT|CONDUCT_BET|CONDUCT_PD|CM_DASHBOARD; regExp(${function_sub_code})=CREATE|UPDATE |
| `createOrUpdateInsuranceNomineeAndAppointeeDetails` | createOrUpdateInsuranceNomineeAndAppointeeDetailsProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${product_code})!INDL_LOAN; regExp(${product_code})=INDL_LOAN |
| `createOrUpdateLead` | createOrUpdateLeadProcessor | — | regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT |
| `createOrUpdateLoanApp` | validateCreditUnderwriterPermissionProcessor → createLoanAppProcessor → createOrUpdateInsurancePolicyDetailsProcessor → createOrUpdateInsurancePolicyDetailsProcessor → createOrUpdateInsurancePolicy... | — | regExp(${function_code})=CM_DASHBOARD; regExp(${function_code})=CONDUCT_BET; regExp(${function_code})=CONDUCT_BET|DEFAULT|ONBOARDING|CONDUCT_PD; regExp(${function_code})=DEFAULT|ONBOARDING; regExp(${function_code})=ONBOARDING|CONDUCT_BET|CONDUCT_PD; regExp(${function_code}_${function_sub_code})=CM_DASHBOARD_UPDATE; regExp(${function_sub_code})=UPDATE; regExp(${premium_update_required})=true |
| `createOrUpdateLoanAppConsent` | createOrUpdateLoanAppConsentProcessor → updateLoanAppStepsStatusProcessor → initiateServiceCallProcessor | — | regExp(${function_code})=DEFAULT|CONDUCT_BET|CONDUCT_PD; regExp(${function_code}_${borrower_type})=CONDUCT_PD_CO_BORROWER; regExp(${function_sub_code})=DEFAULT|CREATE|UPDATE |
| `createOrUpdateLoanAppPersonalDetails` | getBorrowerKycDocumentDetails → validateStateLevelDocumentConfiguration → createOrUpdateLoanAppPersonalDetailsProcessor → getNameMatchPercentageDetails → generateConsentThroughKafkaProcessor → upda... | — | regExp(${borrower_type})=CO_BORROWER; regExp(${do_end_step})=true; regExp(${function_code})=CONDUCT_BET|DEFAULT|ONBOARDING|CONDUCT_PD; regExp(${function_code})=ONBOARDING; regExp(${function_code}_${borrower_type})=ONBOARDING_CO_BORROWER; regExp(${is_borrower_has_pan})=true; regExp(${is_current_address_same_as_ovd}_${is_proof_of_current_address_same_as_poi}_${is_proof_of_current_address_same_as_voter_id})=false_false_false; regExp(${is_current_address_same_as_ovd}_${is_proof_of_current_address_same_as_voter_id}_${is_proof_of_current_address_same_as_poi})=false_false_false … (+6) |
| `createOrUpdateLoanUtilization` | createLoanUtilizationProcessor → preProcessCreateOrUpdateLoanUtilizationDataForAudit → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${function_sub_code})=CREATE|UPDATE |
| `createOrUpdateMappedQuestionnaire` | setScoreCapturedFlagProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → sendForApprovalCreateOrUpdateMappedQuestionnairePreProcessor → deleteDraftProcessor → dummyProcesso... | submitApplication | if(${score_captured})=false; if(${score_captured})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE … (+14) |
| `createOrUpdateMemberBetDetails` | createOrUpdateMemberBetDetailsProcessor → createOrUpdateMemberSHGDetailsProcessor → createOrUpdateMemberBetPreProcess → pslTaggingIndividualRulesProcessor → getGroupTypeProcessor → updateGroupTypeP... | — | regExp(${function_code})!CONDUCT_PD; regExp(${function_code})=CONDUCT_PD; regExp(${function_sub_code})!CONDUCT_SHG; regExp(${function_sub_code})!CREATE; regExp(${function_sub_code})=CONDUCT_SHG; regExp(${function_sub_code})=UPDATE|CONDUCT_SHG; regExp(${function_sub_code})=UPDATE|REMOVE_MEMBER; regExp(${group_type})! … (+2) |
| `createOrUpdatePanDetails` | CreateOrUpdatePanDetailsProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `createOrUpdateQuestionnaireMaster` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → sendForApprovalCreateOrUpdateQuestionnaireMasterPreProcessor → deleteDraftProcessor → dummyProcessor → createOrUpdateQuestionnaireM... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE|DELETE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+6) |
| `createOrUpdateReferences` | createOrUpdateReferencesProcessor → updateLoanAppStepsStatusProcessor → createOrUpdateReferencesProcessorAuditPreProcessor → constructRequestDataForApproval | — | regExp(${function_sub_code})=CREATE|UPDATE |
| `createOrUpdateTaxDetails` | createOrUpdateTaxDetailsProcessor | — | regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT |
| `createPaymentReinitiationChecker` | createPaymentReinitiationCheckerTaskProcessor | — | — |
| `createUpdateOpsTask` | validateOpsTaskProcessor → createUpdateOpsTaskProcessor → constructRequestDataForApproval | — | regExp(${function_code}_${function_sub_code})=UPDATE_DEFAULT |
| `cropSignature` | cropSignatureProcessor | — | — |
| `deleteFamilyMember` | deleteFamilyMemberProcessor | — | — |
| `deleteLoanAppOrGroupDetails` | deleteLoanAppOrGroupDetailsProcessor | — | — |
| `deleteMappedQuestionnaire` | getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → sendForApprovalDeleteMappedQuestionnairePreProcessor → deleteDraftProcessor → dummyProcessor → deleteMappedQuestionnaireProcessor →... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteOtherLoan` | deleteOtherLoanProcessor | — | — |
| `deleteQuestionnaireMaster` | getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → sendForApprovalDeleteQuestionnaireMasterPreProcessor → deleteDraftProcessor → dummyProcessor → deleteQuestionnaireMasterProcessor →... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `delinkApplication` | createOrUpdateMemberBetDetailsProcessor → updateMemberAvailingDetailsProcessor → updateMemberAvailingDetailsProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → updat... | — | regExp(${function_code})=CONDUCT_BET; regExp(${function_code})=DEFAULT; regExp(${is_dde_reject})=true; regExp(${step_code})=ELIGIBILITY_SUMMARY; regExp(${step_code})=HOUSEHOLD_INCOME_EXPENSES |
| `disburseLoanAudit` | disburseLoanAuditProcessor → constructRequestDataForApproval | — | — |
| `disburseLoanCallBack` | disburseLoanCallBackProcessor | — | — |
| `documentExtract` | documentExtractProcessor | — | — |
| `documentVerification` | documentVerificationProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `documentVerification` | documentVerificationProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `downloadCalculateBlendedRoiUploadedFile` | downloadCalculateBlendedRoiUploadedFileProcessor | — | — |
| `downloadCustomerAllocationUploadedFile` | downloadCustomerAllocationUploadedFileProcessor | — | — |
| `downloadIrrUploadedFile` | downloadIRRUploadedFileProcessor | — | — |
| `downloadPaymentReinitiationUploadedFile` | downloadPaymentReinitiationUploadedFileProcessor | — | — |
| `downloadPolicyEligibleCustomersUploadedFile` | downloadPolicyEligibleCustomersUploadedFileProcessor | — | — |
| `downloadReKycDetailsUploadedFile` | downloadReKycDetailsUploadedFileProcessor | — | — |
| `downloadRiskProfileUploadedFile` | downloadRiskProfileUploadedFileProcessor | — | — |
| `downloadSalesPromocodeUploadedFile` | downloadSalesPromocodeUploadedFileProcessor | — | — |
| `downloadShgCodeUploadedFile` | downloadShgCodeUploadedFileProcessor | — | — |
| `downloadUdyam` | triggerUdyamProcessing | — | regExp(${function_sub_code})=BATCH |
| `downloadUpdateInterestSubventionUploadedFile` | downloadUpdateInterestSubventionUploadedFileProcessor | — | — |
| `eSignInitiateRequest` | eSignRequestProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `esignPendingDocumentDetails` | getEsignPendingDocumentProcessor → getDocumentForGroup360Processor | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=GROUP_360 |
| `executeLOSPortfolioTransfer` | transferGroupTaskDetailsByVillageProcessor → transferLoanAppTaskDetailsByVillageProcessor → transferLoanApplicationsByVillageProcessor → transferGroupsByVillageProcessor → transferDraftBorrowersByV... | — | regExp(${transfer_type})=PRTFL_TRNSFR_EMPL |
| `executePostBureauServices` | postBureauServiceProcessor | — | — |
| `expireMandateRegistration` | expireMandateRegistrationProcessor | — | — |
| `fetchDocumentList` | fetchDocumentCategoryProcessor → fetchDocumentListProcessor | — | — |
| `fetchExtShgLoansByGroupId` | fetchExtShgLoansByGroupIdProcessor | — | — |
| `fetchPanDetailsForCustomers` | fetchPanDetailsForCustomersProcessor | — | — |
| `ftsAccountOpeningFormBatch` | ftsAccountOpeningFormBatchProcessor | — | — |
| `ftsAccountStatusResetToUploadBatch` | ftsAccountStatusResetToUploadBatchProcessor | — | — |
| `ftsKycStatusInquiry` | ftsKycStatusInquiryProcessor | — | — |
| `ftsRepushBatch` | ftsRepushBatchProcessor | — | — |
| `ftsResetToUploadBatch` | ftsResetToUploadBatchProcessor | — | — |
| `generateAPYAcknowledgementForm` | generateApyAcknowledgementFormProcessor | — | — |
| `generateConsentLoanDocumentPdf` | generateConsentLoanDocument | — | — |
| `generateCreditPromoCode` | processPromoCodeRulesProcessor | — | — |
| `generateESignDocuments` | createEsignDetailsProcessor → documentVerificationProcessor → generateSpecificLoanDocumentsProcessor → documentVerificationProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL; regExp(${is_regeneration})=true |
| `generateEkycOnePagerDocument` | generateEkycOnePagerDocumentProcessor | — | — |
| `generateGroupFileExtractJob` | groupFileExtractJobProcessor | — | — |
| `generateLarDocument` | generateLARPreProcessor → generateLARDocumentProcessor | — | regExp(${function_sub_code})=REGENERATE |
| `generateLoanApplicationFileExtractJob` | loanApplicationFileExtractJobProcessor | — | — |
| `generateLoanDocuments` | generateLoanDocumentsProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `generateMemberLevelROI` | processMemberLevelROIRulesProcessor | — | — |
| `generateOpsChecklistDocument` | generateOpsChecklistProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `generateOrRegenerateDocuments` | documentVerificationProcessor → generateSpecificLoanDocumentsProcessor | — | regExp(${function_code})!=COMBINED; regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL; regExp(${is_regeneration})=true |
| `generatePhysicalSignDocuments` | generatePhysicalSignDocumentsProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `generatePosidexReport` | posidexGroupLoanDetails → posidexAllActiveLoansProcessor → posidexSummaryProcessor → generatePosidexReportAtCmLevelProcessor | — | regExp(${function_sub_code})!CM_DASHBOARD; regExp(${function_sub_code})=CM_DASHBOARD; regExp(${is_posidex_triggered})=true |
| `generatePslType` | processPslTaggingRulesProcessor | — | — |
| `generatePslTypeIndividual` | pslTaggingIndividualRulesProcessor | — | — |
| `generateSpecificLoanDocuments` | generateSpecificLoanDocumentsProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `geoAuditActivity` | geoTrackingAuditProcessor | — | — |
| `geoAuditLogin` | constructRequestDataForApproval → geoTrackingAuditProcessor | — | — |
| `geoAuditLogout` | constructRequestDataForApproval → geoTrackingAuditProcessor | — | — |
| `getAPYDetails` | getMemberFatcaDetailsProcessor → getAPYDetailsProcessor | — | — |
| `getAadhaarNumberFromCustomToken` | getAadhaarNumberFromCustomTokenProcessor | — | — |
| `getAadhaarNumberFromRefList` | getAadhaarNumberFromRefListProcessor | — | — |
| `getAadhaarRedactedImage` | aadhaarRedactionProcessor | — | — |
| `getAadhaarRedactionServiceStatus` | getAadhaarRedactionServiceStatusProcessor | — | — |
| `getAadhaarReference` | getAadhaarReferenceProcessor | — | — |
| `getAadhaarReferenceNumber` | aadhaarVaultApiProcessor | — | — |
| `getAadhaarReferenceNumberFromAadhaarNumber` | getAadhaarReferenceNumberFromAadhaarNumberProcessor | — | — |
| `getAccountInfo` | getCasaAccountListProcessor → getHdfcAccountDetailsProcessor → getOtherBankAccountInfoProcessor → getGroupAccountDetailsForSHG | — | regExp(${function_code}_${function_sub_code})=DISBURSEMENT_HDFC_BANK; regExp(${function_code}_${function_sub_code})=DISBURSEMENT_OTHER_BANK; regExp(${function_code}_${function_sub_code})=DISBURSEMENT_SHGDL_HDFC_BANK |
| `getActiveLoanForBorrowerAndFamilyMember` | getActiveLoanForBorrowerAndFamilyMemberProcessor → getPosidexActiveLoansForBorrowerProcessor | — | — |
| `getActivityDetails` | getActivityDetailsProcessor | — | — |
| `getActivityDetailsFromAudit` | getActivityDetailsFromAuditProcessor | — | — |
| `getActivitySummaryList` | getActivitySummaryListProcessor | — | — |
| `getAddressByCoordinates` | getAddressByCoordinates | — | — |
| `getAssetAndAmenitiesDetails` | getAssetAndAmenitiesDetailsProcessor | — | — |
| `getAssetSummaryList` | getAssetSummaryListProcessor | — | — |
| `getAuditInfoByUseCase` | getAuditDataProcessor → generateAuditExcelProcessor | — | — |
| `getBETDetails` | getBETDetailsProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDL |
| `getBankAccountNumber` | getBankAccountNumberProcessor | — | — |
| `getBasicDetailsForGroupInBulk` | getBasicDetailsForGroupInBulkProcessor | — | — |
| `getBasicGroupDetails` | getBasicGroupDetailsProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=LOAN_ACC |
| `getBorrowerAccountDetails` | getDisbursementAccountDetailsProcessor → getRenewalDetailsForAccountDetailsProcessor → verifyIFSCCodeDetailsProcessor | — | regExp(${ifsc})!; regExp(${loan_type})=ETB |
| `getBorrowerAddressDetails` | getBorrowerAddressDetailsProcessor | — | — |
| `getBorrowerAddressDetailsHistory` | getBorrowerAddressDetailsHistoryProcessor | — | — |
| `getBorrowerCoBorrowerList` | getBorrowerCoBorrowerListProcessor | — | — |
| `getBorrowerContactDetailsByLan` | getBorrowerContactDetailsByLanProcessor | — | — |
| `getBorrowerDocumentList` | getBorrowerDocumentListProcessor | — | — |
| `getBorrowerFamilyDetailByCustomerId` | getBorrowerFamilyDetailByCustomerIdProcessor → getCoBorrowerPersonalDetailsProcessor | — | — |
| `getBorrowerGroupDetailsByCustomerId` | getBorrowerGroupDetailsByCustomerIdProcessor | — | — |
| `getBorrowerKycDetails` | getBorrowerKycDetailsProcessor | — | — |
| `getBorrowerLoanAccountList` | getBorrowerLoanAccountListProcessor | — | — |
| `getBorrowerLoanApplicationDetailsByCustomerId` | getBorrowerLoanApplicationDetailsByCustomerIdProcessor | — | — |
| `getBorrowerNameMatchPercentage` | getNameMatchPercentageDetails | — | — |
| `getBorrowerNonEligibleReason` | getBorrowerNonEligibleReasonByLoanAppIdsProcessor | — | — |
| `getBorrowerPersonalDetailsByCustomerId` | getBorrowerPersonalDetailsByCustomerIdProcessor → getBorrowerFamilyDetailByCustomerIdProcessor → getCustomerOccupationDetailsProcessor → getCoBorrowerPersonalDetailsProcessor | — | regExp(${function_sub_code})=MOBILE |
| `getBorrowerRelationships` | getBorrowerRelationshipsProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT |
| `getBorrowerStability` | getBorrowerStabilityProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT |
| `getBulkQuestionnaires` | getBulkQuestionnairesProcessor | — | — |
| `getBureauDetails` | getBureauDetailsProcessor | — | — |
| `getCAMReportDetails` | getCAMReportDetailsProcessor → getCAMReportDmsCodeDetailsProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL; regExp(${skip_cam_report_generation})!true; regExp(${skip_cam_report_generation})=true |
| `getCMDetails` | getCMDetailsProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `getCUForwardedNotes` | getCUForwardedNotesProcessor | — | — |
| `getCasaAccountList` | getCasaAccountListProcessor | — | — |
| `getClarificationRequiredDocuments` | getClarificationRequiredDocumentsProcessor | — | — |
| `getCoListMappedToSoBranch` | getCoListMappedToSoBranchProcessor | — | — |
| `getCommunicationAddress` | getCommunicationAddressProcessor | — | — |
| `getCreditPromocode` | getCreditPromocodeListProcessor | — | — |
| `getCustomerDocumentDetails` | getCustomerDocumentDetailsProcessor | — | — |
| `getCustomerDocumentHistory` | getCustomerDocumentHistoryProcessor | — | — |
| `getCustomerEsignDetails` | getCustomerEsignDetailsProcessor | — | — |
| `getCustomerOccupationDetails` | getCustomerOccupationDetailsProcessor | — | — |
| `getCustomerOccupationHistory` | getCustomerOccupationHistoryProcessor | — | — |
| `getDDEBorrowerAndSpouseDetails` | getDDEBorrowerAndSpouseDetailsProcessor | — | regExp(${function_sub_code}_${function_code})=SUBMIT_DEFAULT |
| `getDDEBorrowerDetails` | getDDEBorrowerDetailsProcessor → getInsuranceNomineeAndAppointeeDetailsProcessor → getPolicyEligibleDDEBorrowerDetailsProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT|DEFAULT_LOAN_APP_360; regExp(${loan_type})=ETB |
| `getDDEQuestionnaire` | getDDEQuestionnaireProcessor → getMappedQuestionListForMultiActivityProcessor | — | — |
| `getDSADetails` | getDSADetailsProcessor | — | — |
| `getDashBoardCount` | getDashBoardCountProcessor | — | — |
| `getDecisionHistory` | getDecisionHistoryProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `getDeviatedRules` | getDeviatedRulesProcessor | — | regExp(${function_sub_code})=DEFAULT|LOAN_APPLICATION|ALL_LOANS; regExp(${function_sub_code})=GROUP |
| `getDocumentGenerationStatus` | getDocumentGenerationStatusProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `getDocumentGenerationStatus` | getDocumentGenerationStatusProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `getDotAccountActivationStatus` | getDotAccountActivationStatusProcessor | — | — |
| `getDotAccountDetails` | getDotAccountDetailsProcessor | — | — |
| `getDotAccountDocumentDetails` | getDotAccountDocumentDetailsProcessor | — | — |
| `getEStampPaper` | getEStampPaperProcessor | — | — |
| `getEStampStatus` | getEStampStautsProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `getEkycBioAuthDetails` | getEkycBioAuthDetailsProcessor | — | regExp(${doc_type})=AADHAAR_NUMBER; regExp(${doc_type})=AADHAAR_VIRTUAL_ID |
| `getEligibilityFlags` | checkGroupFatcaApplicableProcessor → secondaryCasaApplicableProcessor | — | — |
| `getEligibilitySummaryDetails` | getEligibilitySummaryDetailsProcessor | — | — |
| `getEligibilitySummaryReport` | getCreditBureauReportProcessor → getPosidexReportProcessor | — | regExp(${function_sub_code})=CREDIT_BUREAU; regExp(${function_sub_code})=POSIDEX |
| `getEmployeeActivities` | getEmployeeActivitiesProcessor | — | — |
| `getEmployeeActivityHistory` | getEmployeeActivityHistoryProcessor | — | — |
| `getEmployeeCurrentDetails` | getEmployeeCurrentDetailsProcessor | — | — |
| `getEmployeeLocationHistory` | getEmployeeLocationHistoryProcessor | — | — |
| `getEmployeeTravelHistory` | getEmployeeTravelHistoryProcessor | — | — |
| `getEsignDetails` | getEsignDetailsProcessor | — | — |
| `getEsignInvitationLink` | getEsignInvitationLinkProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `getEsignPendingDocumentDetailsForIndividual` | getEsignPendingDocumentDetailsForIndividualProcessor | — | regExp(${function_sub_code})=E_SIGN|PHYSICAL_SIGN |
| `getExistingLoans` | getExistingLoansProcessor | — | — |
| `getExpectedDisbursementDate` | getExpectedDisbursementDateProcessor | — | — |
| `getExpenseDetails` | getExpenseDetailsProcessor | — | — |
| `getFamilyMemberDetailsByRelationship` | getFamilyMemberDetailsByRelationshipProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getFamilyMembers` | getFamilyMembersProcessor | — | — |
| `getFatcaDetails` | getFatcaDetailsProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT |
| `getFinancialDetails` | getFinancialDetailsProcessor → createOrUpdateInsurancePolicyDetailsProcessor → createOrUpdateInsurancePolicyDetailsProcessor → createOrUpdateInsurancePolicyDetailsProcessor → createOrUpdateInsuranc... | — | regExp(${expenses_status})=COMPLETED; regExp(${function_code})=CM_DASHBOARD; regExp(${premium_update_required})=true |
| `getFinancialDetailsSHG` | getFinancialDetailsSHGProcessor | — | — |
| `getFirstRepaymentDate` | getFirstRepaymentDateProcessor | — | — |
| `getGroupBasicDetails` | getGroupDetailsProcessor → getGroupAdditionalDetails | — | regExp(${function_code})=GROUP_360 |
| `getGroupCountUnderMeetingCenter` | getGroupCountProcessor | — | regExp(${function_code})=DEFAULT |
| `getGroupDetails` | getGroupDetailsProcessor → getGroupEligibilityRulesDetails | — | regExp(${function_sub_code})!GROUP_ID_LIST; regExp(${function_sub_code})=GROUP_ID_LIST |
| `getGroupDocuments` | getGroupDocumentsProcessor | — | — |
| `getGroupDotAccountDetails` | getGroupDotAccountDetailsProcessor | — | — |
| `getGroupFlccDetails` | populateGroupDetailsProcessor → populateFlccDetailsForGroupProcessor → getGroupMemberDetailsProcessor → getGroupFlccDetailsProcessor | — | — |
| `getGroupInfo` | getGroupInfoProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getGroupList` | getGroupListProcessor | — | regExp(${function_code}_${function_sub_code})=DEFAULT_DEFAULT; regExp(${function_sub_code})=FILTER; regExp(${function_sub_code})=SEARCH |
| `getGroupListByEmployeeId` | getGroupListByEmployeeIdProcessor | — | — |
| `getGroupListByMeetingCenterId` | getGroupListByMeetingCenterIdProcessor | — | — |
| `getGroupLoanDetails` | getGroupLoanApplicationDetailsProcessor → getGroupLoanDetailsProcessor → getGroupAndSubLoanDetailsProcessor | — | — |
| `getGroupMemberBasicDetails` | getGroupMemberBasicDetailsProcessor | — | — |
| `getGroupMemberDetails` | getGroupCustomerDetailsProcessor | — | — |
| `getGroupMembers` | getGroupMembersDetailsProcessor | — | — |
| `getGroupMembersDetailsForBet` | getGroupMembersDetailsForBetProcessor | — | — |
| `getGroupMembersDetailsForFatca` | getGroupMembersDetailsForFatcaProcessor | — | — |
| `getGroupMembersDetailsForPdc` | getGroupMembersDetailsForBetProcessor → getGroupMembersDetailsForPdcProcessor → validateGroupMembersAvailingToNonAvailingProcessor | — | regExp(${loan_product_code})=SHGDL |
| `getGroupMembersPremiumDetails` | getGroupMembersPremiumDetailsProcessor | — | — |
| `getGroupMitigants` | getGroupMitigantsProcessor | — | — |
| `getGroupRenewalDetails` | getGroupRenewalDetailsProcessor | — | — |
| `getGroupSavingAccountDetails` | getGroupSavingAccountDetailsProcessor | — | — |
| `getGroupStepsStatus` | getGroupStepsStatusProcessor | — | — |
| `getGroupType` | getGroupTypeProcessor | — | regExp(${function_sub_code})=BY_GROUP_ID; regExp(${function_sub_code})=BY_LOAN_APP_IDS |
| `getHdfcAccountInfo` | getHdfcAccountInfoProcessor | — | — |
| `getHouseholdProfileByLoanAppId` | fetchHHCustomerProfileProcessor | — | — |
| `getHouseholdProfileDetails` | getHouseholdProfileDetailsProcessor | — | — |
| `getHouseholdTaskStatus` | getHouseholdTaskStatusProcessor → saveFOIRAndEIRProcessor → saveFOIRAndEIRProcessor | — | regExp(${expenses_status}_${income_status}_${stage})=COMPLETED_COMPLETED_ONBOARDING; regExp(${stage})=CONDUCT_BET|CONDUCT_PD |
| `getIncomeDetails` | getIncomeDetailsProcessor | — | — |
| `getIncomeSurrogateDetails` | getIncomeSurrogateDetailsProcessor | — | — |
| `getIndvCustomerOccupationDetails` | getIndvCustomerOccupationDetailsProcessor | — | — |
| `getIndvCustomerOccupationHistory` | getIndvCustomerOccupationHistoryProcessor | — | — |
| `getInsuranceNomineeAndAppointeeDetails` | getInsuranceNomineeAndAppointeeDetailsProcessor | — | — |
| `getInsurancePremium` | getInsurancePremiumProcessor → getCalculatePremiumProcessor | — | regExp(${function_sub_code})=CALCULATE_PREMIUM; regExp(${function_sub_code})=DEFAULT |
| `getLeadsByEmployee` | getLeadsListProcessor | — | — |
| `getListOfVtcByGroupId` | getListOfVtcByGroupProcessor | — | — |
| `getLoanAmountDetails` | getLoanAmountDetailsProcessor | — | — |
| `getLoanAppCUDetails` | validateCreditUnderwriterPermissionProcessor → getLoanAppDetailsProcessor → getLoanAppCUDetailsProcessor | — | — |
| `getLoanAppCountForOffice` | getLoanAppCountForOfficeProcessor | — | — |
| `getLoanAppDetails` | getLoanAppDetailsProcessor | — | — |
| `getLoanAppList` | getLoanAppListProcessor | — | — |
| `getLoanAppQuestionnaireResponse` | getLoanAppQuestionnaireResponseProcessor | — | — |
| `getLoanAppStatus` | getLoanAppStatusProcessor | — | — |
| `getLoanAppStepsStatus` | getLoanAppStepsStatusProcessor | — | — |
| `getLoanApplicationInfo` | getLoanApplicationInfoProcessor | — | — |
| `getLoanApplicationList` | getLoanApplicationListProcessor | — | — |
| `getLoanApplicationSummary` | getLoanApplicationSummaryProcessor | — | — |
| `getLoanAppsForPslTag` | getLoanAppsForPslTagProcessor | — | — |
| `getLoanDemographicsHistory` | getLoanDemographicsHistoryProcessor | — | — |
| `getLoanDocuments` | getLoanDocumentsProcessor | — | — |
| `getLoanDocumentsByDocumentCategory` | getLoanDocumentsByDocumentCategoryProcessor | — | — |
| `getLoanProductsUsedByVillageIds` | getLoanProductsUsedByVillageIdsProcessor | — | — |
| `getLoanStage` | getLoanStageProcessor | — | — |
| `getLoanUtilizationDetails` | getLoanUtilizationDetailsProcessor | — | — |
| `getMappedQuestionnaire` | getMappedQuestionListForMultiActivityProcessor | — | regExp(${function_sub_code})=ALL_QUESTIONS; regExp(${function_sub_code})=DEFAULT |
| `getMappedQuestionnaireList` | getMappedQuestionnaireListProcessor | — | — |
| `getMeetingCenterList` | getMeetingCenterListProcessor | — | — |
| `getMemberBetDetails` | getMemberBetDetailsProcessor | — | — |
| `getMemberFatcaDetails` | getMemberFatcaDetailsProcessor | — | — |
| `getMemberHouseholdDetails` | getMemberHouseholdDetailsProcessor → getIncomeDetailsProcessor | — | — |
| `getMemberPDCDetails` | getMemberPDCDetailsProcessor → getPreDisbursementSummaryProcessor | — | — |
| `getMitigantsHistory` | getMitigantsHistoryProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `getMitigantsIndividualDetails` | getMitigantsIndividualProcessor | — | — |
| `getMultiBureauReports` | getMultiBureauReportsProcessor | — | — |
| `getMultiEmployeeActivityHistory` | getMultiEmployeeActivityHistoryProcessor | — | — |
| `getNameMatchPercentage` | getNameMatchPercentageProcessor | — | — |
| `getNetOffEligibleFlag` | getNetOffEligibleFlagProcessor | — | — |
| `getNoteCodeHistory` | getNoteCodeHistoryProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `getOfflineDetails` | getOfflineDetailsProcessor | — | regExp(${function_code})!ETB; regExp(${function_code})=ETB |
| `getOpsRejectedReasonHistory` | getOpsRejectedReasonHistoryProcessor | — | — |
| `getOriginateLoanCount` | getLeadsListProcessor → getOriginateLoanCountProcessor | — | — |
| `getOriginationCardsList` | getOriginationCardsListProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT |
| `getOverdueDetails` | getOverdueDetailsProcessor | — | — |
| `getPanVerificationDetails` | getPanVerificationDetailsProcessor → dummyProcessor | — | — |
| `getPdcGroupLoanDetails` | calculateGroupProcessingFeeProcessor → getPdcGroupLoanDetailsProcessor | — | — |
| `getPersonalDetailsHistory` | getPersonalDetailsHistoryProcessor | — | — |
| `getPhysicalSignDocumentDetails` | getPhysicalSignDocumentDetailsProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `getPosidexStatus` | getPosidexStatusProcessor | — | — |
| `getPreDisbursementSummary` | getPreDisbursementSummaryProcessor | — | — |
| `getProcessInstanceId` | getInstanceIdByLoanAppIdProcessor | — | — |
| `getQdeDetails` | getQdeDetailsProcessor | — | regExp(${function_sub_code})=ETB; regExp(${function_sub_code})=NTB |
| `getQuestionnaireMaster` | getQuestionnaireMasterProcessor | — | regExp(${function_sub_code})=ACTIVE; regExp(${function_sub_code})=DEFAULT |
| `getQuestionnaireMasterList` | getQuestionnaireMasterListProcessor | — | — |
| `getQuestionnaireResponse` | getQuestionnaireResponseProcessor | — | — |
| `getReferencesDetails` | getReferencesDetailsProcessor | — | — |
| `getRejectedCustomers` | getRejectedCustomersProcessor | — | — |
| `getRenewalGroups` | getRenewalGroupsProcessor | — | — |
| `getRenewalSummaryCount` | getRenewalSummaryCountProcessor | — | — |
| `getRenewalSummaryCountForIndividual` | getRenewalSummaryCountForIndividualProcessor | — | — |
| `getRenewalSummaryList` | getRenewalSummaryListProcessor | — | — |
| `getRenewalSummaryListForIndividual` | getRenewalSummaryListForIndividualProcessor | — | — |
| `getSalesPromocodeDetailsForSHG` | getSalesPromocodeDetailsForSHGProcessor | — | — |
| `getScheduleBetTaskDetails` | getBetTaskDetailsProcessor → getBetAdditionalDetailsProcessor | — | — |
| `getServiceStatus` | getServiceStatusProcessor → deleteDuplicateServicesProcessor | — | regExp(${function_sub_code})!AADHAAR_REDACTION; regExp(${is_delete_required})=true |
| `getShgCreditPromocodes` | getShgCreditPromocodesProcessor | — | — |
| `getSignDetailsForGroup` | populateGroupDetailsProcessor → getGroupMemberDetailsProcessor | — | — |
| `getSignDetailsForGroupMember` | getSignDetailsForGroupMemberProcessor | — | — |
| `getStatewiseDocumentConfig` | getStatewiseDocumentConfigProcessor | — | — |
| `getTaskDataFromLos` | getTaskDataFromLosProcessor | — | — |
| `getTaskForEtbTaskIds` | getTaskForEtbTaskIdsProcessor | — | — |
| `getTatOfGroupAndLoanAppStage` | getTatOfGroupAndLoanAppStageProcessor | — | — |
| `getTimeSlotsBasedOnUser` | getTimeSlotsBasedOnUserProcessor | — | — |
| `getUnassignedMembersList` | unassignedMembersListProcessor → similarMembersProcessor | — | regExp(${function_code})=ETB; regExp(${function_code})=ETB_MEMBERS_LIST; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT|SEARCH; regExp(${function_sub_code})=FILTER; regExp(${function_sub_code})=SEARCH |
| `getVillageLOSPortfolioSummary` | getVillageLOSPortfolioSummaryProcessor | — | — |
| `getWIPApplication` | getLoanAppIdByCenterIdSetProcessor → getLoanAppIdByEmpIdAndOfficesProcessor | — | regExp(${function_sub_code})=BY_EMP_OFFICES; regExp(${function_sub_code})=DEFAULT |
| `getZippedDocumentDetails` | getZippedDocumentDetailsProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `impsPartnerValidation` | impsPartnerValidationProcessor | — | regExp(${beneficiary_bank})=HDFC_BANK; regExp(${beneficiary_bank})=OTHER_BANK; regExp(${borrower_has_bank_account})=1; regExp(${function_code})!GROUP_CASA; regExp(${function_code})=GROUP_CASA; regExp(${function_sub_code}_${beneficiary_bank})=DEFAULT_OTHER_BANK |
| `initiateForeClosure` | initiateForeClosureProcessor | — | — |
| `isAPYApplicable` | checkAPYApplicableProcessor | — | — |
| `loanAppRefProcessDetails` | loanAppRefProcessProcessor | — | — |
| `moveGroupLoans` | moveGroupLoansProcessor | — | — |
| `offlineTest` | createOfflineDataTestProcessor → createEtbOfflineDataTestProcessor | — | regExp(${function_code})!ETB; regExp(${function_code})=ETB |
| `outboundInitiateFinnoneForeclosureJob` | triggerOutboundInitiateFinnoneForeclosureJobProcessor | — | — |
| `panValidation` | panValidationsProcessor | — | — |
| `paymentReinitiationMakerBatch` | paymentReinitiationMakerBatchProcessor | — | — |
| `pennyDrop` | pennyDropProcessor → accountStatusCheckProcessor → submitAccountDetailsProcessor → saveGroupCasaAccountProcessor → saveGroupCasaAccountProcessor | — | regExp(${function_code}_${beneficiary_bank})=DEFAULT_OTHER_BANK; regExp(${function_code}_${beneficiary_bank})=DEFAULT_OTHER_BANK|GROUP_CASA_OTHER_BANK; regExp(${function_code}_${beneficiary_bank})=GROUP_CASA_OTHER_BANK; regExp(${function_sub_code})!MANUAL_DISBURSEMENT; regExp(${response_status})!FAIL; regExp(${skip_pennydrop})!true; regExp(${skip_pennydrop})=true … (+1) |
| `performDotAccountActivation` | performDotAccountActivationProcessor → constructRequestDataForApproval | — | — |
| `performInternalMobileDedupe` | checkCustomerMobileDedupeProcessor | — | — |
| `performKycDedupe` | performKycDedupeProcessor → internalDedupeServiceShg | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=SHGDL |
| `performLoanAppTagging` | familyMemberDedupeCheckProcessor → loanPSLTaggingProcessor → loanMFITaggingProcessor → updateLoanAppStepsStatusProcessor | — | regExp(${function_code})=CONDUCT_BET |
| `posidexDedupe` | posidexDedupeProcessor | — | — |
| `posidexFinnoneBatch` | posidexFinnoneBatchProcessor | — | — |
| `posidexInput` | posidexInputProcessor | — | — |
| `posidexOutput` | posidexOutputProcessor | — | — |
| `posidexPublish` | posidexPublishProcessor | — | — |
| `posidexService` | posidexInputProcessor → posidexPublishProcessor → posidexOutputProcessor | — | — |
| `postCreditUnderwritingAction` | saveGrandMonthlyProfitProcessor → loanAppPslProcessor → updateWeakerSectionDetailsProcessor | — | regExp(${function_code})=INDIVIDUAL |
| `processAllEligibilityRules` | processAllEligibilityRulesProcessor → dummyProcessor → getGroupTypeProcessor → updateGroupTypeProcessor → processPromoCodeRulesProcessor | — | regExp(${group_type})!; regExp(${responseCode})!LOS-5066; regExp(${rule_stage})=ALL_GROUP |
| `processBetEligibilityRules` | processBetEligibilityRulesProcessor → dummyProcessor | — | regExp(${responseCode})!LOS-5066 |
| `processCUEligibilityRules` | processCUEligibilityRulesProcessor | — | — |
| `processEligibilityRules` | mapRuleStageProcessor → processRuleEngineRulesProcessor → dummyProcessor → dummyProcessor → getGroupTypeProcessor → updateGroupTypeProcessor → processPromoCodeRulesProcessor | — | regExp(${group_type})!; regExp(${responseCode})!LOS-5066; regExp(${rule_stage})!CU_GROUP; regExp(${rule_stage})!CU_RERUN_GROUP; regExp(${rule_stage})!GROUP; regExp(${rule_stage})!GROUP_NOTE_CODE; regExp(${rule_stage})!NOTE_CODE; regExp(${rule_stage})=CU_RERUN_GROUP … (+3) |
| `processEligibilitySummaryRules` | addBorrowerProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → processEligibilitySummaryRulesProcessor | — | regExp(${borrower_type})=BORROWER; regExp(${borrower_type})=CO_BORROWER; regExp(${function_code})!CM_DASHBOARD; regExp(${function_code})=CONDUCT_PD; regExp(${function_code})=DEFAULT|ELIGIBILITY_SUMMARY |
| `processGroupFormationEligibilityRules` | processGroupFormationEligibilityRulesProcessor → dummyProcessor | — | regExp(${responseCode})!LOS-5066 |
| `processLoanAppIdForDisbursementAfterPDC` | processLoanAppIdForDisbursementAfterPDCProcessor → processLoanAppIdForDisbursementAuditPreProcessor → constructRequestDataForApproval | — | regExp(${loan_type})=INDIVIDUAL |
| `purgeOldPolicyDataJob` | purgeOldPolicyDataJobProcessor | — | regExp(${function_sub_code})=BATCH |
| `pushAuditEvent` | pushAuditEventProcessor → constructRequestDataForApproval | — | — |
| `rejectBetTask` | getBetTaskDetailsProcessor → rejectBetTaskProcessor → acceptBetRejectPreProcessAuditData → constructRequestDataForApproval | — | regExp(${reject_reason})=OTHERS |
| `rejectBorrower` | rejectBorrowerProcessor | — | — |
| `rejectCoBorrower` | rejectCoBorrowerProcessor | — | — |
| `rejectExpiredGroupCasaTask` | repaymentGroupCasaTaskProcessor → rejectExpiredRepaymentGroupCasaTaskProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `rejectGroup` | rejectGroupProcessor → checkNetOffEligibilityAndUpdateStatusProcessor | — | — |
| `rejectGroup` | constructRequestDataForApproval → rejectGroupProcessor | — | — |
| `rejectGroupForSignatoryNotInterested` | rejectGroupForSignatoryNotInterestedProcessor | — | — |
| `rejectLoanApplication` | rejectLoanApplicationProcessor → checkNetOffEligibilityAndUpdateStatusProcessor → constructRequestDataForApproval | — | — |
| `rejectOrCancelGroup` | validateRejectCaseForScStProcessor → rejectCancelGroupProcessor | — | — |
| `reopenClosedLOSTask` | reopenClosedGroupTaskProcessor → reopenClosedLoanAppTaskProcessor | — | regExp(${entity_type})=GROUP; regExp(${entity_type})=LOAN_APP |
| `repaymentGroupCASAValidation` | casaAccountValidationProcessor → saveRepaymentCasaAccountProcessor → constructRequestDataForApproval | — | regExp(${group_has_hdfc_account})=true; regExp(${save_account_details})=true; regExp(${sub_use_case})=REPAYMENT_GROUP_CASA_ACCOUNT|VERIFY_CASA |
| `retryMemberBureau` | triggerMemberMultiBureauRequestProcessor | — | — |
| `retryMemberFactiva` | triggerMemberFactivaProcessor | — | — |
| `retryMemberPosidex` | triggerMemberPosidexProcessor | — | — |
| `retryServiceCall` | retryServiceCallProcessor | — | — |
| `rollbackLOSPortfolioTransfer` | rollbackLOSPortfolioTransferProcessor | — | — |
| `saveDDEQuestionnaireResponse` | saveDDEQuestionnaireResponseProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${function_sub_code})!DDE; regExp(${function_sub_code})=DDE; regExp(${product_code})!INDL_LOAN; regExp(${product_code})=INDL_LOAN |
| `saveDeclaration` | saveDeclarationProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → initiateServiceCallProcessor → updateLoanAppStatusProcessor | — | regExp(${borrower_type})=CO_BORROWER; regExp(${function_code})=CONDUCT_BET|DEFAULT|ONBOARDING|CONDUCT_PD; regExp(${function_code})=DEFAULT|ONBOARDING; regExp(${function_code})=ONBOARDING; regExp(${function_code}_${borrower_type})=ONBOARDING_CO_BORROWER; regExp(${requested_stage})!EDIT_BORROWER |
| `saveDocumentClarificationDetails` | saveDocumentClarificationDetailsProcessor → clarificationDocDetailsRequestPreProcessor → constructRequestDataForApproval | — | — |
| `saveEmployeeAllocationDetails` | saveEmployeeAllocationDetailsProcessor | — | — |
| `saveEsignFailureReason` | saveEsignFailureReasonProcessor | — | — |
| `saveEsignStatusProcess` | saveESignStatusProcessor | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL |
| `saveFOIRAndEIR` | saveFOIRAndEIRProcessor | — | — |
| `saveLoanCycle` | saveCycleCountProcessor | — | — |
| `saveMandateStatus` | saveMandateStatusProcessor → constructRequestDataForApproval | — | regExp(${is_audit_required})=TRUE |
| `saveMemberFatcaDetails` | saveMemberFatcaDetailsProcessor | — | — |
| `saveMultiBureauResponse` | saveMultiBureauResponseProcessor → calculateAndUpdateDivergencePercentageProcessor | — | — |
| `saveNoteCodes` | saveNoteCodesProcessor | — | — |
| `savePdcMemberDetails` | createOrUpdateFlccGroupMembers → validateGroupMembersAvailingToNonAvailingProcessor → removeExistingESignEntriesProcessor → uploadSliTopUpLetterProcessor → conductPDCDetailsForAuditPreProcessor → c... | — | regExp(${is_group_members_non_availed})=true; regExp(${loan_product_code})=SHGDL |
| `savePhysicalSignDocument` | savePhysicalSignDocumentProcessor → physicalSignDocumentPreProcessor → constructRequestDataForApproval | — | regExp(${doc_category})=INDIVIDUAL_BORROWER|INDIVIDUAL_COBORROWER|INDIVIDUAL_SPOUSE|INDIVIDUAL_COBORROWER_SPOUSE |
| `savePhysicalSignDocumentAsBulk` | savePhysicalSignDocumentAsBulkProcessor | — | — |
| `saveQuestionnaireResponse` | saveQuestionnaireResponseProcessor → updateLoanAppStepsStatusProcessor → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval → updateLoanAppStepsStatusProcessor → updateGroupStepsSt... | — | regExp(${function_code})!RECORD_KEEPING|SHG_RATING_EVALUATION|SHG_CM_DASHBOARD; regExp(${function_code})=RECORD_KEEPING; regExp(${function_code})=SHG_RATING_EVALUATION; regExp(${function_sub_code})!DDE; regExp(${function_sub_code})=DDE; regExp(${product_code})!INDL_LOAN; regExp(${product_code})=INDL_LOAN … (+1) |
| `saveSignerCallBackStatus` | saveSignerCallBackStatusProcessor → constructRequestDataForApproval | — | — |
| `saveStageCompletion` | saveStageCompletionProcessor | — | — |
| `sendReApprovalLoanAmount` | sendReApprovalLoanAmountProcessor → saveSendForReApprovalAmountHistoryProcessor | — | — |
| `sendReKycMessageJob` | sendReKycMessageJobProcessor | — | — |
| `setFoirDetailsForAudit` | populateFoirDetailsForAudit → constructRequestDataForApproval | — | regExp(${screen_name})=INCOME_AND_EXPENSES|CONDUCT_PD |
| `signatureExtract` | extractSignatureProcessor | — | — |
| `submitAcceptBetTask` | getBetTaskDetailsProcessor → submitAcceptBetTaskProcessor → acceptBetPreProcessAuditData → createOrUpdateMemberBetDetailsProcessor → constructRequestDataForApproval → closeLatestTaskProcessor → clo... | — | regExp(${close_task_flag})=true; regExp(${close_task_flag}_${entity_type})=true_GROUP; regExp(${close_task_flag}_${entity_type})=true_LOAN_APP; regExp(${function_sub_code})=CREATE|DEFAULT; regExp(${revert_flag})=true |
| `submitAccountDetails` | addBorrowerProcessor → accountStatusInquiryProcessor → accountStatusCheckProcessor → nameValidationCheckProcessor → dummyProcessor → submitAccountDetailsProcessor → bulkSubmitAccountDetailsProcesso... | — | regExp(${beneficiary_bank})=HDFC_BANK; regExp(${beneficiary_bank})=OTHER_BANK; regExp(${beneficiary_bank}_${account_purpose})!OTHER_BANK_DISBURSEMENT; regExp(${beneficiary_bank}_${account_purpose})=HDFC_BANK_REPAYMENT; regExp(${borrower_has_bank_account})=1; regExp(${function_sub_code})!MANDATE; regExp(${function_sub_code})!PD; regExp(${function_sub_code})=MANDATE|PD … (+16) |
| `submitCUMemberDetails` | submitCUMemberDetailsProcessor → submitCuMemberDetailsAuditDataProcessor → getGroupTypeProcessor → updateGroupTypeProcessor → processPromoCodeRulesProcessor → constructRequestDataForApproval | — | regExp(${function_sub_code})=GROUP; regExp(${group_type})!; regExp(${is_hold_for_clarification})!true |
| `submitCUMemberFinalDecision` | submitCUMemberDetailsProcessor → submitCUMemberFinalDecisionProcessor | — | — |
| `submitCreditUnderwriting` | validateCreditUnderwriterPermissionProcessor → approveCreditUnderwritingProcessor → getGroupTypeProcessor → updateGroupTypeProcessor → processPromoCodeRulesProcessor → rejectCreditUnderwritingProce... | — | regExp(${function_code})=GROUP; regExp(${function_code})=INDIVIDUAL; regExp(${function_code}_${function_sub_code})=GROUP_APPROVE; regExp(${function_code}_${function_sub_code})=GROUP_REJECT; regExp(${function_code}_${function_sub_code})=INDIVIDUAL_REJECT; regExp(${function_sub_code})=APPROVE; regExp(${function_sub_code})=REJECT; regExp(${group_type})! … (+4) |
| `submitDDEDetails` | updateLoanAppStepsStatusProcessor | — | — |
| `submitDisbursementAccountDetails` | casaAccountValidationProcessor → saveGroupCasaAccountProcessor → updateGroupStepsStatusProcessor → updateGroupStepsStatusProcessor → submitSavingsAccountDetailsPreProcessor → constructRequestDataFo... | — | regExp(${function_code})!CONDUCT_SHG; regExp(${function_code})=CONDUCT_SHG; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|VERIFY; regExp(${group_has_hdfc_account})=true; regExp(${save_account_details})=true |
| `submitDotAccountDetails` | validateDotAccountProcessor → accountStatusInquiryProcessor → verifyDotAccountStatusProcessor → submitDotAccountDetailsProcessor → submitDotAccountDetailsPreProcessor → constructRequestDataForApproval | — | regExp(${is_rejected})!true |
| `submitFinancialDetail` | submitFinancialDetailProcessor | — | — |
| `submitGroupConductBet` | submitGroupConductBetProcessor → submitGroupSHGRatingProcessor → submitGroupConductBetPreProcessAuditData → constructRequestDataForApproval | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=SHG_SAVINGS |
| `submitGroupConductPdc` | submitGroupSHGConductPdcProcessor → submitGroupConductPdcProcessor → rejectGroupForSignatoryNotInterestedProcessor → rejectPdcTaskProcessor → submitGroupSHGConductPdcPreProcessorAuditData → constru... | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=SHG; regExp(${reject_api_call_required})=true; regExp(${reject_pdc_api_call_required})=true |
| `submitIncomeDetail` | submitIncomeDetailsProcessor → updateLoanAppStepsStatusProcessor → resetCUMemberDetailsProcessor → constructRequestDataForApproval | — | regExp(${function_code})!CM_DASHBOARD; regExp(${function_code})=CM_DASHBOARD |
| `submitManualSignTask` | submitManualSignTaskProcessor → constructRequestDataForApproval | — | — |
| `submitPhysicalSignTask` | submitPhysicalSignTaskProcessor → constructRequestDataForApproval | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `submitSavingAccAdditionalDetails` | submitSavingAccAdditionalDetailsProcessor → processAllEligibilityRulesProcessor → updateGroupStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${function_code})!CM_DASHBOARD; regExp(${function_code})=CM_DASHBOARD |
| `submitSavingsAccountDetails` | addGroupDetailsProcessor → casaAccountValidationProcessor → saveGroupCasaAccountProcessor → updateGroupStepsStatusProcessor → updateGroupStepsStatusProcessor → saveGroupCasaAccountProcessor → submi... | — | regExp(${beneficiary_bank})!OTHER_BANK; regExp(${function_code})=CONDUCT_SHG; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})!REVIEW_MEMBER; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|PD; regExp(${function_sub_code})=CREATE|REVIEW_MEMBER|VERIFY; regExp(${function_sub_code})=PD … (+3) |
| `submitScheduleBet` | getBetTaskDetailsProcessor → submitScheduleBetProcessor → scheduleBetPreProcessAuditData → constructRequestDataForApproval → closeLatestTaskProcessor → taskRollBackStatusCheckerProcessor | — | regExp(${close_task_flag})=true |
| `submitTaDashboardTask` | submitTaDashboardTaskProcessor → constructRequestDataForApproval | — | — |
| `testDocumentOCR` | documentInfoExtractProcessor | — | — |
| `triggerCkycApiCallBatch` | triggerCkycJobProcessor | — | — |
| `triggerDedupeAndMultiBureau` | performKycDedupeProcessor → factivaForBorrowerProcessor → triggerPosidexDedupeProcessor → triggerMultiBureauRequestProcessor → updateLoanAppStepsStatusProcessor | — | regExp(${function_code}_${function_sub_code})=CONDUCT_BET_POST_BUREAU; regExp(${function_code}_${function_sub_code})=CONDUCT_BET_PRE_BUREAU; regExp(${trigger_required})=true |
| `triggerDisburseLoan` | triggerDisburseLoanProcessor | — | regExp(${function_sub_code})=DEFAULT|BATCH|SINGLE_LOAN_DISBURSEMENT|REINITIATE; regExp(${function_sub_code})=REINITIATE; regExp(${function_sub_code})=SINGLE_LOAN_DISBURSEMENT|REINITIATE |
| `triggerDocumentDispatchTask` | triggerDocumentDispatchTaskProcessor | — | regExp(${function_sub_code})=DEFAULT|BATCH |
| `triggerLoanAppPsl` | loanAppPslProcessor | — | — |
| `triggerMandateLink` | triggerMandateLinkProcessor | — | — |
| `triggerMultiBureauRequest` | triggerMultiBureauRequestProcessor → resetEligibilitySummaryProcessor → triggerMemberMultiBureauRequestProcessor | — | regExp(${borrower_id})!\$\{.*?\}; regExp(${family_member_id})!\$\{.*?\} |
| `triggerNetOffMarking` | triggerNetOffMarkingProcessor | — | regExp(${function_sub_code})=BATCH |
| `triggerPosidex` | borrowerFamilyMemberEligibilitySummaryPosidexProcessor | — | regExp(${borrower_id})!\$\{.*?\} |
| `triggerPromocodeRoiIndividualRules` | promocodeRoiCalculatorProcessor | — | — |
| `triggerRejectBetTask` | triggerRejectBetTaskProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `triggerRejectConductBetTask` | triggerRejectBetTaskProcessor | — | — |
| `triggerRejectConductPDTask` | triggerRejectBetTaskProcessor | — | — |
| `triggerRejectGroupBetTask` | triggerRejectBetTaskProcessor | — | — |
| `triggerRejectIndividualBetTask` | triggerRejectBetTaskProcessor | — | — |
| `triggerRejectPdcTask` | triggerRejectPdcTaskProcessor | — | regExp(${function_sub_code})=DEFAULT|BATCH |
| `triggerStagingDataMigration` | triggerStagingMigrationDataProcessor | — | regExp(${function_sub_code})=BATCH |
| `triggerUploadDocument` | triggerUploadDocumentProcessor | — | — |
| `updateAssigneeContributorByTaskId` | updateAssigneeContributorByTaskIdProcessor → updateEmployeeInLosProcessor | — | regExp(${function_sub_code})=TASK_DELEGATION |
| `updateBorrowerDetails` | dummyProcessor → setLoanAppPersonalDetailsResponseProcessor → createOrUpdateInsurancePolicyDetailsProcessor → initiateServiceCallProcessor → resetCUMemberDetailsProcessor → dummyProcessor | createOrUpdateBorrowerKycDetails, createOrUpdateLoanAppPersonalDetails | regExp(${function_code})=CM_DASHBOARD; regExp(${function_sub_code}_${function_code})=UPDATE; regExp(${marital_status})=MARRIED; regExp(${marital_status})=SINGLE; regExp(${premium_update_required})=true |
| `updateBorrowerMobile` | updateBorrowerMobileProcessor | — | regExp(${function_sub_code})=APPROVE|REJECTED |
| `updateDeviationRemedyDetails` | updateDeviationRemedyDetailsProcessor → updateLoanAppStepsStatusProcessor → constructRequestDataForApproval | — | regExp(${family_member_id})=0; regExp(${function_code})=CONDUCT_BET|ELIGIBILITY_SUMMARY|CONDUCT_PD |
| `updateEditDemographics` | generateDataForDemographics → createAndCompleteTaskProcessor → editDemoGraphicsDataChecker → updateEditDemographicsProcessor → updateWeakerSectionDetailsProcessor → createAndCompleteTaskProcessor →... | — | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|APPROVE; regExp(${function_code})=REJECT |
| `updateEntityStatus` | updateEntityStatusProcessor | — | — |
| `updateEsignStatus` | validateUpdateEsignStatus → updateEsignStatusProcessor → constructRequestDataForApproval | — | — |
| `updateGroupLoanTenure` | updateGroupLoanTenureProcessor → processAllEligibilityRulesProcessor | — | — |
| `updateGroupSignatories` | updateGroupSignatoriesProcessor | — | regExp(${function_code})=SHG_UPDATE; regExp(${function_sub_code})=UPDATE |
| `updateGroupStepsStatus` | updateGroupStepsStatusProcessor | — | — |
| `updateGroupType` | updateGroupTypeProcessor | — | — |
| `updateLoanAppAssignee` | updateLoanAppAssigneeProcessor | — | — |
| `updateLoanAppEmployeeByVillage` | getGroupInfoByCustomerIdsProcessor → updateLoanApplicationServingEmployeeProcessor | — | regExp(${function_sub_code})=DEFAULT|UPDATE_SERV_EMP; regExp(${function_sub_code})=MEETING_CENTER; regExp(${function_sub_code})=UPDATE_SERV_EMP|MEETING_CENTER |
| `updateLoanAppStatus` | updateLoanAppStatusProcessor | — | — |
| `updateLoanAppStepsStatus` | updateLoanAppStepsStatusProcessor | — | regExp(${function_sub_code}_${function_code})=UPDATE_CONDUCT_BET |
| `updateMemberAvailingDetails` | updateMemberAvailingDetailsProcessor → constructRequestDataForApproval | — | — |
| `updatePosidexExtBatch` | updatePosidexExtBatchProcessor | — | — |
| `updateRenewalFlowFlags` | updateRenewalFlowFlagsProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL; regExp(${function_sub_code})=INDIVIDUAL|GROUP |
| `updateVtc` | updateVtcProcessor → constructRequestDataForApproval → geoTrackingAuditProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=GROUP|INDIVIDUAL; regExp(${function_sub_code})=INDIVIDUAL |
| `updateWeakerSectionDetails` | updateWeakerSectionDetailsProcessor | — | — |
| `uploadLoanOriginationDocument` | uploadLoanOriginationDocumentProcessor | — | regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT |
| `uploadPhysicalSignDocForGroup` | uploadPhysicalSignDocForGroupProcessor | — | — |
| `uploadPhysicalSignDocForMember` | uploadPhysicalSignDocForMemberProcessor | — | — |
| `uploadUdyam` | triggerUdyamProcessing | — | regExp(${function_sub_code})=BATCH |
| `validateDotAccountNumber` | dotAccountNumberValidationProcessor | — | — |
| `verifyAPYAccount` | verifyAPYAccountProcessor | — | — |
| `verifyAccountDetails` | accountStatusInquiryProcessor → impsPartnerValidationProcessor → pennyDropProcessor → accountStatusCheckProcessor → nameValidationCheckProcessor → verifyAccountPreProcessor → constructRequestDataFo... | — | regExp(${beneficiary_bank})=HDFC_BANK; regExp(${beneficiary_bank})=OTHER_BANK; regExp(${borrower_has_bank_account})=1; regExp(${function_sub_code}_${beneficiary_bank})=DEFAULT_HDFC_BANK; regExp(${function_sub_code}_${beneficiary_bank})=DEFAULT_OTHER_BANK; regExp(${response_status})!FAIL |
| `verifyDotAccountStatus` | validateDotAccountProcessor → accountStatusInquiryProcessor → verifyDotAccountStatusProcessor → updateDotAccountCreationDetails | — | — |
| `verifyIFSCCodeDetails` | verifyIFSCCodeDetailsProcessor | — | — |
| `verifyMobileForActiveApplication` | verifyMobileForActiveApplicationProcessor | — | — |
| `verifyPreviousAccountNumber` | verifyPreviousAccountNumberProcessor | — | — |
| `verifyShgCode` | verifyShgCodeProcessor | — | — |
| `viewBulkCalculateBlendedRoiFileStatus` | viewBulkCalculateBlendedRoiFileStatusProcessor | — | — |
| `viewBulkCustomerAllocationFileStatus` | viewBulkCustomerAllocationFileStatusProcessor | — | — |
| `viewBulkIrrFileStatus` | viewBulkIRRFileStatusProcessor | — | — |
| `viewBulkPaymentReinitiationFileStatus` | viewBulkPaymentReinitiationFileStatusProcessor | — | — |
| `viewBulkPolicyEligibleCustomersFileStatus` | viewBulkPolicyEligibleCustomersFileStatusProcessor | — | — |
| `viewBulkReKycDetailsFileStatus` | viewBulkReKycDetailsStatusProcessor | — | — |
| `viewBulkRiskProfileFileStatus` | viewBulkRiskProfileFileStatusProcessor | — | — |
| `viewBulkSalesPromocodeFileStatus` | viewBulkSalesPromocodeFileStatusProcessor | — | — |
| `viewBulkShgCodeFileStatus` | viewBulkShgCodeFileStatusProcessor | — | — |
| `viewBulkUpdateInterestSubventionFileStatus` | viewBulkUpdateInterestSubventionFileStatusProcessor | — | — |
| `voterIdAuthentication` | voterIdAuthenticationProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-accounting-v2/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-accounting-v2` 
**Root element:** `Accounting`  
**Requests:** 138

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `bulkFileToSGAssetCriteriaGroupUpdateJob` | populateUserDetails → bulkFileToSGAssetCriteriaGroupUpdateJobProcessor | — | — |
| `bulkFileToSGEnachRepresentationJob` | populateUserDetails → bulkFileToSGEnachRepresentationJobProcessor | — | — |
| `bulkFileToSGManualHoldMarkingJob` | populateUserDetails → bulkFileToSGManualHoldMarkingJobProcessor | — | — |
| `bulkFileToSGManualHoldRemovalJob` | populateUserDetails → bulkFileToSGManualHoldRemovalJobProcessor | — | — |
| `bulkFileToSGRefundMarkingJob` | populateUserDetails → bulkFileToSGRefundMarkingJobProcessor | — | — |
| `bulkSGToAssetCriteriaGroupUpdateJob` | bulkSGToAssetCriteriaGroupUpdateJobProcessor | — | — |
| `bulkSGToEnachRepresentationJob` | populateUserDetails → bulkSGToEnachRepresentationJobProcessor | — | — |
| `bulkSGToManualHoldMarkingJob` | populateUserDetails → bulkSGToManualHoldMarkingJobProcessor | — | — |
| `bulkSGToManualHoldRemovalJob` | populateUserDetails → bulkSGToManualHoldRemovalJobProcessor | — | — |
| `bulkSGToRefundMarkingJob` | bulkSGToRefundMarkingJobProcessor | — | — |
| `checkMandateStatusForUpdate` | checkMandateStatusProcessor | — | — |
| `createOrUpdateAssetClassificationMaster` | dummyProcessor → getUserDetailsPostProcessor → getMakerCheckerEnabledForUseCaseProcessor → validateAssetClassificationMasterProcessor → validateAssetClassificationMasterSlabListProcessor → construc... | getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+11) |
| `createOrUpdateAssetCriteriaMaster` | getUserDetailsPostProcessor → getMakerCheckerEnabledForUseCaseProcessor → validateAssetCriteriaMasterProcessor → validateAssetCriteriaMasterGroupListProcessor → validateAssetCriteriaMasterSlabListP... | getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+11) |
| `createOrUpdateBaseInterestRate` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForCreateBaseInterestRateProcessor → fetchBulkUniqueMasterData → sendForApprovalCreateBaseInterestRatePreProcessor → deleteDr... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `createOrUpdateGeneralLedger` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForCreateGeneralLedger → fetchBulkUniqueMasterData → sendForApprovalCreateGeneralLedgerPreProcessor → deleteDraftProcessor → ... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `createOrUpdateHoliday` | populateUserDetails → validateCreateHolidayDetailsProcessor → getMakerCheckerEnabledForUseCaseProcessor → fetchBulkUniqueMasterData → populateHolidayOfficeListProcessor → validateHolidayDataProcess... | submitApplication | regExp(${create_holiday})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+9) |
| `createOrUpdateInterestSetup` | populateUserDetails → validateForCreateInterestSetup → getMakerCheckerEnabledForUseCaseProcessor → constructRequestDataForApproval → deleteDraftProcessor → populateUserStoryProcessor → populateCurr... | submitApplication | regExp(${base_interest_rate_applicable})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+13) |
| `createOrUpdateInternalAccount` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → setOfficeDetailsProcessor → checkDataForCreateInternalAccountProcessor → checkOfficeAndIADForInternalAccountProcessor → generateCodeFo... | getNotificationMessageByNotificationCode, getOfficeDetails, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+13) |
| `createOrUpdateInternalAccountDefinition` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForCreateInternalAccountDefinitionProcessor → generateCodeForCreateInternalAccountDefinitionProcessor → fetchBulkUniqueMaster... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+13) |
| `createOrUpdateLoanProduct` | populateUserDetails → fetchBulkUniqueMasterDataExt → validateForCreateLoanProduct → validateLoanTransactionPlaceholders → validateLoanProductAssetCriteriaDetailsProcessor → checkDataForLoanProductA... | submitApplication | regExp(${auto_closure_tolerance_allowed})=true; regExp(${eligible_for_net_off})=true; regExp(${enach_allowed})=true; regExp(${excess_amount_refund_allowed})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE … (+26) |
| `createOrUpdatePriceMaster` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → validateForCreatePriceMaster → constructRequestDataForApproval → deleteDraftProcessor → populateUserStoryProcessor → populateCurren... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `createOrUpdatePriceSetup` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → validateForCreatePriceSetup → fetchBulkUniqueMasterData → constructRequestDataForApproval → deleteDraftProcessor → populateUserStor... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1; regExp(${tax_applicable})=true … (+13) |
| `createOrUpdateProductScheme` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForCreateProductSchemeProcessor → checkPricingDataForProductSchemeProcessor → checkPriceSetupDataProcessor → checkProductSche... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `createOrUpdateSavingsAccount` | populateCurrencyFromProductSchemeProcessor → generateSequenceNumberProcessor → validateProductSchemeForAccountProcessor → createSavingsAccountProcessor → createAccountBalanceProcessor → dummyProcessor | getOfficeDetails | — |
| `createOrUpdateSavingsProduct` | populateUserDetails → validateForCreateSavingsProduct → validateTransactionPlaceholders → fetchBulkUniqueMasterDataExt → getMakerCheckerEnabledForUseCaseProcessor → constructRequestForApprovalUsing... | submitApplication | regExp(${function_code})!APPROVE; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${joint_holders_allowed})=true; regExp(${maker_checker_enabled})=0 … (+14) |
| `createOrUpdateStampDutyMaster` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → validateForCreateStampDutyMaster → fetchBulkUniqueMasterData → constructRequestDataForApproval → deleteDraftProcessor → populateUse... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `createOrUpdateTaxComponent` | getUserDetailsPostProcessor → getMakerCheckerEnabledForUseCaseProcessor → fetchCurrencyValueProcessor → validateTaxComponentSlabProcessor → parseDataForStartDateAndEndDateProcessor → checkDataForCr... | getUseCaseDetails, getUserDetails, submitApplication | regExp(${computation_type})!TAX_COM_EXT; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+20) |
| `createOrUpdateTaxGroup` | getUserDetailsPostProcessor → getMakerCheckerEnabledForUseCaseProcessor → checkDataForCreateTaxGroup → fetchCurrencyValueProcessor → fetchBulkUniqueMasterData → constructRequestDataForApproval → de... | getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `createOrUpdateWorkingDay` | setUserStoryForResponseProcessor → getUserDetailsPostProcessor → dummyProcessor → dummyProcessor → getUseCaseDetailsPostProcessor → checkDataForWorkingDayMasterProcessor → constructRequestDataForAp... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+16) |
| `createRepaymentMandateDetails` | getUseCaseDetailsPostProcessor → validateMandateDetailsForCreateProcessor → createMandateDetailsProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode, getUseCaseDetails | — |
| `deleteAccountingTaskUsingCode` | deleteAccountingTaskUsingCodeProcessor | — | — |
| `deleteAssetClassificationMaster` | checkDataForDeleteAssetClassificationMasterProcessor → getUserDetailsPostProcessor → getMakerCheckerEnabledForUseCaseProcessor → getAssetClassificationMasterDetailsProcessor → sendForApprovalLogica... | getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteAssetCriteriaMaster` | getUserDetailsPostProcessor → checkDataForDeleteAssetCriteriaMasterProcessor → getMakerCheckerEnabledForUseCaseProcessor → constructRequestDataForApproval → getAssetCriteriaMasterDetailsProcessor →... | getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteBaseInterestRate` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForDeleteBaseInterestRateProcessor → fetchBulkUniqueMasterData → sendForApprovalLogicalDeleteBaseInterestRatePreProcessor → s... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteGeneralLedger` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForDeleteGeneralLedger → setIdentifierAndMasterDataForDeleteGeneralLedgerProcessor → fetchBulkUniqueMasterData → sendForAppro... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteHoliday` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → getHolidayDetailsProcessor → getHolidayOfficeDetailsProcessor → populateHolidayOfficeListProcessor → fetchBulkUniqueMasterData → co... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteInterestSetup` | getInterestSetupDetailsProcessor → populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → validateForDeleteInterestSetup → constructRequestDataForApproval → populateUserStoryProcessor → ... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteInternalAccount` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForDeleteInternalAccountProcessor → setOfficeDetailsProcessor → fetchBulkUniqueMasterData → sendForApprovalLogicalDeleteInter... | getNotificationMessageByNotificationCode, getOfficeDetails, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteInternalAccountDefinition` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForDeleteInternalAccountDefinitionProcessor → fetchBulkUniqueMasterData → sendForApprovalLogicalDeleteInternalAccountDefiniti... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deletePriceMaster` | getPriceMasterDetailsProcessor → populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → validateForDeletePriceMaster → constructRequestDataForApproval → populateUserStoryProcessor → logi... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deletePriceSetup` | getPriceSetupDetailsProcessor → populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → validateForDeletePriceSetup → constructRequestDataForApproval → populateUserStoryProcessor → logica... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteStampDutyMaster` | getStampDutyMasterDetailsProcessor → populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → validateForDeleteStampDutyMaster → constructRequestDataForApproval → populateUserStoryProcesso... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteTaxComponent` | getUserDetailsPostProcessor → getMakerCheckerEnabledForUseCaseProcessor → constructRequestDataForApproval → getTaxComponentDetailsProcessor → sendForApprovalLogicalDeleteTaxComponentPreProcessor → ... | getUserDetails, submitApplication | regExp(${computation_type})!TAX_COM_EXT; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteTaxGroup` | getUserDetailsPostProcessor → getMakerCheckerEnabledForUseCaseProcessor → checkDataForLogicalDeleteProcessor → getTaxGroupDetailsProcessor → constructRequestDataForApproval → sendForApprovalLogical... | getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteWorkingDay` | setUserStoryForResponseProcessor → getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForDeleteWorkingDayProcessor → constructRequestDataForApproval → dummyProcessor → logicalD... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `downloadAssetCriteriaGroupUpdateUploadedFile` | downloadAssetCriteriaGroupUpdateUploadedFileProcessor | — | — |
| `downloadEnachRepresentationUploadedFile` | downloadEnachRepresentationUploadedFileProcessor | — | — |
| `downloadManualHoldMarkingUploadedFile` | downloadManualHoldMarkingUploadedFileProcessor | — | — |
| `downloadManualHoldRemovalUploadedFile` | downloadManualHoldRemovalUploadedFileProcessor | — | — |
| `downloadRefundMarkingUploadedFile` | downloadRefundMarkingUploadedFileProcessor | — | — |
| `expirePendingMandatesBatchJob` | expirePendingMandatesBatchProcessor | — | — |
| `fetchFailedSIPresentationList` | updateFailedSIPresentationListProcessor → fetchFailedSIPresentationListProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `fetchMandateDetails` | fetchMandateDetailsProcessor → fetchMandateDetailsForGroupProcessor → fetchBulkUniqueMasterDataExt → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=GROUP |
| `fetchMandateDetailsHistory` | fetchMandateDetailsHistoryProcessor → fetchMandateDetailsHistoryProcessor → fetchMandateDetailsHistoryForGroupProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | regExp(${function_sub_code})=BY_LOAN_APPLICATION_NO; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=GROUP |
| `generateEnachPresentationFile` | outboundEnachPresentationBatchProcessor | — | — |
| `generateEnachRepresentationFile` | outboundEnachRepresentationBatchProcessor | — | — |
| `generateFinnoneSILienPresentationFiles` | outboundFinnoneSILienPresentationBatchProcessor | — | — |
| `generateOnDemandDocument` | generateReportProcessor → generateReportProcessor → generateReportProcessor → generateReportProcessor | — | regExp(${function_code})=REPORT; regExp(${function_sub_code})=LOAN_REBOOKING_DOC; regExp(${function_sub_code})=RPS_REPORT; regExp(${function_sub_code})=SI_MANDATE_DOC; regExp(${function_sub_code})=SOA_REPORT |
| `generateSIAutoHoldRemovalPresentationFiles` | outboundSIAutoHoldRemovalBatchProcessor | — | — |
| `generateSILienPresentationFiles` | outboundSILienPresentationBatchProcessor | — | — |
| `generateSIManualHoldMarkingPresentationFiles` | outboundSIManualHoldMarkingBatchProcessor | — | — |
| `generateSIManualHoldRemovalPresentationFiles` | outboundSIManualHoldRemovalBatchProcessor | — | — |
| `generateSIManualPresentationFiles` | outboundSIManualPresentationBatchProcessor | — | — |
| `generateSIPresentationFiles` | outboundSIPresentationBatchProcessor | — | — |
| `generateUniqueReferenceNumber` | generateUniqueReferenceNumberProcessor → dummyProcessor | — | — |
| `getAccountDetails` | checkAccountDetailsProcessor → getAccountDetailsProcessor → fetchBulkUniqueMasterData → dummyProcessor | — | — |
| `getAssetClassificationMasterDetails` | getAssetClassificationMasterDetailsProcessor → dummyProcessor | — | — |
| `getAssetClassificationMasterList` | getAssetClassificationMasterListProcessor → dummyProcessor | — | — |
| `getAssetCriteriaMasterDetails` | getAssetCriteriaMasterDetailsProcessor → getAssetCriteriaSlabDetailsProcessor → dummyProcessor | — | — |
| `getAssetCriteriaMasterList` | getAssetCriteriaMasterListProcessor → dummyProcessor | — | — |
| `getBaseInterestRateDetails` | getBaseInterestRateDetailsProcessor → fetchBulkUniqueMasterData → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getBaseInterestRateList` | getBaseInterestRateListProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getCurrencyMasterList` | getCurrencyMasterListProcessor → dummyProcessor | — | — |
| `getEffectiveInterestRateForInterestSetupCode` | getEffectiveInterestRateForInterestSetupCodeProcessor | — | — |
| `getEffectiveInterestRateForProductScheme` | getInterestSetupDetailsForProductSchemeProcessor → getEffectiveInterestRateForInterestSetupCodeProcessor → populateInterestDetailsForAccountProcessor → fetchBulkUniqueMasterData | — | — |
| `getEntryLookupCodesOfTransaction` | getEntryLookupCodesOfTransactionForPriceProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | regExp(${function_code})=PRICE |
| `getFinancialTransactionPlaceholderList` | getFinancialTransactionPlaceholderListProcessor → dummyProcessor | — | — |
| `getGeneralLedgerDetails` | getGeneralLedgerDetailsProcessor → fetchBulkUniqueMasterData → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getGeneralLedgerList` | getGeneralLedgerListProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getHolidayDetails` | getHolidayDetailsProcessor → getHolidayOfficeDetailsProcessor → populateHolidayOfficeListProcessor → fetchBulkUniqueMasterData → populateUserStoryProcessor | — | — |
| `getHolidayList` | getHolidayListProcessor → populateUserStoryProcessor | — | — |
| `getInterestSetupDetails` | getInterestSetupDetailsProcessor → populateUserStoryProcessor | — | — |
| `getInterestSetupList` | getInterestSetupListProcessor → populateUserStoryProcessor | — | — |
| `getInternalAccountDefinitionDetails` | getInternalAccountDefinitionDetailsProcessor → fetchBulkUniqueMasterData → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getInternalAccountDefinitionList` | getInternalAccountDefinitionListProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getInternalAccountDetails` | getInternalAccountDetailsProcessor → fetchBulkUniqueMasterData → setOfficeDetailsProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode, getOfficeDetails | — |
| `getInternalAccountList` | getInternalAccountListProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getLoanProductDetails` | getLoanProductByProductSchemeIdProcessor → getLatestLoanProductIdForProductId → getLoanProductDetailsProcessor → getLoanProductTransactionsAndAccountingDetailsProcessor → getLoanProductAssetCriteri... | — | regExp(${function_code})=BYSCHEMEID; regExp(${function_code})=DEFAULT; regExp(${function_code})=LATEST |
| `getLoanProductList` | getLoanProductListProcessor → getProductCodeNameListProcessor → getAvailableLoanProductListProcessor → populateUserStoryProcessor | — | regExp(${function_sub_code})=AVAILABLE_LOAN_PRODUCTS; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=GET_PRODUCT_CODE_NAME |
| `getPresentationDetailsForLoanAccount` | getPresentationDetailsForLoanAccountProcessor | — | — |
| `getPriceMasterDetails` | getPriceMasterDetailsProcessor → populateUserStoryProcessor | — | — |
| `getPriceMasterList` | getPriceMasterListProcessor → populateUserStoryProcessor | — | — |
| `getPriceSetupDetails` | getPriceSetupDetailsProcessor → populateUserStoryProcessor | — | — |
| `getPriceSetupList` | getPriceSetupListProcessor → populateUserStoryProcessor | — | — |
| `getProductList` | getProductListProcessor → dummyProcessor | — | — |
| `getProductSchemeDetails` | getProductSchemeDetailsProcessor → fetchBulkUniqueMasterDataExt → fetchBulkUniqueMasterData → getProductSchemePricingDetailsProcessor → populateMasterDataInProductSchemePricingDetailsProcessor → ge... | getNotificationMessageByNotificationCode | — |
| `getProductSchemeList` | getProductSchemeListProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getSavingsAccountDetails` | getSavingsAccountDetailsProcessor → fetchBulkUniqueMasterData → dummyProcessor | — | regExp(${function_sub_code})!TRANSACTION |
| `getSavingsProductDetails` | getSavingsProductDetailsProcessor → getSavingsProductGeneralLedgerDetailsProcessor → getTransactionsAndAccountingDetailsProcessor → fetchBulkUniqueMasterDataExt → populateUserStoryProcessor | — | — |
| `getSavingsProductList` | getSavingsProductListProcessor → populateUserStoryProcessor | — | — |
| `getServerClockDetails` | getServerClockDetailsProcessor | — | — |
| `getStampDutyMasterDetails` | getStampDutyMasterDetailsProcessor → fetchBulkUniqueMasterData → populateUserStoryProcessor | — | — |
| `getStampDutyMasterList` | getStampDutyMasterListProcessor → populateUserStoryProcessor | — | — |
| `getTaskDataFromLMS` | getTaskProductDetailsProcessor → dummyProcessor | — | — |
| `getTaxComponentDetails` | getTaxComponentDetailsProcessor → dummyProcessor | — | — |
| `getTaxComponentList` | getTaxComponentListProcessor → dummyProcessor | — | — |
| `getTaxGroupDetails` | getTaxGroupDetailsProcessor → fetchBulkUniqueMasterData → dummyProcessor | — | — |
| `getTaxGroupList` | getTaxGroupListProcessor → dummyProcessor | — | — |
| `getTransactionCategoryList` | getTransactionCategoryListProcessor | — | — |
| `getWorkingDayDetails` | setUserStoryForResponseProcessor → fetchWorkingDayDetailsProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getWorkingDayList` | setUserStoryForResponseProcessor → fetchWorkingDayListProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getWorkingDays` | getWorkingDaysProcessor | — | — |
| `inboundReverseExcessAmountRefundJob` | inboundReverseExcessAmountRefundJobProcessor | — | — |
| `proactiveExcessAmountRefund` | proactiveExcessAmountRefundJobProcessor | — | — |
| `proactiveExcessAmountRefundStaging` | proactiveExcessAmountRefundStagingJobProcessor | — | — |
| `proactiveReverseTransaction` | proactiveReverseTransactionJobProcessor | — | — |
| `processingEnachPresentationResponseFiles` | inboundEnachPresentationBatchProcessor | — | — |
| `processingEnachRepresentationResponseFiles` | inboundEnachRepresentationBatchProcessor | — | — |
| `processingSIAutoHoldRemovalReverseFeedFiles` | inboundSIAutoHoldRemovalBatchProcessor | — | — |
| `processingSILienReverseFeedFiles` | inboundSILienPresentationBatchProcessor | — | — |
| `processingSIManualHoldMarkingReverseFeedFiles` | inboundSIManualHoldMarkingBatchProcessor | — | — |
| `processingSIManualHoldRemovalReverseFeedFiles` | inboundSIManualHoldRemovalBatchProcessor | — | — |
| `processingSIManualPresentationReverseFeedFiles` | inboundSIManualPresentationBatchProcessor | — | — |
| `processingSIReverseFeedFiles` | inboundSIPresentationBatchProcessor | — | — |
| `retrySIJob` | retrySIJobProcessor | — | — |
| `runInboundReverseExcessAmountRefundJob` | runInboundReverseExcessAmountRefundJobProcessor | — | — |
| `siFileDownloadBatchJob` | siFileDownloadBatchJobProcessor | — | — |
| `siFileEnquiryBatchJob` | siFileEnquiryBatchJobProcessor | — | — |
| `siFileTransferBatchJob` | siFileTransferBatchJobProcessor | — | — |
| `updateGeneralLedgerStatus` | getUserDetailsPostProcessor → dummyProcessor → dummyProcessor → getUseCaseDetailsPostProcessor → checkDataForUpdateGeneralLedgerStatus → fetchBulkUniqueMasterData → sendForApprovalUpdateGeneralLedg... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code}_${function_sub_code})=DEFAULT_ACTIVATE; regExp(${function_code}_${function_sub_code})=DEFAULT_DEACTIVATE; regExp(${function_sub_code})=ACTIVATE; regExp(${function_sub_code})=ACTIVATE|DEACTIVATE; regExp(${function_sub_code})=DEACTIVATE; regExp(${maker_checker_enabled})=0 … (+6) |
| `updateMandateDetailsTask` | populateUserDetails → validateDocumentDataForGenericDocumentProcessor → setCommonAttributesProcessor → validateCustomerAccountDetailsProcessor → validateBeneficiaryNameProcessor → validateMandateDe... | createOrUpdateTask, deleteTask | regExp(${existing_account})=NO; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=GROUP; regExp(${repayment_mode})=DIRDR … (+2) |
| `updateMandateStatus` | updateMandateStatusProcessor | — | — |
| `updateSIPresentationDetails` | checkDataForUpdateSIPresentationStatusProcessor → updateSIPresentationStatusProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `viewBulkAssetCriteriaGroupUpdateFileStatus` | viewBulkAssetCriteriaGroupUpdateFileStatusProcessor | — | — |
| `viewBulkEnachRepresentationFileStatus` | viewBulkEnachRepresentationFileStatusProcessor | — | — |
| `viewBulkManualHoldMarkingFileStatus` | viewBulkManualHoldMarkingFileStatusProcessor | — | — |
| `viewBulkManualHoldRemovalFileStatus` | viewBulkManualHoldRemovalFileStatusProcessor | — | — |
| `viewBulkRefundMarkingFileStatus` | viewBulkRefundMarkingFileStatusProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml`
**Owner service:** `novopay-platform-accounting-v2` 
**Root element:** `Accounting`  
**Requests:** 19

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `childLoanAccountExcessAmountRefund` | populateChildLoanAccountExcessAmountRefundDataProcessor → createLoanAccountPaymentsDetailsProcessor → updateLoanAccountChildAccountEntityProcessor | postTransaction | — |
| `childLoanBooking` | childLoanEventsProcessingProcessor | — | if(${function_code})=DEFAULT |
| `childLoanDisbursement` | populateDataForChildLoanBookingProcessor → bookChildLoanProcessor | — | — |
| `childLoanDisbursementCancellation` | setCommonAttributesProcessor → populateChildLoanDisbursementCancellationDataProcessor → checkLoanAccountInterestAccrualCalculationProcessor → checkLoanAccountInterestAccrualBookingProcessor → dummy... | postTransaction | — |
| `childLoanDisbursementCancellationParentRescheduling` | populateDisbursementCancellationParentAccountDetailsProcessor → dummyProcessor → populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails → dummyProcessor → createLoanAccountPaymentsDetailsPro... | postTransaction | — |
| `childLoanEventProcessingBatchJob` | childLoanEventProcessingJobProcessor | — | — |
| `childLoanForeclosure` | childLoanForeclosureProcessor | — | — |
| `childLoanPartPrepayment` | childLoanRestructuringProcessor → setCommonAttributesProcessor → createOrUpdateLoanAccountPartPrepaymentProcessor → createChildLoanPartPrepaymentInstallmentProcessor → createPartPrepaymentTaxDetail... | — | if(${function_code})=DO_TRANSACTION; if(${function_code})=RESTRUCTURE |
| `childLoanRebooking` | childLoanRebookingSaveAdjustmentDetailsProcessor → childLoanRestructuringProcessor → childLoanRebookingAdjustmentTxnProcessor | — | — |
| `childLoanRebookingAdjustmentTransaction` | populateAdditionalAmountDetailsProcessor → populateAdditionalAmountDetailsProcessor → populateAdditionalAmountDetailsProcessor → dummyProcessor → populateAdditionalAmountDetailsProcessor → dummyPro... | postTransaction | regExp(${excess_int_amt_txn})=true; regExp(${less_int_amt_txn})=true; regExp(${post_txn})=true |
| `childLoanReopening` | setCommonAttributesProcessor → populateChildLoanReopeningAccountDataProcessor → initiateClosureReversalProcessor → reverseTransactionProcessor → updateLoanAccountClosureDetailsProcessor → updateLoa... | — | — |
| `childLoanRepayment` | populateChildLoanAccountDataProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → getOfficeIdFromAccountNumberProcessor → checkEligibleFo... | postTransaction | if(${do_npa_reverse_movement})=true; if(${do_repayment_appropriation})=true; if(${repayment_mode})=ACH; if(${repayment_mode})=CASH; if(${repayment_mode})=DIRDR; if(${repayment_mode})=EXCESS_AMT; if(${repayment_mode})=NET_BANKING; if(${repayment_mode})=UPI … (+2) |
| `childLoanRestructuring` | childLoanRestructuringProcessor → createChildLoanAccountRestructuringDetailsProcessor → loanAdvanceRepaymentProcessor | — | if(${function_code})=FORECLOSURE; if(${function_code})=RESTRUCTURE |
| `childLoanTransactionReversal` | executeTransactionReversalProcessor → populateEODJobDataAfterReversalProcessor → populateLoanAccountPaymentDetailsDataProcessor → reverseTransactionProcessor → convertTransactionValueDateProcessor ... | — | — |
| `childWaiveLoanAccountCharges` | populateChildLoanWaiverDataProcessor → updateLoanDueDetailsForWaiverProcessor → updateWaiverLoanDueDetailsProcessor | — | — |
| `getChildLoanAccountList` | getChildLoanAccountListProcessor | — | — |
| `individualChildLoanForeclosure` | setUserStoryForResponseProcessor → setCommonAttributesProcessor → valdiateLoanAccountNumberAndStatusProcessor → populateUserDetails → fetchSuperDataForForeclosureProcessor → createPrepaymentDetails... | getNotificationMessageByNotificationCode, postTransaction | — |
| `parentLoanAccountPartPrepayment` | populateUserDetails → setCommonAttributesProcessor → fetchBulkUniqueMasterData → fetchSuperDataForForeclosureProcessor → createOrUpdateLoanAccountPartPrepaymentProcessor → getOfficeIdFromAccountNum... | — | — |
| `updateChildLoanDisbursementStatus` | updateChildLoanDisbursementStatusProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-accounting-v2/deploy/application/orchestration/insurance_orc.xml`
**Owner service:** `novopay-platform-accounting-v2` 
**Root element:** `Accounting`  
**Requests:** 12

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `checkInsuranceProductGeoEligibility` | checkInsuranceProductGeoEligibilityProcessor | — | — |
| `createOrUpdateInsuranceProduct` | validateInsuranceProductProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → fetchBulkUniqueMasterData → populateInsuranceProviderNameProcessor → populatePremiumCalculation... | submitApplication | regExp(${all_states_applicable})=false; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+11) |
| `createOrUpdatePremiumCalculationMatrixDetails` | validatePremiumCalculationMasterDetailsProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → populateTaxGroupNameProcessor → fetchBulkUniqueMasterData → populateMasterDataFo... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE; regExp(${is_tax_applicable})=true; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+9) |
| `deleteInsuranceProduct` | validateInsuranceProductProcessor → validateInsuranceProductForDeletion → getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → getStateListProcessor → getInsuranceProductDetailsProcess... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deletePremiumCalculationMatrixDetails` | validatePremiumCalculationMasterDetailsProcessor → validateInsuranceMatrixForDeletion → populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → getPremiumCalculation... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `getInsuranceDetailsForServicingEmployee` | getEmployeeServicableOfficeDetailsProcessor → getInsuranceDetailsForServicingEmployeeProcessor | — | — |
| `getInsurancePremiumAmount` | populateUserDetails → getInsurancePremiumAmountProcessor → populateInsuranceProviderNameProcessor → fetchBulkUniqueMasterData | — | — |
| `getInsuranceProductDetails` | getStateListProcessor → getInsuranceProductDetailsProcessor → fetchBulkUniqueMasterData → populateInsuranceProviderNameProcessor → populatePremiumCalculationNameProcessor | — | — |
| `getInsuranceProductList` | extractPremiumCalculationCodeNameDetailsProcessor → getInsuranceProductsProcessor | — | regExp(${function_sub_code})=BY_PROVIDER |
| `getPremiumCalculationMatrixDetails` | getPremiumCalculationMatrixDetailsProcessor → populateMasterDataForPremiumCalculationDetailsProcessor → populateTaxGroupNameProcessor → fetchBulkUniqueMasterData | — | — |
| `getPremiumCalculationMatrixList` | getPremiumCalculationMatrixListProcessor | — | — |
| `getUniquePremiumCalculationCodeAndName` | getUniquePremiumCalculationCodeAndNameProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-accounting-v2/deploy/application/orchestration/loans_insurance_orc.xml`
**Owner service:** `novopay-platform-accounting-v2` 
**Root element:** `Accounting`  
**Requests:** 26

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `bulkSGToDisbursementCancellationJob` | bulkSGToDisbursementCancellationJobProcessor | — | — |
| `bulkSGToPostDisbursementInsuranceUpdateJob` | bulkSGToPostDisbursementInsuranceUpdateJobProcessor | — | — |
| `deathForeclosureInsuranceJob` | deathForeclosureInsuranceJobProcessor | — | — |
| `getLoanAccountInsuranceList` | getLoanAccountInsuranceDetailListProcessor | — | — |
| `inboundDeathForeclosureInsuranceJob` | inboundDeathForeclosureInsuranceJobProcessor | — | — |
| `inboundDisbursementBajajErgoHealthInsuranceJob` | inboundDisbursementInsuranceJobProcessor | — | — |
| `inboundDisbursementCancellationBajajErgoHealthInsuranceJob` | inboundDisbursementCancellationInsuranceJobProcessor | — | — |
| `inboundDisbursementCancellationHdfcErgoHealthInsuranceJob` | inboundDisbursementCancellationInsuranceJobProcessor | — | — |
| `inboundDisbursementCancellationHdfcLifeLifeInsuranceJob` | inboundDisbursementCancellationInsuranceJobProcessor | — | — |
| `inboundDisbursementHdfcErgoHealthInsuranceJob` | inboundDisbursementInsuranceJobProcessor | — | — |
| `inboundDisbursementHdfcLifeLifeInsuranceJob` | inboundDisbursementInsuranceJobProcessor | — | — |
| `outboundDeathForeclosureInsuranceJob` | outboundDeathForeclosureInsuranceJobProcessor | — | — |
| `outboundDisbursementBajajErgoHealthInsuranceJob` | outboundDisbursementInsuranceJobProcessor | — | — |
| `outboundDisbursementCancellationBajajErgoHealthInsuranceJob` | outboundDisbursementCancellationInsuranceJobProcessor | — | — |
| `outboundDisbursementCancellationHdfcErgoHealthInsuranceJob` | outboundDisbursementCancellationInsuranceJobProcessor | — | — |
| `outboundDisbursementCancellationHdfcLifeLifeInsuranceJob` | outboundDisbursementCancellationInsuranceJobProcessor | — | — |
| `outboundDisbursementHdfcErgoHealthInsuranceJob` | outboundDisbursementInsuranceJobProcessor | — | — |
| `outboundDisbursementHdfcLifeLifeInsuranceJob` | outboundDisbursementInsuranceJobProcessor | — | — |
| `runInboundDeathForeclosureInsuranceJob` | runInboundDeathForeclosureInsuranceJobProcessor | — | — |
| `runInboundDisbursementBajajErgoHealthInsuranceJob` | runInboundDisbursementInsuranceJobProcessor | — | — |
| `runInboundDisbursementCancellationBajajErgoHealthInsuranceJob` | runInboundDisbursementCancellationInsuranceJobProcessor | — | — |
| `runInboundDisbursementCancellationHdfcErgoHealthInsuranceJob` | runInboundDisbursementCancellationInsuranceJobProcessor | — | — |
| `runInboundDisbursementCancellationHdfcLifeLifeInsuranceJob` | runInboundDisbursementCancellationInsuranceJobProcessor | — | — |
| `runInboundDisbursementHdfcErgoHealthInsuranceJob` | runInboundDisbursementInsuranceJobProcessor | — | — |
| `runInboundDisbursementHdfcLifeLifeInsuranceJob` | runInboundDisbursementInsuranceJobProcessor | — | — |
| `validateInsurance` | validateInsuranceProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-accounting-v2/deploy/application/orchestration/loans_notification.xml`
**Owner service:** `novopay-platform-accounting-v2` 
**Root element:** `Accounting`  
**Requests:** 2

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `loanInstallmentBounceNotificationJob` | loanInstallmentBounceNotificationJobProcessor | — | — |
| `loanInstallmentDueNotificationJob` | loanInstallmentDueNotificationJobProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml`
**Owner service:** `novopay-platform-accounting-v2` 
**Root element:** `Accounting`  
**Requests:** 82

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `bulkFileToSGTransactionReversalJob` | populateUserDetails → bulkFileToSGTransactionReversalJobProcessor | — | — |
| `bulkSGToTransactionReversalJob` | bulkSGToTransactionReversalJobProcessor | — | — |
| `calculateAnnualPercentageRate` | calculateAnnualPercentageRateProcessor | — | — |
| `calculateStampDutyCharges` | calculateStampDutyChargesProcessor | — | — |
| `cancelLoanForeclosure` | cancelLoanForeclosureProcessor → dummyProcessor | deleteTask | regExp(${task_status})!APPROVED|REJECTED |
| `createOrUpdateLoanAccount` | populateCurrentDateProcessor → throwNovopayFatalExceptionProcessor → validateLoanAccountDetailsProcessor → validateDisbursementRepaymentAccountDetailsProcessor → populateRepaymentDetailsProcessor →... | createActorAccountDetails, getCustomerDetails, getOfficeDetails | if(${function_sub_code})=UPDATE; regExp(${errorCode})!\$\{errorCode\}; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${run_mode})=REAL |
| `disburseLoan` | populateUserDetails → validateLoanDisbursementDetailsProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateCurrentDateProcessor → dummyProcessor → dummyProcessor → populateCurrentDateProc... | getLoanAccountDetails, postTransaction, submitApplication | if(${call_post_transaction_required})=1; if(${disbursement_mode})=CASH; if(${disbursement_mode})=OTHBACCT; if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1 … (+14) |
| `downloadTransactionReversalUploadedFile` | downloadTransactionReversalUploadedFileProcessor | — | — |
| `fetchDisbursementCancellationSimulationDetails` | setCommonAttributesProcessor → validateDataForDisbursementCancellation → populateUserDetails → dummyProcessor → fetchDisbursementCancellationSimulationDetailsProcessor → dummyProcessor | — | — |
| `fetchLoanAccountChargeDetails` | dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → fetchLoanAccountChargeDetailsProcessor → fetchChargeDetailsProcessor → dummyProcessor | — | regExp(${event})=DISBURSEMENT_CASA|APR; regExp(${event})=DISBURSEMENT_CASH; regExp(${event})=DISB_CNCL; regExp(${event})=FORECLOSURE; regExp(${function_sub_code})=BY_PRICE_SETUP_CODE; regExp(${function_sub_code})=DEFAULT |
| `fetchLoanForeclosureSimulationDetails` | setCommonAttributesProcessor → validateTransactionForLoanAccountProcessor → fetchSuperDataForForeclosureProcessor → validateDataForForeclosureProcessor → validateLoanPrepaymentProductProcessor → du... | — | regExp(${channel_code},${client_code})=novosli,novosli |
| `fetchPartPrepaymentRepaymentSchedule` | dummyProcessor → populateUserDetails → setCommonAttributesProcessor → validateLoanAccountPartPrepaymentProcessor → generateLoanAccountPartPrepaymentRepaymentScheduleProcessor → dummyProcessor | — | — |
| `fetchRestructuringRepaymentSchedule` | populateUserDetails → setCommonAttributesProcessor → validateLoanRestructuringBusinessCaseProcessor → populateRegisterLoanAccountRescheduleDataPreProcessor → registerLoanAccountRescheduleEventProce... | — | regExp(${is_roi_changed})=true; regExp(${restructuring_impact})=UPDATE_EMI; regExp(${restructuring_impact})=UPDATE_TENURE |
| `generatePreEMIRepaymentSchedule` | populateUserDetails → generatePreEMIRepaymentScheduleProcessor | — | — |
| `generateRepaymentSchedule` | populateUserDetails → getInterestSetupDetailsProcessor → dummyProcessor → getInterestSetupDetailsProcessor → dummyProcessor → validateGenerateRepaymentScheduleProcessor → generateRepaymentScheduleP... | getLoanProductDetails | if(${installment_multiples_of})=ZERO; if(${installment_type})=INSTL_TYP_BULT; if(${installment_type})=INSTL_TYP_PRN; if(${upfront_interest_applicable})=true; regExp(${function_sub_code})!BY_PRODUCT_ID|BY_EMI_AMOUNT; regExp(${function_sub_code})=BY_EMI_AMOUNT; regExp(${function_sub_code})=BY_PRODUCT_ID; regExp(${function_sub_code})=DEFAULT … (+6) |
| `getActiveLoansForCustomer` | getActiveLoansForCustomerProcessor | — | — |
| `getBulkLoanAccountDetails` | getBulkLoanAccountDetailsProcessor | — | — |
| `getCasaBalanceDetails` | getCasaBalanceDetailsProcessor | — | — |
| `getCustomerAccountList` | getCustomerAccountListProcessor | — | — |
| `getCustomerLoanAccountBounces` | getCustomerLoanAccountBouncesProcessor | — | — |
| `getDeathForeclosureDetails` | getDeathForeclosureDetailsProcessor → dummyProcessor | — | regExp(${function_sub_code})=BY_ACCOUNT_NUMBER; regExp(${function_sub_code})=BY_TASK_ID |
| `getDisbursementCancellationDetails` | switchChildToParentLoanAccountNumberProcessor → getDisbursementCancellationDetailsProcessor → fetchBulkUniqueMasterData → populateUserStoryProcessor | — | — |
| `getLoanAccountBPIAmount` | getLoanAccountAccruedBPIAmountProcessor | — | — |
| `getLoanAccountBasicDetails` | setCommonAttributesProcessor → valdiateLoanAccountNumberProcessor → validateMaturityDateProcessor → getLoanAccountBasicDetailsProcessor → getLoanAccountInstallmentDetailsProcessor → getLoanDisburse... | — | — |
| `getLoanAccountCASADetails` | dummyProcessor → dummyProcessor → getLoanAccountCASADetailsProcessor → dummyProcessor | — | regExp(${function_code})=DISB_IFT_ACT_DETAILS; regExp(${function_code})=DISB_NEFT_ACT_DETAILS |
| `getLoanAccountDetails` | getLoanAccountByExternalRefNumberProcessor → getLoanAccountDetailsProcessor → populateDisbursementRepaymentAccountDetailsProcessor → getAccountInterestDetailsProcessor → populateDisbursementAmountP... | — | if(${function_sub_code})=DEFAULT; if(${function_sub_code})=ENQUIRY |
| `getLoanAccountDisbursmentTransactions` | getLoanDisbursementTransactionHistoryProcessor | — | — |
| `getLoanAccountDpdCount` | getLoanAccountDpdCountProcessor → dummyProcessor | — | — |
| `getLoanAccountExcessAmountRefundDetails` | getLoanAccountExcessAmountRefundDetailsProcessor → fetchBulkUniqueMasterData → fetchBulkUniqueMasterData → fetchBulkUniqueMasterData → dummyProcessor | — | regExp(${is_proactive_refund})=false; regExp(${is_proactive_refund})=true |
| `getLoanAccountExcessAmountRefundList` | getLoanAccountExcessAmountRefundListProcessor → dummyProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getLoanAccountGenericDetails` | getLoanAccountGenericDetailsProcessor → fetchBulkUniqueMasterData → dummyProcessor | — | — |
| `getLoanAccountList` | getLoanAccountsByCustomerIdProcessor → getLoanAccountListProcessor → populateCustomerOfficeDetailsProcessor → populateUserStoryProcessor | — | regExp(${customer_present})=TRUE |
| `getLoanAccountOverviewDetails` | setCommonAttributesProcessor → checkLoanAccountInterestAndPenalAccrualProcessor → getLoanAccountOverviewDetailsProcessor → getLoanAccountInstallmentDetailsProcessor → populateUserStoryProcessor | — | regExp(${function_sub_code})=CALC_ACCRUAL |
| `getLoanAccountPartPrepaymentDetails` | getLoanAccountPartPrepaymentDetailsProcessor → fetchBulkUniqueMasterData | — | — |
| `getLoanAccountRebookingDetails` | getLoanAccountRebookingDetailsProcessor → fetchBulkUniqueMasterData → dummyProcessor | — | — |
| `getLoanAccountReopeningDetails` | populateLoanAccountReopeningDetailsProcessor → fetchBulkUniqueMasterData → dummyProcessor | — | — |
| `getLoanAccountRepaymentScheduleDetails` | valdiateLoanAccountNumberProcessor → getLoanAccountRepaymentScheduleDetailsProcessor → populateUserStoryProcessor | — | — |
| `getLoanAccountRestructuringDetails` | getLoanRestructuringDetailsProcessor → populateUserStoryProcessor | — | — |
| `getLoanAccountRestructuringList` | getLoanRestructuringListProcessor → populateUserStoryProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getLoanAccountSummaryDetails` | setCommonAttributesProcessor → valdiateLoanAccountNumberProcessor → getLoanAccountSummaryDetailsProcessor → getPenalInterestAccrualDetailsProcessor → getInterestAccrualDetailsProcessor → populateUs... | — | — |
| `getLoanForeclosureDetails` | getLoanForeclosureDetailsProcessor → populateUserStoryProcessor | — | — |
| `getLoanMaturityDateAndNumberOfInstallments` | validateParametersForMaturityDate → generateMaturityDateProcessor → generateNumberOfInstallmentsProcessor | — | if(${installment_type})=INSTL_TYP_BULT; regExp(${function_code})=ALL; regExp(${installment_type})!INSTL_TYP_BULT; regExp(${number_of_installments})![0-9]{1,3}; regExp(${number_of_installments})=[0-9]{1,3}; regExp(${schedule_start_date})![0-9]{1,14} … (+2) |
| `getLoanUpfrontInterestAmount` | computeUpfrontInterestAmountProcessor | — | regExp(${installment_type})!INSTL_TYP_BULT |
| `getManualJournalEntryDetails` | getManualJournalEntryDetailsProcessor → dummyProcessor | — | — |
| `getManualJournalEntryList` | getManualJournalEntryListProcessor → dummyProcessor | — | — |
| `getPartPrepaymentBPIAmount` | getPartPrepaymentBPIAmountProcessor | — | — |
| `getVillageAccountingPortFolioSummary` | getVillageAccountingPortfolioSummaryProcessor → getVillageAccountingPortfolioAccountNumbersProcessor | — | regExp(${function_sub_code})!LOAN_ACCOUNTS; regExp(${function_sub_code})=LOAN_ACCOUNTS|VALIDATION |
| `groupLoanAccountRebooking` | setCommonAttributesProcessor → validateDataForGroupLoanAccountRebookingProcessor → validateDocumentDataForGenericDocumentProcessor → populateUserDetails → setCommonAttributesProcessor → dummyProces... | createOrUpdateTask, deleteTask | regExp(${create_task})=true; regExp(${do_rebooking})=true; regExp(${function_code})!REJECT; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${reject_rebooking})=true; regExp(rebooking_reason)=OTHERS |
| `individualLoanAccountRebooking` | setCommonAttributesProcessor → validateTransactionForLoanAccountProcessor → validateDataForIndividualLoanAccountRebookingProcessor → validateDocumentDataForGenericDocumentProcessor → populateUserDe... | createOrUpdateTask, deleteTask | regExp(${create_task})=true; regExp(${do_rebooking})=true; regExp(${function_code})!REJECT; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${reject_rebooking})=true; regExp(rebooking_reason)=OTHERS |
| `interestAccrualCalculation` | trialInterestAccrualCalculationProcessor → interestAccrualCalculationProcessor → interestAccrualCalculationBatchProcessor | — | if(${function_sub_code})=BATCH; if(${run_mode})=REAL; if(${run_mode})=TRIAL; regExp(${function_sub_code})=DEFAULT |
| `interestAccrualPosting` | interestAccrualBookingProcessor → interestAccrualBookingBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `loanAccountAssetClassificationJob` | validateLoanAccountNumbersList → populateUserDetails → loanAccountAssetClassificationProcessor → populateUserDetails → loanAccountAssetClassificationBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `loanAccountAssetCriteriaJob` | validateLoanAccountNumbersList → populateUserDetails → loanAccountAssetCriteriaProcessor → populateUserDetails → loanAccountAssetCriteriaBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `loanAccountBillingJob` | loanAccountBillingProcessor → dummyProcessor → loanAccountBillingBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `loanAccountClosure` | loanAccountAutoClosureBatchProcessor | — | — |
| `loanAccountDpdCalcJob` | validateLoanAccountNumbersList → populateUserDetails → loanAccountDpdCalcProcessor → populateUserDetails → loanAccountDpdCalcBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `loanAccountExcessAmountRefund` | setCommonAttributesProcessor → validateTransactionForLoanAccountProcessor → validateDataForLoanAccountExcessAmountRefundProcessor → setPaymentModeProcessor → populateUserDetails → dummyProcessor → ... | createOrUpdateTask, deleteTask, postTransaction | regExp(${create_task})=true; regExp(${do_refund})=true; regExp(${function_code})!REJECT; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${payment_mode})=ACCTWB|OTHBACCT; regExp(${payment_mode})=OTHBACCT … (+6) |
| `loanAccountPartPrepayment` | populateUserDetails → setCommonAttributesProcessor → validatePendingLoanAccountPartPrepaymentProcessor → validateTransactionForLoanAccountProcessor → validateLoanAccountPartPrepaymentProcessor → va... | createOrUpdateTask, deleteTask, getLoanAccountDetails, getOfficeDetails, loanAccountCollection | if(${create_approval_request})=true; if(${create_task})=true; regExp(${do_part_prepayment})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|APPROVE; regExp(${function_code})=REJECT; regExp(${function_code})=RESUBMIT … (+16) |
| `loanAccountRebooking` | populateUserDetails → setCommonAttributesProcessor → executeLoanAccountRebookingProcessor → populateAdditionalAmountDetailsProcessor → populateAdditionalAmountDetailsProcessor → populateAdditionalA... | getLoanAccountDetails, postTransaction | regExp(${excess_int_amt_txn})=true; regExp(${less_int_amt_txn})=true; regExp(${post_txn})=true |
| `loanAccountReopening` | validateDataForLoanAccountReopeningProcessor → validateDocumentDataForGenericDocumentProcessor → populateUserDetails → setCommonAttributesProcessor → dummyProcessor → dummyProcessor → dummyProcesso... | createOrUpdateTask, deleteTask | regExp(${create_task})=true; regExp(${do_reopen})=true; regExp(${function_code})!REJECT; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${reject_reopen})=true; regExp(reason)=OTHERS |
| `loanAccountRestructuring` | populateUserDetails → setCommonAttributesProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → validateDataForLoanAccountRestructuring → ... | createOrUpdateTask, deleteTask | if(${reject_task})=true; regExp(${approve_task})=true; regExp(${create_task})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|APPROVE|REJECT; regExp(${function_code})=REJECT; regExp(${function_sub_code})=DEFAULT … (+12) |
| `loanAccountServicingDocumentEventsJob` | loanAccountServicingDocumentEventsJobProcessor | — | — |
| `loanAccountTransactionReversal` | populateUserDetails → setCommonAttributesProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → validatePendingTxnReversalTaskProcessor → validateTransactionForLoanAccountP... | createOrUpdateTask, deleteTask | if(${approve_task})=true; if(${create_task})=true; if(${reject_task})=true; if(${run_mode})=REAL; if(${validate_task})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|APPROVE … (+8) |
| `loanAdvanceRepayment` | loanAdvanceRepaymentProcessor → loanAdvanceRepaymentBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `loanDeathForeclosure` | populateUserDetails → setCommonAttributesProcessor → valdiateLoanAccountNumberAndStatusForTransactionProcessor → validateDeathForeclosureDocumentsProcessor → validateTransactionForLoanAccountProces... | — | regExp(${function_code})!REJECT; regExp(${function_code})=REJECT; regExp(${function_code})=RE_UPLOAD_DOCUMENT; regExp(${function_code})=STAGE_1; regExp(${function_code})=STAGE_2; regExp(${function_code})=STAGE_3; regExp(${function_code})=STAGE_4; regExp(${function_code})=STAGE_5 … (+12) |
| `loanDisbursementCancellation` | populateUserDetails → setCommonAttributesProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyPro... | getOfficeDetails, getRoleDetailsByUserId, loanAccountCollection, postTransaction | if(${approve_task})=true; if(${collection_deposited})=true; if(${create_task})=true; if(${insurance_opted})=true; if(${insurance_pending})=false; if(${insurance_pending})=true; if(${is_child_loan})=true; if(${reject_task})=true … (+31) |
| `loanPrepayment` | validateTransactionForLoanAccountProcessor → setUserStoryForResponseProcessor → setCommonAttributesProcessor → valdiateLoanAccountNumberAndStatusProcessor → populateUserDetails → fetchSuperDataForF... | getLoanAccountDetails, getNotificationMessageByNotificationCode, getOfficeDetails, postTransaction | regExp(${approve_task})=true; regExp(${create_task})=true; regExp(${delete_task})=true; regExp(${do_prepayment})=true; regExp(${do_validate})=true; regExp(${function_code})!REJECT; regExp(${function_code})=APPROVE; regExp(${function_code})=APPROVE_TASK … (+25) |
| `loanProvisioningPosting` | validateLoanAccountNumbersList → loanProvisioningPostingProcessor → populateUserStoryProcessor | — | — |
| `loanRecurringPaymentBatchApi` | loanRecurringPaymentBatchProcessor | — | regExp(${function_sub_code})=BATCH |
| `loanRepayment` | populateUserDetails → setCommonAttributesProcessor → setUserStoryForResponseProcessor → validateLoanAccountNumberAndStatusForRepayProcessor → validateLoanRepaymentData → autoPopulateChildLoansForRe... | getLoanAccountDetails, getNotificationMessageByNotificationCode, postTransaction, submitApplication | if(${do_npa_reverse_movement})=true; if(${do_repayment_appropriation})=true; if(${repayment_mode})=ACH; if(${repayment_mode})=CASH; if(${repayment_mode})=DIRDR; if(${repayment_mode})=EXCESS_AMT; if(${repayment_mode})=NET_BANKING; if(${repayment_mode})=UPI … (+24) |
| `loanWriteoff` | validateLoanWriteOffDataProcessor → populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → dummyProcessor → dummyProcessor → dummyProcessor → populateUserStoryProcessor → dummyProcessor ... | getLoanAccountDetails, postTransaction, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1; regExp(${post_transaction})=true; regExp(${submit_application})=true … (+2) |
| `penalInterestAccrualBooking` | penalInterestAccrualBookingProcessor → penalInterestAccrualBookingBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `penalInterestAccrualCalculation` | penalInterestAccrualCalculationProcessor → penalInterestAccrualCalculationBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `registerLoanAccountRescheduleEvent` | populateUserDetails → registerLoanAccountRescheduleEventProcessor → dummyProcessor | — | if(${identifier_type})=EMIORTENOR; if(${rescheduling_handling_type})=REDUCE_EMI; if(${rescheduling_handling_type})=REDUCE_TENOR |
| `rescheduleLoanAccountRescheduleBatch` | populateUserDetails → loanAccountRescheduleBatchProcessor → dummyProcessor | — | — |
| `updateCollectionBatchDetails` | updateLoanForeclosureStatus → expirePendingCollectionsProcessor → dummyProcessor | — | regExp(${function_sub_code})=CHALLAN_DETAILS; regExp(${function_sub_code})=EXPIRED |
| `updateLoanAccountPreDisbursementDetails` | populateUserDetails → getLoanAccountByExternalRefNumberProcessor → updateLoanDisbursementModeDetailsProcessor → populateUserStoryProcessor | — | — |
| `validateCustomerAccountDetails` | validateCustomerAccountDetailsProcessor → validateBeneficiaryNameProcessor → dummyProcessor | — | — |
| `validateLMSRestrictedActivitiesForPTrfr` | validateLMSRestrictedActivitiesForPTrfrProcessor | — | — |
| `validateLoanAccountTransaction` | dummyProcessor → setCommonAttributesProcessor → validateTransactionForLoanAccountProcessor → valdiateLoanAccountNumberAndStatusProcessor → validateTransactionForLoanAccountProcessor → validatePendi... | — | regExp(${user_story_permission})=DISB-CNCL-TASK; regExp(${user_story_permission})=EXCS-AMNT-REFND-INIT; regExp(${user_story_permission})=LOAN-PART-PYMT; regExp(${user_story_permission})=LOAN-PRE-PYMT-TASK|LOAN-PRE-PYMT-VIEW; regExp(${user_story_permission})=LOAN-REBKG-INIT; regExp(${user_story_permission})=LOAN-REOPEN-TASK; regExp(${user_story_permission})=LOAN-RESTRCTRN-TASK; regExp(${user_story_permission})=TRNS-REVL-TASK … (+1) |
| `viewBulkTransactionReversalFileStatus` | viewBulkTransactionReversalFileStatusProcessor | — | — |
| `waiveLoanAccountCharges` | validateDataForWaiverChargesProcessor → validateDocumentDataForGenericDocumentProcessor → populateUserDetails → setCommonAttributesProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dum... | deleteTask | regExp(${create_task})=true; regExp(${do_waiver})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${reject_waiver})=true; regExp(${run_mode})=REAL; regExp(${run_mode})=TRIAL … (+4) |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml`
**Owner service:** `novopay-platform-accounting-v2` 
**Root element:** `Accounting`  
**Requests:** 59

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `accountingBankServiceRetryJob` | accountingBankServiceRetryJobProcessor | — | — |
| `bulkFileToSGDispatchDetailsJob` | populateUserDetails → bulkFileToSGDispatchDetailsJobProcessor | — | — |
| `bulkFileToSGFinsallRepaymentJob` | populateUserDetails → bulkFileToSGFinsallRepaymentJobProcessor | — | — |
| `bulkFileToSGForeclosureChargeUpdateJob` | populateUserDetails → bulkFileToSGForeclosureChargeUpdateJobProcessor | — | — |
| `bulkFileToSGManualJournalEntriesJob` | populateUserDetails → bulkFileToSGManualJournalEntriesJobProcessor | — | — |
| `bulkFileToSGNocBlockUnblockJob` | populateUserDetails → bulkFileToSGNocBlockUnblockJobProcessor | — | — |
| `bulkFileToSGSecNpaReverseFeedFileJob` | bulkFileToSGSecNpaReverseFeedFileJobProcessor | — | — |
| `bulkOutboundSecNpaReverseFeedFileJob` | outboundSecNpaStatusFileJobProcessor | — | — |
| `bulkSGToDispatchDetailsJob` | bulkSGToDispatchDetailsJobProcessor | — | — |
| `bulkSGToFinsallRepaymentJob` | populateUserDetails → bulkSGToFinsallRepaymentJobProcessor | — | — |
| `bulkSGToForeclosureChargeUpdateJob` | bulkSGToForeclosureChargeUpdateJobProcessor | — | — |
| `bulkSGToManualJournalEntriesJob` | populateUserDetails → bulkSGToManualJournalEntriesJobProcessor | — | — |
| `bulkSGToNocBlockUnblockJob` | bulkSGToNocBlockUnblockJobProcessor | — | — |
| `bulkSGToSecNpaReverseFeedFileJob` | bulkSGToSecNpaReverseFeedFileJobProcessor | — | — |
| `createOrUpdateGeneralLedger` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForAllowedTransactionType → checkDataForCreateGeneralLedger → fetchBulkUniqueMasterData → mfiSendForApprovalCreateGeneralLedg... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `createOrUpdateLoanAccount` | populateCurrentDateProcessor → throwNovopayFatalExceptionProcessor → validateLoanAccountDetailsProcessor → customValidateDisbursementRepaymentAccountDetailsProcessor → populateRepaymentDetailsProce... | createActorAccountDetails, getCustomerDetails, getOfficeDetails | if(${function_sub_code})=UPDATE; regExp(${SKIP_PLATFORM_INTEREST_CALCULATION})=FALSE; regExp(${errorCode})!\$\{errorCode\}; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${interest_rate})=^0*[1-9]\d{0,1}(\.\d{1,6}){0,1}$; regExp(${run_mode})=REAL |
| `createOrUpdateProductScheme` | oneToOneMappingProductSchemeProcessor → getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForCreateProductSchemeProcessor → checkDataForNonTransactionalCharges → checkPricingD... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `disburseLoan` | dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → populateCurrentDateProcessor → dummyProcessor → dummyProcessor → populateExpec... | createOrUpdateLoanAccount, getLoanAccountDetails | if(${disbursement_mode})=CASH; if(${upfront_interest_applicable})=true; regExp(${IS_BANK_CALL_FAILED})=FALSE; regExp(${IS_BANK_CALL_FAILED})=TRUE; regExp(${IS_LMS_FAILED})=FALSE; regExp(${IS_LMS_FAILED})=TRUE; regExp(${LRS_FAILED})=FALSE; regExp(${LRS_FAILED})=TRUE … (+33) |
| `doGenericSyncSTPBankNEFNeftCallBack` | doGenericSyncSTPBankNeftCallBackProcessor | — | — |
| `doGenericSyncSTPBankNEINeftCallBack` | doGenericSyncSTPBankNeftCallBackProcessor | — | — |
| `downloadDispatchDetailsUploadedFile` | downloadDispatchDetailsUploadedFileProcessor | — | — |
| `downloadFinsallRepaymentUploadedFile` | downloadFinsallRepaymentUploadedFileProcessor | — | — |
| `downloadForeclosureChargeUpdateUploadedFile` | downloadForeclosureChargeUpdateUploadedFileProcessor | — | — |
| `downloadManualJournalEntriesUploadedFile` | downloadManualJournalEntriesUploadedFileProcessor | — | — |
| `downloadNocBlockUnblockUploadedFile` | downloadNocBlockUnblockUploadedFileProcessor | — | — |
| `extractCasaBalanceFor180ProductCode` | extractCasaBalanceFor180ProductCodeBatchProcessor | — | — |
| `extractCasaBalanceFor182ProductCode` | extractCasaBalanceFor182ProductCodeBatchProcessor | — | — |
| `fetchLoanAccountsForCustomer` | fetchCustomerAccountNumberProcessor | — | — |
| `generateNocFileJob` | generateNocFileJobProcessor | — | — |
| `generatePostEODReports` | generatePostEODReportsBatchService | — | — |
| `generateTBZeroisationReport` | generateZeroisationReportBatchService | — | — |
| `getEffectiveInterestRateForProductScheme` | getInterestSetupDetailsForProductSchemeProcessor → getEffectiveInterestRateForInterestSetupCodeProcessor → populateInterestDetailsForAccountProcessor → fetchBulkUniqueMasterData | — | — |
| `getEntryLookupCodesOfTransaction` | getEntryLookupCodesOfTransactionForPriceProcessor → getEntryLookupCodesOfNonTransactionForPriceProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | regExp(${function_code})=NON_TXN_PRICE; regExp(${function_code})=PRICE |
| `getForeclosureChargeDetails` | getForeclosureChargeDetailsProcessor → populateUserStoryProcessor | — | — |
| `getGeneralLedgerDetails` | mfiGetGeneralLedgerDetailsProcessor → fetchBulkUniqueMasterData → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getLoanAccountApplicableCharges` | getLoanAccountApplicableChargesProcessor → populateUserStoryProcessor | — | — |
| `getLoanAccountAppliedCharges` | getLoanAccountAppliedChargesProcessor → populateUserStoryProcessor | — | — |
| `getLoanAccountDetails` | getLoanAccountByExternalRefNumberProcessor → getLoanAccountDetailsProcessor → customPopulateDisbursementRepaymentAccountDetailsProcessor → getAccountInterestDetailsProcessor → fetchBulkUniqueMaster... | — | if(${function_sub_code})=DEFAULT; if(${function_sub_code})=ENQUIRY |
| `getLoanAccountNocDetails` | getLoanAccountNocDetailsProcessor → generateLoanAccountNocDetailsProcessor → populateUserStoryProcessor | — | — |
| `getLoanProductDetails` | getLoanProductByProductSchemeIdProcessor → getLatestLoanProductIdForProductId → getLoanProductDetailsProcessor → getProductSchemeForLoanProductProcessor → getProductSchemeInsuranceDetailsProcessor ... | — | regExp(${function_code})=BYSCHEMEID; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|LATEST|BYSCHEMEID; regExp(${function_code})=LATEST|MFI; regExp(${function_code})=MFI |
| `getLoanProductList` | getLoanProductListProcessor → getProductCodeNameListProcessor → getAvailableLoanProductListProcessor → getEmployeeAndOfficeCommonServiceableProductListProcessor → populateUserStoryProcessor | — | regExp(${function_sub_code})=AVAILABLE_LOAN_PRODUCTS; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=GET_EMP_AND_OFC_COM_SVCBL_PRODS; regExp(${function_sub_code})=GET_PRODUCT_CODE_NAME |
| `getProductSchemeDetails` | getProductSchemeDetailsProcessor → fetchBulkUniqueMasterDataExt → fetchBulkUniqueMasterData → getProductSchemePricingDetailsProcessor → populateMasterDataInProductSchemePricingDetailsProcessor → ge... | getNotificationMessageByNotificationCode | — |
| `getProductSchemeList` | getProductSchemeListProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `loanRepayment` | dummyProcessor → populateUserDetails → setCommonAttributesProcessor → validateLoanAccountNumberAndStatusForRepayProcessor → validateLoanRepaymentData → autoPopulateChildLoansForRepaymentProcessor →... | postTransaction | if(${do_npa_reverse_movement})=true; if(${do_repayment_appropriation})=true; if(${repayment_mode})=EXCESS_AMT; regExp(${channel_code},${client_code})=novosli,novosli; regExp(${client_code})!novosli; regExp(${is_eligible_for_auto_closure})=true; regExp(${loan_account_status})=CLOSED; regExp(${repayment_mode})!DIRDR … (+5) |
| `loanRepaymentInquiry` | fetchLoanRepaymentInquiryDetailsProcessor → dummyProcessor | — | regExp(${channel_code},${client_code})=novosli,novosli |
| `runBODJobs` | populateUserDetails → mfiRunBODJobsProcessor → populateUserStoryProcessor | — | — |
| `runEODJobs` | populateUserDetails → mfiRunEODJobsProcessor → populateUserStoryProcessor → rejectExpiredPrepaymentTasksProcessor → populateOpeningBalanceProcessor → populateTrialBalanceProcessor → populateClosing... | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=POST_EOD; regExp(${function_code})=REPORT_GEN |
| `runSecNpaBulkUploadJob` | runSecNpaBulkJobProcessor | — | — |
| `trialBalanceCalculation` | trialBalanceCalculationBatchService | — | — |
| `trialBalanceZeroisationJob` | trialBalanceZeroisationBatchService | — | — |
| `updateDisbursementAccountDetails` | updateDisbursementAccountDetailsProcessor → populateUserStoryProcessor | — | — |
| `updateGeneralLedgerStatus` | getUserDetailsPostProcessor → dummyProcessor → dummyProcessor → getUseCaseDetailsPostProcessor → checkDataForUpdateGeneralLedgerStatus → fetchBulkUniqueMasterData → mfiSendForApprovalUpdateGeneralL... | getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code}_${function_sub_code})=DEFAULT_ACTIVATE; regExp(${function_code}_${function_sub_code})=DEFAULT_DEACTIVATE; regExp(${function_sub_code})=ACTIVATE; regExp(${function_sub_code})=ACTIVATE|DEACTIVATE; regExp(${function_sub_code})=DEACTIVATE; regExp(${maker_checker_enabled})=0 … (+6) |
| `updateLoanAccountDerivedFieldsJob` | loanAccountDerivedFieldsJobProcessor | — | — |
| `updateLoanAccountDerivedFieldsMonthlyJob` | loanAccountDerivedFieldsMonthlyJobProcessor | — | — |
| `viewBulkDispatchDetailsFileStatus` | viewBulkDispatchDetailsFileStatusProcessor | — | — |
| `viewBulkFinsallRepaymentFileStatus` | viewBulkFinsallRepaymentFileStatusProcessor | — | — |
| `viewBulkForeclosureChargeUpdateFileStatus` | viewBulkForeclosureChargeUpdateFileStatusProcessor | — | — |
| `viewBulkManualJournalEntriesFileStatus` | viewBulkManualJournalEntriesFileStatusProcessor | — | — |
| `viewBulkNocBlockUnblockFileStatus` | viewBulkNocBlockUnblockFileStatusProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_accounting_definition_orc.xml`
**Owner service:** `novopay-platform-accounting-v2` 
**Root element:** `Accounting`  
**Requests:** 12

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateAccountingRules` | populateUserDetails → validateAccountingRulesProcessor → validateTransactionCatalogueForAccountingRuleProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateCurrentDateProcessor → dummyPro... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=CREATE; if(${function_sub_code})=UPDATE; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1 … (+21) |
| `createOrUpdatePlaceholderMaster` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → checkDataForPlaceholderMaster → constructRequestDataForApproval → deleteDraftProcessor → populateUserStoryProcessor → checkDataForP... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+6) |
| `createOrUpdatePlaceholderMasterListForProductType` | populateUserDetails → validateProductTypeForPlaceholderMasterProcessor → validatePlaceholderMasterListProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateCurrentDateProcessor → dummyPro... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=CREATE; if(${function_sub_code})=UPDATE; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1 … (+21) |
| `createOrUpdateTransactionCatalogue` | populateUserDetails → validateProductTypeForTransactionCatalogueProcessor → validateTransactionCatalogueDetailsProcessor → fetchBulkUniqueMasterData → getMakerCheckerEnabledForUseCaseProcessor → po... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=CREATE; if(${function_sub_code})=UPDATE; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1 … (+21) |
| `deleteAccountingRule` | populateUserDetails → validateDeleteTransactionAccountingRuleProcessor → populateTransactionAccountingRuleByTransactionTypeProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateCurrentDat... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1 |
| `deletePlaceholderMaster` | populateUserDetails → checkDataForLogicalDeletePlaceholderMasterProcessor → getMakerCheckerEnabledForUseCaseProcessor → constructRequestDataForApproval → populateUserStoryProcessor → logicalDeleteP... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deletePlaceholderMasterListForProductType` | populateUserDetails → validateProductTypeForPlaceholderMasterProcessor → populatePlaceholderMasterMappingForProductTypeProcessor → validateForDeletePlaceholderMasterListProcessor → getMakerCheckerE... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1 |
| `deleteTransactionCatalogue` | populateUserDetails → validateProductTypeForTransactionCatalogueProcessor → populateTransactionCatalogueMappingForProductTypeProcessor → validateForDeleteTransactionCatalogueProcessor → getMakerChe... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1 |
| `getAccountingRuleList` | getTransactionAccountingRuleListProcessor → getTransactionAccountingRuleGroupByProductTypeProcessor → populateUserStoryProcessor | — | if(${function_sub_code})=DEFAULT; if(${function_sub_code})=GROUP_BY_PRODUCT_TYPE |
| `getPlaceholderMasterDetails` | getPlaceholderMasterDetailsProcessor → dummyProcessor | — | — |
| `getPlaceholderMasterList` | getPlaceholderMasterListProcessor → getPlaceholderMasterListGroupedByProductTypeProcessor → populateUserStoryProcessor | — | if(${function_sub_code})=DEFAULT; if(${function_sub_code})=GROUP_BY_PRODUCT_TYPE |
| `getTransactionCatalogueList` | getTransactionCatalogueListProcessor → getTransactionCatalogueListGroupedByProductTypeProcessor → getTransactionCatalogueListGroupedByProductTypeTranTypeProcessor → populateUserStoryProcessor | — | if(${function_sub_code})=DEFAULT; if(${function_sub_code})=GROUP_BY_PRODUCT_TYPE; if(${function_sub_code})=GROUP_BY_PRODUCT_TYPE_TRAN_TYPE |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml`
**Owner service:** `novopay-platform-accounting-v2` 
**Root element:** `Accounting`  
**Requests:** 12

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `doGLTransfer` | setCommonAttributesProcessor → getTransactionCatalogueIdProcessor → doGLTransferProcessor | — | — |
| `executeLMSPortfolioTransfer` | setCommonAttributesProcessor → executeLMSPortfolioTransferProcessor | — | — |
| `getAccountBalances` | getAccountBalancesProcessor | — | — |
| `getAccountStatement` | getAccountStatementProcessor | — | — |
| `getCurrencyMasterDetails` | getCurrencyMasterDetailsProcessor | — | regExp(${function_sub_code})=BY_CODE; regExp(${function_sub_code})=BY_ID |
| `getLoanAccountStatement` | getLoanAccountStatementProcessor → getLoanAccountExportTransactionsProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=EXPORT |
| `getTransactionPartitionDetails` | getTransactionPartitionDetailsProcessor | — | — |
| `glBalanceZeroisation` | populateUserDetails → populateCurrentDateProcessor → setCommonAttributesProcessor → clientReferenceNumberDedupProcessor → validateAndPopulateDataForGLZeroisation → getTransactionCatalogueIdProcesso... | — | regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=TRANSACTION |
| `postManualJournalEntry` | populateUserDetails → populateCurrentDateProcessor → setCommonAttributesProcessor → dummyProcessor → validateTransactionForLoanAccountProcessor → getUseCaseDetailsPostProcessor → checkDataForManual... | getUseCaseDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=BULK; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=TRANSACTION; regExp(${maker_checker_enabled})=0 … (+7) |
| `postTransaction` | validateTransactionDataProcessor → populateAdditionalInformationProcessor → populateAndValidateAccountDetailsProcessor → populateAdditionalAmountProcessor → clientReferenceNumberDedupProcessor → ge... | — | regExp(${run_mode})=REAL; regExp(${run_mode})=TRIAL |
| `reverseManualJournalEntry` | populateUserDetails → populateCurrentDateProcessor → setCommonAttributesProcessor → validateTransactionForLoanAccountProcessor → getUseCaseDetailsPostProcessor → populateDataForReverseManualJournal... | getUseCaseDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=TRANSACTION; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1; regExp(${manual_journal_entry_on})=INTRA_BRNH … (+1) |
| `reverseTransaction` | reverseTransactionProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 80

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `addOrRemoveHierarchyElementEntityMapping` | addHierarchyElementEntityMappingProcessor → dummyProcessor → removeHierarchyElementEntityMappingProcessor → dummyProcessor | — | regExp(${function_code})=ADD; regExp(${function_code})=REMOVE |
| `agentDedup` | agentDedupProcessor | — | — |
| `agentLogin` | getUserDetailsForLoginProcessor → checkEmployeeStatusProcessor → isMPINSetProcessor → generateOTPProcessor → checkForNewDeviceProcessor → dummyProcessor → checkForNewDeviceProcessor → dummyProcesso... | — | if(${isCaptchaEnable})=true; regExp(${byod})=FALSE; regExp(${byod})=TRUE; regExp(${channel_code})!WEBAPP; regExp(${channel_code})=WEBAPP; regExp(${function_sub_code})=CONFIRM; regExp(${function_sub_code})=INITIATE; regExp(${is_device_registered})=FALSE … (+18) |
| `assignInventoryItem` | populateUserDetails → getInventoryItemDetailsProcessor → populateInventoryAssigneeDetails → getMakerCheckerEnabledForUseCaseProcessor → assignInventoryItemApprovalPreProcessor → deleteDraftProcesso... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `authenticateUser` | validateAuthTypeProcessor → validateActorTypeIdProcessor → getActorUserProcessor → throwNovopayFatalExceptionProcessor → dummyProcessor → authenticateUserForLoginProcessor → dummyProcessor | — | if(${auth_type})=MPIN; regExp(${actor_user_id})![0-9]{1,10} |
| `bulkFileToSGOfficeUpsertJob` | populateUserDetails → bulkFileToSGOfficeUpsertJobProcessor | — | — |
| `bulkSGToOfficeUpsertJob` | bulkSGToOfficeUpsertJobProcessor | — | — |
| `changePassword` | authenticateAgentProcessor → authenticateUserProcessor → changeAuthValueProcessor → saveAuthDetailsForLoginProcessor → dummyProcessor | — | regExp(${channel_code})=AGENTAPP; regExp(${channel_code})=NOVOPAY |
| `checkExternalIdExists` | — | — | — |
| `clearFCMDetailsByUserId` | clearFCMDetailsByUserIdProcessor | — | — |
| `createActorAccountDetails` | getCustomerActorProcessor → createActorAccountDataProcessor | — | regExp(${account_type})=INT; regExp(${actor_type})=CUSTOMER; regExp(${same_as_parent})=false |
| `createOrUpdateDevice` | createDeviceProcessor → createMobileDeviceProcessor → dummyProcessor → updateDeviceProcessor → updateMobileDeviceProcessor → dummyProcessor | — | regExp(${function_code})=MOBILE; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `createOrUpdateEmployee` | dummyProcessor → populateTenantCorporateDetailsProcessor → getEmployeeUserValidationFlagProcessor → getUserCorporateProcessor → validateEmployeeRoleDetailsProcessor → checkPreferredLanguageProcesso... | createUserRoleMapping, submitApplication, updateUserRoleMapping, verifyDocuments | regExp(${create_user_during_update})=false; regExp(${create_user_during_update})=true; regExp(${employee_user_validation_flag})=false; regExp(${employee_user_validation_flag})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=RESUBMIT … (+62) |
| `createOrUpdateHierarchyElement` | createHierarchyElementProcessor → dummyProcessor → updateHierarchyElementProcessor → dummyProcessor | — | regExp(${function_code})=CREATE; regExp(${function_code})=UPDATE |
| `createOrUpdateInventoryItem` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → addingTypeProcessor → dummyProcessor → generateInventoryItemNumberProcessor → validateForCreateInventoryItemProcessor → checkCorpor... | getNotificationMessageByNotificationCode, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${inv_item_type})=INV_ITM_TYP_MOB|INV_ITM_TYP_MATM; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+19) |
| `createOrUpdateOffice` | populateUserDetails → validateForCreateOffice → fetchBulkUniqueMasterData → validateOfficeServiceableProductsProcessor → checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → getMakerChecke... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT|MFI_COLLECTION; regExp(${function_code})=MFI_COLLECTION; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+15) |
| `createUser` | createUserProcessor → createAddressProcessor → createUserAddressProcessor → createContactDetailProcessor → createUserContactDetailProcessor → createUserHandleProcessor → createUserOfficeProcessor →... | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `deleteCorporate` | dummyProcessor → deleteCachedKeysProcessor | — | — |
| `deleteDevice` | logicalDeleteDeviceProcessor → logicalDeleteMobileDeviceProcessor | — | regExp(${function_code})=MOBILE |
| `deleteEmployee` | logicalDeleteEmployeeProcessor → logicalDeleteEmploymentDetailsProcessor → logicalDeleteActorAddressProcessor → logicalDeleteAddressProcessor → logicalDeleteActorContactDetailProcessor → logicalDel... | — | — |
| `deleteInventoryItem` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → validateForDeleteInventoryItemProcessor → getInventoryItemDetailsProcessor → fetchBulkUniqueMasterData → createApprovalDataForDelet... | getNotificationMessageByNotificationCode, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteOffice` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → validateForDeleteOfficeProcessor → getOfficeDetailsProcessor → getOfficeContactDetailProcessor → getContactDetailProcessor → getOff... | submitApplication, updateCollectionOfficeInfo | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `deleteUser` | logicalDeleteUserProcessor → logicalDeleteUserContactDetailProcessor | — | — |
| `downloadOfficeUpsertUploadedFile` | downloadOfficeUpsertUploadedFileProcessor | — | — |
| `fetchUserCorporateAgentIdInternalAPI` | checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor | — | — |
| `forgotAuthValue` | getUserDetailsForLoginProcessor → checkForNewDeviceProcessor → generateOTPProcessor → dummyProcessor → byodFailureProcessor → generateOTPProcessor → dummyProcessor → getActorDocumentProcessor → get... | — | regExp(${byod})=FALSE; regExp(${byod})=TRUE; regExp(${channel_code})!WEBAPP; regExp(${channel_code})=WEBAPP; regExp(${function_code})=CONFIRM; regExp(${function_code})=CONFIRM_REGISTER; regExp(${function_code})=CONFIRM|CONFIRM_REGISTER; regExp(${function_code})=INITIATE … (+6) |
| `forgotPassword` | getMockDataForDeviceRegProcessor → getUserDetailByDeviceReferenceId → getActorContactDetailProcessor → getContactDetailProcessor → validateDeviceDetailsProcessor → getUserDetailsForLoginProcessor →... | — | if(${channel_code})=ANDROID; if(${function_code})=CONFIRM; if(${isCaptchaEnable})=true; regExp(${function_code})!CONFIRM; regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE|INI_FORGOT_MPIN|INI_EXPIRE_MPIN|INI_SETUP_MPIN |
| `forgotPin` | validateHandleValueForAgentEmployeeProcessor → generateOTPProcessor → dummyProcessor → validateOTPProcessor → generateAuthValueProcessor → sendSMSProcessor → updateMpinForAgentProcessor → dummyProc... | — | regExp(${function_code})=INITIATE; regExp(${function_code})=VALIDATE |
| `getAccountsByCustomerId` | getCustomerActorProcessor → getActorAccountNumbersProcessor | — | — |
| `getActorDetailsForAccount` | getActorDetailsForAccountProcessor → getCustomerFromActorProcessor | — | regExp(${account_type})=INT; regExp(${actor_type})=CUSTOMER|GROUP |
| `getChildHierarchyElements` | validateAndPopulateElementDetails → populateHierarchyElementsByLevelProcessor → dummyProcessor | — | — |
| `getCustomerBasicDetails` | getCustomerDetailsForExternalIdProcessor | — | if(${function_sub_code})=EXTERNAL_ID |
| `getCustomersForExternalIds` | — | — | — |
| `getDemoAuthValue` | demoAuthValue | — | — |
| `getDeviceDetails` | getDeviceDetailsProcessor → getMobileDeviceDetailsProcessor → getMappingDetailsProcessor → dummyProcessor | — | regExp(${function_code})=MOBILE |
| `getDeviceList` | getDeviceListProcessor → getMobileDeviceListProcessor → dummyProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=MOBILE |
| `getEmployeeDetails` | checkCorporateEmployeeIdProcessor → getEmployeeActorProcessor → getActorUserProcessor → getEmployeeDetailsProcessor → getEmploymentDetailsProcessor → dummyProcessor → getUserRoleDetailsProcessor → ... | — | if(${employee_status_change_reason})=PARENT_BLOCKED; if(${employee_status_change_reason})=PARENT_DEACTIVATED; if(${employee_status_change_reason})=PARENT_UNBLOCKED; if(${employee_status})=ACTIVE; if(${employee_status})=BLOCKED; if(${employee_status})=DEACTIVATED; regExp(${employee_status_change_reason})!; regExp(${employee_status_change_reason})!PARENT_BLOCKED … (+3) |
| `getEmployeeList` | checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → getEmployeeListProcessor → getClusterLinkedToEmployeeListProcessor → populateUserStoryProcessor | — | if(${function_sub_code})=SCOPED |
| `getEmployeeListWithRoles` | checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → getEmployeeListProcessor → getEmployeeListWithRolesProcessor → getClusterLinkedToEmployeeListProcessor → populateUserStoryProcessor | — | if(${function_sub_code})=SCOPED |
| `getEmployeeServiceableOffices` | dummyProcessor → validateGetEmployeeServiceableOffices → getEmployeeServiceableOfficesProcessor → dummyProcessor | — | if(${function_sub_code})=STATE_FILTER |
| `getEncryptionKey` | getPublicKeyProcessor → dummyProcessor | — | — |
| `getEntityGeoHierarchyDetails` | getGeoHierarchyElementByOfficeProcessor → dummyProcessor | — | regExp(${entity_type})=OFFICE |
| `getFCMTokens` | getFCMTokensProcessor | — | — |
| `getGeoHierarchyEntityDetails` | getOfficeListByGeoHierarchyElementProcessor → dummyProcessor | — | regExp(${entity_type})=OFFICE |
| `getHierarchyElementNamesByIds` | getHierarchyElementNamesByIdsProcessor | — | — |
| `getHierarchyForNLevels` | getHierarchyForNLevelsProcessor | — | — |
| `getHierarchyLevels` | getTemplateDetailProcessor → populateHierarchyLevelsProcessor → populateHierarchyRootElementsProcessor → dummyProcessor | — | — |
| `getInventoryBrandList` | getInventoryBrandListProcessor | — | — |
| `getInventoryBrandList` | getInventoryBrandListProcessor → setUserStoryForResponseCommonProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getInventoryItemDetails` | getInventoryItemDetailsProcessor → getInventoryAssignmentsDetailsProcessor → fetchBulkUniqueMasterData → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getInventoryItemList` | getInventoryItemListProcessor → setUserStoryForResponseProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getInventoryManufacturerList` | getInventoryManufacturerListProcessor | — | — |
| `getInventoryManufacturerList` | getInventoryManufacturerListProcessor → setUserStoryForResponseCommonProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getInventoryProductList` | getInventoryProductListProcessor | — | — |
| `getInventoryProductList` | getInventoryProductListProcessor → setUserStoryForResponseCommonProcessor → dummyProcessor | getNotificationMessageByNotificationCode | — |
| `getOfficeCodeAndNameByIds` | getOfficeListByIdsProcessor → populateUserStoryProcessor | — | — |
| `getOfficeDetails` | getOfficeDetailsByBranchCodeProcessor → getOfficeNameOnlyProcessor → getOfficeDetailsProcessor → getOfficeContactDetailProcessor → getContactDetailProcessor → getOfficeAddressProcessor → getAddress... | — | regExp(${function_sub_code})=BRANCH_CODE; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT|BRANCH_CODE; regExp(${function_sub_code})=OFFICE_NAME_ONLY |
| `getOfficeIdByNameOrFormattedId` | — | — | — |
| `getOfficeIdByNameOrFormattedId` | — | — | — |
| `getOfficeList` | checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → getOfficeListProcessor → getOfficeListUnderUserProcessor → getOfficeListUnderUserProcessor → populateLinkedOfficesProcessor → getOffice... | — | if(${function_sub_code})=GET_OFC_BY_LVL_AND_USR_ID; if(${function_sub_code})=GET_PARENT_OFFICES_BY_LVL; if(${function_sub_code})=SCOPED; regExp(${function_sub_code})=COLLECTIONS; regExp(${function_sub_code})=COLLECTIONS|VIEW_LINKED_AGENCY_OFFICES; regExp(${function_sub_code})=DEFAULT|SCOPED; regExp(${function_sub_code})=USER_ID … (+2) |
| `getParentHierarchyList` | getParentHierarchyListProcessor → dummyProcessor | — | regExp(${function_sub_code})=BY_ELEMENT; regExp(${function_sub_code})=BY_ENTITY |
| `getStateDistrictVtcList` | getStateDistrictVtcListProcessor → getStateDistrictVtcDetailByVtcIdProcessor | — | if(${function_sub_code})=DEFAULT; if(${function_sub_code})=VTC |
| `getUserDetails` | getUserDetailsByHandleValueProcessor → getUserDetailsProcessor → getUserAddressMappingProcessor → getAddressDetailsProcessor → getUserContactDetailProcessor → getContactDetailProcessor → getUserOff... | — | regExp(${function_sub_code})!HANDLE_VALUE; regExp(${function_sub_code})=HANDLE_VALUE |
| `getUserList` | listUserProcessor | — | — |
| `getVANDetails` | getVANDetailsProcessor → getCorporateFromActorProcessor → getCustomerFromActorProcessor | — | regExp(${actor_type})=CORPORATE; regExp(${actor_type})=CUSTOMER |
| `login` | getConfigValueProcessor → getMockDataForDeviceRegProcessor → getUserDetailByDeviceReferenceId → getActorContactDetailProcessor → getContactDetailProcessor → validateDeviceDetailsProcessor → validat... | — | if(${channel_code})=ANDROID; if(${channel_code})=AWEB; if(${function_sub_code})=VALIDATE_OTP; if(${generate_otp})=true; if(${lock_user})=true; if(${password_validated})=false; if(${password_validated})=true; if(${user_authenticated})=true … (+7) |
| `logout` | userLogoutProcessor → logoutPostProcessingProcessor | — | — |
| `mapDevice` | createUserDeviceMappingProcessor → createOfficeDeviceMappingProcessor → dummyProcessor → logicalDeleteUserDeviceMappingProcessor → logicalDeleteOfficeDeviceMappingProcessor → dummyProcessor | — | regExp(${function_code})=DEMAP; regExp(${function_code})=MAP; regExp(${function_sub_code})=OFFICE; regExp(${function_sub_code})=UPDATE; regExp(${function_sub_code})=USER |
| `registerDevice` | getUserDetailsForLoginProcessor → checkEmployeeStatusProcessor → generateOTPProcessor → dummyProcessor → validateOTPProcessor → registerDeviceProcessor → fetchBulkUniqueMasterData → dummyProcessor ... | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE |
| `setAuthValue` | getMockDataForDeviceRegProcessor → getUserDetailByDeviceReferenceId → getUserDetailByDeviceReferenceId → getActorContactDetailProcessor → getContactDetailProcessor → validateDeviceDetailsProcessor ... | — | if(${channel_code})=ANDROID |
| `unassignInventoryItem` | populateUserDetails → getInventoryItemDetailsProcessor → getInventoryAssignmentsDetailsProcessor → getMakerCheckerEnabledForUseCaseProcessor → unassignInventoryItemApprovalPreProcessor → deleteDraf... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `updateEmployeeStatus` | populateUserDetails → checkTenantEmployeeIdProcessor → getUserCorporateProcessor → populateActorStatusConfigProcessor → dummyProcessor → dummyProcessor → dummyProcessor → getMakerCheckerEnabledForU... | submitApplication | if(${employee_status_change_reason})=PARENT_BLOCKED; if(${employee_status})=ACTIVE; if(${employee_status})=BLOCKED; if(${employee_status})=DEACTIVATED; if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=BLOCK … (+41) |
| `updateFCMTokenForUser` | checkDataForFCMTokenUpdateProcessor | — | — |
| `updateHierarchyElementEntityMapping` | bulkModifyHierarchyElementEntityMappingProcessor → dummyProcessor | — | — |
| `validateEmployeeByRoleCode` | validateEmployeeByRoleCodeProcessor | — | — |
| `validateOffice` | validateCPUOfficeMappingProcessor | — | if(${function_code})=CPU_OFFICE |
| `verifyNRLMStateCode` | verifyNRLMStateCodeProcessor | — | — |
| `verifyStateCode` | verifyStateCodeProcessor | — | — |
| `verifyUserHandle` | verifyUserHandleProcessor | — | — |
| `viewBulkOfficeUpsertFileStatus` | viewBulkOfficeUpsertFileStatusProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/ServiceOrchestrationXML_idfc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 1

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `getInvertoryDetailsByAttribute` | getInvertoryDetailsByAttributeProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/bp_card_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 7

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `getCardDetails` | getCustomerDetailsProcessor → customGetCardDetailsProcessor → getActorContactDetailProcessor → getContactDetailProcessor → generateOTPProcessor → validateOTPProcessor → viewCardDetailsProcessor | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=VIEW |
| `getCardPinEncryptionKey` | customGetCardPinEncryptionKeyProcessor | — | — |
| `linkCard` | getCustomerIdProcessor → getCustomerDetailsProcessor → getActorContactDetailProcessor → getContactDetailProcessor → generateOTPProcessor → validateOTPProcessor → customLinkNewCardProcessor → equita... | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE; regExp(${function_sub_code})!ONBOARDING; regExp(${function_sub_code})=ONBOARDING |
| `lockOrUnlockCard` | getCustomerDetailsProcessor → customGetCardDetailsProcessor → getUserDetailsFromCustomerProcessor → authenticateUserForLoginProcessor → customLockCardProcessor → fetchBulkUniqueMasterData → equitas... | — | regExp(${function_code})=LOCK; regExp(${function_code})=UNLOCK |
| `replaceCard` | getCustomerDetailsProcessor → customGetCardDetailsForReplaceCardProcessor → getActorContactDetailProcessor → getContactDetailProcessor → generateOTPProcessor → validateOTPProcessor → equitasReplace... | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE |
| `requestNewCard` | getCustomerDetailsProcessor → getActorContactDetailProcessor → getContactDetailProcessor → generateOTPProcessor → validateOTPProcessor → customRequestNewCardProcessor → customGetCardDetailsProcesso... | cardReplacementChargeTransaction | regExp(${card_status})!BLOCKED; regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE |
| `setCardPin` | getCustomerDetailsProcessor → validateSetCardPinDetailsProcessor → getActorContactDetailProcessor → getContactDetailProcessor → generateOTPProcessor → validateOTPProcessor → customGetCardDetailsPro... | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/bp_corporate_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 3

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateCorporate` | populateTenantParentCorporateIdCustomProcessor → dummyProcessor → checkCorporateCodeProcessor → populateParentActorId → createActorProcessor → createContactDetailProcessor → createActorContactDetai... | verifyDocuments | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT; regExp(${verify_documents})=YES |
| `getCorporateDetails` | checkCorporateIdProcessor → populateTenantCorporateDetailsProcessor → dummyProcessor → getCorporateProcessor → getCorporateProcessor → getCorporateDetailsProcessor → dummyProcessor → getActorContac... | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT|ALL; regExp(${function_sub_code})=TENANT |
| `getCorporateList` | getCorporateListProcessor → dummyProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/bp_customer_batch_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 2

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `customerFileGenerationBatch` | customerFileGenerationProcessor | — | — |
| `customerFileProcessBatch` | customerFileProcessProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/bp_customer_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 4

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateCustomer` | customPopulateHandleDetailsProcessor → checkCorporateIdProcessor → createActorProcessor → createAddressProcessor → createActorAddressProcessor → createContactDetailProcessor → createActorContactDet... | createUserRoleMapping, registerRemitter, verifyDocuments | regExp(${customer_status})!REJECTED|REGISTERED; regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT; regExp(${is_pan})!TRUE; regExp(${is_pan})=TRUE; regExp(${verify_documents})=YES |
| `customerContactSync` | customerContactSyncProcessor | — | — |
| `getCustomerDetails` | getUserDetailsForLoginProcessor → getCustomerDetailsForLoginProcessor → getCustomerDetailsProcessor → getActorAddressProcessor → getAddressDetailsProcessor → getActorContactDetailProcessor → getCon... | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=HANDLE; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=TRANSACTION |
| `processTimeOutForCustomer` | processTimeOutForCustomerProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/bp_login_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 7

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `changeAuthValue` | getUserDetailsForLoginProcessor → authenticateUserForLoginProcessor → setAuthValueProcessor | — | — |
| `customerLogin` | getUserDetailsForLoginProcessor → getCustomerDetailsForLoginProcessor → throwNovopayFatalExceptionProcessor → dummyProcessor → generateOTPProcessor → dummyProcessor → dummyProcessor → authenticateU... | — | regExp(${handle_type})=MSISDN; regExp(${is_device_registered})!FALSE; regExp(${is_device_registered})=FALSE; regExp(${run_mode})=REAL; regExp(${run_mode})=TRIAL; regExp(${status})!APPROVED|ACTIVE; regExp(${status})=ACTIVE; regExp(${status})=APPROVED … (+1) |
| `forgotAuthValue` | getUserDetailsForLoginProcessor → getCustomerDetailsForLoginProcessor → throwNovopayFatalExceptionProcessor → dummyProcessor → generateOTPProcessor → getActorDocumentProcessor → getDocumentGenericP... | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE; regExp(${handle_type})=MSISDN; regExp(${status})!APPROVED|ACTIVE |
| `getEncryptionKey` | getPublicKeyProcessor → dummyProcessor | — | — |
| `registerDevice` | getUserDetailsForLoginProcessor → dummyProcessor → validateOTPProcessor → registerDeviceProcessor → dummyProcessor | — | regExp(${function_code})=CONFIRM |
| `setAuthValue` | getUserDetailsForLoginProcessor → setAuthValueProcessor → activateCustomerFromActorIdProcessor → getCustomerDetailsForLoginProcessor → dummyProcessor | — | — |
| `verifyHandle` | getUserDetailsForLoginProcessor → dummyProcessor → generateOTPProcessor → dummyProcessor → validateOTPProcessor → registerDeviceProcessor | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE; regExp(${handle_type})=MSISDN |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/fk_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 5

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `authenticateCollectionUser` | authenticateAPIUserProcessor → getUserDetailsProcessor → dummyProcessor | — | — |
| `changePassword` | authenticateAgentProcessor → authenticateUserProcessor → changeAuthValueProcessor → saveAuthDetailsForLoginProcessor → dummyProcessor | — | regExp(${channel_code})=AGENTAPP; regExp(${channel_code})=NOVOPAY |
| `forgotPassword` | getUserDetailsForLoginProcessor → checkEmployeeStatusProcessor → checkCaptchaEnableProcessor → validateCaptchaProcessor → forgotAuthValueProcessor → generateOTPProcessor → dummyProcessor → validate... | — | if(${function_code})=CONFIRM; if(${function_code})=INITIATE; if(${isCaptchaEnable})=true; regExp(${email_exist})=YES; regExp(${function_code})!CONFIRM; regExp(${function_code})=CONFIRM|DEFAULT |
| `forgotPin` | validateHandleValueForCollectorEmployeeProcessor → generateOTPProcessor → dummyProcessor → validateOTPProcessor → generateAuthValueProcessor → updateMpinForCollectorProcessor → sendSMSProcessor → d... | — | regExp(${function_code})=INITIATE; regExp(${function_code})=VALIDATE |
| `setAuthValue` | getUserDetailsForLoginProcessor → checkEmployeeStatusProcessor → validateOTPProcessor → registerDeviceProcessor → validateOTPProcessor → getConfigValueProcessor → setAuthValueProcessor → getAgentDe... | — | regExp(${function_code})=DEFAULT_REGISTER; regExp(${function_code})=DEFAULT_VALIDATE |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/idfcp_agent_employee_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 3

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateAgentEmployee` | checkEmployeeParentAgentIdProcessor → populateEmployeeParentAgentDetailsProcessor → populateAgentAuthDetailsProcessor → validateHandleDetailsProcessor → populateUserDetails → checkEmployeeIdProcess... | createUserRoleMapping, deleteRole, submitApplication, updateUserRoleMapping, verifyDocuments | regExp(${create_new_role_flag})=true; regExp(${delete_existing_role_flag})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE … (+42) |
| `getAgentEmployeeDetails` | checkAgentEmployeeIdProcessor → getEmployeeActorProcessor → getActorUserProcessor → getUserRoleDetailsProcessor → getEmployeeDetailsProcessor → getEmploymentDetailsProcessor → dummyProcessor → getE... | — | — |
| `getAgentEmployeeList` | getAgentEmployeeListProcessor → dummyProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/idfcp_agent_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 3

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateAgent` | dummyProcessor → populateUserDetails → validateAgentBusinessLogicProcessor → checkEmployeeIdProcessor → populateParentActorId → validateAgentProductProcessor → validateActorAccountProcessor → valid... | createOrUpdateCorporateRoleMapping, createUserRoleMapping, submitApplication, verifyDocuments | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${is_validate_user})=true; regExp(${maker_checker_enabled})=0 … (+33) |
| `getAgentDetails` | checkAgentIdProcessor → getAgentActorProcessor → dummyProcessor → populateAgentIdProcessor → getCorporateProcessor → getActorAccountsProcessor → getCorporateDetailsProcessor → getParentAgentAndCorp... | — | regExp(${function_sub_code})=DEFAULT |
| `getAgentList` | getAgentListProcessor → dummyProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/idfcp_corporate_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 3

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateCorporate` | populateTenantParentCorporateIdCustomProcessor → dummyProcessor → validateRoleGroupProcessor → populateUserDetails → validateCorporateProcessor → getMakerCheckerEnabledForUseCaseProcessor → checkEm... | createOrUpdateCorporateRoleMapping, createUserRoleMapping, submitApplication, verifyDocuments | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${is_validate_user})=true; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+35) |
| `getCorporateDetails` | checkCorporateIdProcessor → populateTenantCorporateDetailsProcessor → dummyProcessor → getCorporateProcessor → getCorporateDetailsProcessor → getCorporateProductsProcessor → getActorAddressProcesso... | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT|ALL; regExp(${function_sub_code})=TENANT |
| `getCorporateList` | getCorporateListProcessor → dummyProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/idfcp_employee_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 3

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateEmployee` | dummyProcessor → populateTenantCorporateDetailsProcessor → getEmployeeUserValidationFlagProcessor → validateUserChannelsAndAuthProcessor → validateEmployeeUserBusinessLogicProcessor → validateEmplo... | createUserRoleMapping, submitApplication, updateUserRoleMapping, verifyDocuments | regExp(${employee_user_validation_flag})=false; regExp(${employee_user_validation_flag})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE … (+54) |
| `getEmployeeDetails` | checkCorporateEmployeeIdProcessor → getEmployeeActorProcessor → getActorUserProcessor → getEmployeeDetailsProcessor → getEmploymentDetailsProcessor → getEmployeeCustomDetailsProcessor → dummyProces... | — | regExp(${user_id_str})=[0-9]{1,11} |
| `getEmployeeList` | getEmployeeListProcessor → dummyProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/insurance_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 5

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateInsuranceProvider` | validateInsuranceProviderProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → fetchBulkUniqueMasterData → constructRequestForApprovalUsingApprovalTemplate → deleteDraftProc... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+4) |
| `deleteInsuranceProvider` | validateInsuranceProviderForDeleteProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → getInsuranceProviderDetailsProcessor → fetchBulkUniqueMasterData → constructRequestFo... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `getInsuranceProviderDetails` | getInsuranceProviderDetailsProcessor → fetchBulkUniqueMasterData | — | regExp(${function_sub_code})=BY_CODE; regExp(${function_sub_code})=DEFAULT |
| `getInsuranceProvidersList` | getInsuranceProvidersListProcessor | — | — |
| `getUniqueInsuranceProviderCodeAndName` | getUniqueInsuranceProviderCodeAndNameProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/nl_agent_lending.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 3

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `getAgentLoanAccountNumberList` | checkAgentIdProcessor → getAgentAccountNumberListProcessor | — | — |
| `getAgentThroughLoanAccountNumber` | getCustomerByLoanAccountNumberProcessor | — | — |
| `getCustomerLoanAccountNumberList` | checkCustomerIdProcessor → getCustomerLoanAccountNumberListProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/orc_bp.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 2

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `blockOrUnblockCustomer` | dummyProcessor → dummyProcessor | — | if(${function_sub_code})=BLOCK; if(${function_sub_code})=UNBLOCK |
| `getCustomerList` | getCustomerListDummyProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/orc_collections.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 62

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `allocateCollections` | allocateCollectionsProcessor → allocateMfiCollectionsProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=MFI_COLLECTION; regExp(${function_sub_code}_${allocation_type})=COLLECTIONS_PRIMARY; regExp(${function_sub_code}_${allocation_type})=COLLECTIONS_SECONDARY; regExp(${function_sub_code}_${allocation_type})=MFI_REALLOCATE_SECONDARY_REALLOCATE; regExp(${function_sub_code}_${allocation_type})=REALLOCATE_PRIMARY; regExp(${function_sub_code}_${allocation_type})=REALLOCATE_SECONDARY … (+1) |
| `autoPrimaryAllocation` | automaticPrimaryAllocationProcessor | — | — |
| `autoSecondaryAllocation` | automaticSecondaryAllocationProcessor | — | — |
| `bulkAllocate` | bulkAllocateProcessor | — | — |
| `collectionDetailsForTask` | collectionTaskProcessor → getAllCustomersRecordsProcessor → createFinalCollectionDetailsProcessor | — | regExp(${function_sub_code}_${function_code})=GETCOLLECTION_DEFAULT |
| `collectorLoginReminderBatch` | getEmployeeListProcessor → getEmployeeListByRoleProcessor → collectorLoginReminderBatch | — | — |
| `createMinimumCustomer` | checkCorporateIdProcessor → createActorProcessor → createAddressProcessor → createActorAddressProcessor → createContactDetailProcessor → createActorContactDetailProcessor → createCustomerProcessor ... | — | regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT |
| `createOfficeLinkage` | getMakerCheckerEnabledForUseCaseProcessor → constructRequestForApprovalUsingApprovalTemplate → deleteDraftProcessor → populateUserStoryProcessor → addOfficeLinkageProcessor → deleteOfficeLinkagePro... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=DELETE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+1) |
| `createOrUpdateClusterToVtcMapping` | createOrUpdateClusterVtcMappingProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `createOrUpdateCollection` | validateCollectionProcessor → checkCorporateIdProcessor → createActorProcessor → createAddressProcessor → createActorAddressProcessor → createContactDetailProcessor → createActorContactDetailProces... | — | regExp(${action})=CREATE; regExp(${function_sub_code}_${function_code})=CREATE_COLLECTION; regExp(${function_sub_code}_${function_code})=CREATE_COLLECTION|UPDATE_COLLECTION |
| `createOrUpdateCollectionLead` | leadGenerationForCollectionProcessor → dummyProcessor | — | — |
| `createOrUpdateCorporateSubClientMapping` | createOrUpdateCorporateSubClientMappingProcessor → dummyProcessor | — | — |
| `createOrUpdateEmployeeClusterMapping` | createOrUpdateEmployeeClusterMappingProcessor | — | — |
| `createOrUpdateOfficeClustersMapping` | createOrUpdateOfficeClustersMappingProcessor | — | — |
| `createOrUpdateRule` | createOrUpdateRuleProcessor | — | regExp(${function_sub_code})=OFFICE_LEVEL_UPDATE |
| `createOrUpdateVtcListToOfficeMapping` | createOrUpdateVtcListToOfficeMappingProcessor → deleteCachedKeysProcessor | — | — |
| `downloadEmployeeList` | downloadEmployeeListProcessor | — | — |
| `findGeoCodingForAddressBatch` | findGeoCodingForAddressBatchProcessor | — | — |
| `generateCollectionMISReportInBatch` | generateCollectionMISReportInBatchProcessor → collectionMISReportCsvProcessor | — | — |
| `generateSettlementMISReportInBatch` | generateSettlementMISReportInBatchProcessor → settlementMISReportCsvProcessor | — | — |
| `generatecollectionAttemptMTDReportBatch` | generateCollectionAttemptMTDReportBatchProcessor → collectionAttemptMTDReportCsvProcessor | — | — |
| `getAllEmployeeServiceableProduct` | getEmployeeServiceableProductsProcessor | — | — |
| `getClusterList` | getClusterListProcessor | — | — |
| `getCollectionCountForCollector` | extractMfiOfficeIdProcessor → getRoleDetailsForUserProcessor → getRequiredCollectorIdsProcessor → getCollectionCountForCollectorProcessor → fetchGroupDetailsForFinnoneRecordsProcessor → createFinal... | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=MFI_COLLECTION; regExp(${function_sub_code})=DEFAULT|COUNT; regExp(${function_sub_code})=PTP; regExp(${operation_mode})!MOBILE; regExp(${operation_mode})=MOBILE |
| `getCollectionDetails` | extractOfficeIdProcessor → getCollectionDetailsProcessor → getAllCustomersRecordsProcessor → createFinalCollectionDetailsProcessor → getAllMfiCustomersRecordsProcessor → createFinalMfiCollectionDet... | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=MFI_COLLECTION; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT|PTP|NEARBY|MFI_NEARBY; regExp(${function_sub_code})=MFI_MISFETCH; regExp(${function_sub_code})=MISFETCH; regExp(${function_sub_code})=NEARBY; regExp(${function_sub_code})=PTP … (+3) |
| `getCollectionsListForPastEmi` | getLastOpenCollectionsIdForCollIdsProcessor → extractMfiOfficeIdProcessor → getRoleDetailsForUserProcessor → getRequiredCollectorIdsProcessor → getCollectionDetailsProcessor → getCustomerRecordsFor... | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=MFI_COLLECTION; regExp(${operation_mode})!MOBILE; regExp(${operation_mode})=MOBILE |
| `getCollectionsListOld` | extractMfiOfficeIdProcessor → getRoleDetailsForUserProcessor → getRequiredCollectorIdsProcessor → getCollectionDetailsProcessor → getCustomerRecordsForCollectionsProcessor → getExternalSystemCustom... | — | regExp(${for_offline_collection})!true; regExp(${for_offline_collection})=true; regExp(${function_code})=MFI_COLLECTION; regExp(${function_code})=PRIORITY; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=MFI_NEARBY; regExp(${function_sub_code})=PTP; regExp(${nearby_collection_flag})=1 … (+6) |
| `getCollectorMtd` | getCollectorMtdProcessor → collectorMtdCalculatorProcessor | — | regExp(${function_sub_code}_${function_code})=MTD_COLLECTION|MTD_MFI_COLLECTION |
| `getCorporateListForEligibilityRule` | getCorporateListForEligibilityRuleProcessor | — | — |
| `getCorporateOfficeList` | getCorporateOfficeListProcessor | — | — |
| `getCorporateSubclientMapping` | getCorporateSubclientMappingProcessor | — | — |
| `getCustomerDetailsForCollection` | getCustomerDetailsForCollectionProcessor | — | — |
| `getCustomerDetailsForIVR` | getCustomerDetailsForIVRProcessor | — | — |
| `getCustomersIdsForCollector` | getCustomersIdsForCollectorProcessor → getCustomerDetailsForCollectionProcessor | — | — |
| `getEligibilityRuleList` | getEligibilityRuleListProcessor | — | — |
| `getEligibleUserListForTaskAllocation` | getEligibleUserListForTaskAllocationProcessor → dummyProcessor | — | — |
| `getEmployeeData` | getEmployeeDataProcessor | — | regExp(${function_sub_code})=COLLECTIONS; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=EMPLIST |
| `getEmployeeList` | getEmployeeListProcessor → getEmployeeListByRoleProcessor → getEmployeeClusterMappingProcessor → filterDropDownEmployeeListProcessor → getClusterLinkedToEmployeeListProcessor → dummyProcessor | — | regExp(${function_sub_code})=COLLECTIONS |
| `getGeoCoding` | getGeoCodingProcessor | — | — |
| `getGroupCollectionDetails` | extractMfiOfficeIdProcessor → getRoleDetailsForUserProcessor → getRequiredCollectorIdsProcessor → getGroupCollectionDetailsProcessor → restructureGroupCollDetailsProcessor | fetchLMSUpdatesForCollections | regExp(${for_offline_collection})!true; regExp(${for_offline_collection})=true; regExp(${operation_mode})!MOBILE; regExp(${operation_mode})=MOBILE; regExp(${sub_client_code})=NOVOPAY |
| `getGroupDetailsForCustomers` | getGroupDetailsForCustomersProcessor | — | — |
| `getIndividualCollectionDetails` | extractMfiOfficeIdProcessor → getRoleDetailsForUserProcessor → getRequiredCollectorIdsProcessor → getIndividualCollectionDetailsProcessor → restructureIndividualCollDetailsProcessor | fetchLMSUpdatesForCollections | regExp(${for_offline_collection})!true; regExp(${for_offline_collection})=true; regExp(${operation_mode})!MOBILE; regExp(${operation_mode})=MOBILE; regExp(${sub_client_code})=NOVOPAY |
| `getLinkedCorporateList` | getOfficeHierarchyUnderUserProcessor → populateLinkedCorporatesProcessor | — | — |
| `getLinkedOffices` | populateLinkedOfficesProcessor | — | — |
| `getMeetingCentreAndLeaderCustomerLocation` | getMeetingCentreAndCustomerLocationProcessor | — | — |
| `getNearbyRetailers` | getNearbyRetailersProcessor | — | regExp(${function_sub_code}_${function_code})=FETCHRETAILERS_COLLECTION |
| `getOfficeClusterMappingList` | getOfficeHierarchyUnderUserProcessor → getOfficeClusterMappingListProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getOfficeList` | getMfiOfficeListProcessor → getOfficeListProcessor → getOfficeGeoHierarchyDetailsProcessorV2 → getOfficeListUnderUserProcessor → getOfficeHierarchyUnderUserProcessor → getOfficeListProcessor → getU... | — | if(${function_sub_code})=GET_OFC_BY_LVL_AND_USR_ID; if(${function_sub_code})=GET_PARENT_OFFICES_BY_LVL; regExp(${base_office_level})!OFF_LVL_001; regExp(${base_office_level})=OFF_LVL_001; regExp(${client_code})!hdfcisac; regExp(${client_code})=hdfcisac; regExp(${function_sub_code})=CHILD_LIST; regExp(${function_sub_code})=DEFAULT … (+7) |
| `getPrimaryAllocation` | applySpecialFiltersOnCollectionsProcessor → productTypeFilterProcessor → applySubClientCodeFilterProcessor → getPrimaryAllocationProcessor → getVtcListForOfficeProcessor → getAllCustomersRecordsPro... | — | regExp(${function_sub_code}_${function_code})=PRIMARY_DEFAULT |
| `getPrimaryReAllocation` | getVtcListForOfficeProcessor → applySpecialFiltersOnCollectionsProcessor → productTypeFilterProcessor → applySubClientCodeFilterProcessor → getPrimaryAllocationProcessor → getAllCustomersRecordsPro... | — | regExp(${function_sub_code}_${function_code})=REALLOCATE_PRIMARY |
| `getReportDetails` | getReportDetailsProcessor | — | — |
| `getReportingToDesignation` | getReportingToDesignationProcessor | — | — |
| `getReportingToEmployee` | getReportingToEmployeeProcessor | — | — |
| `getRoleFromAdid` | getRoleFromBulkBranchIdProcessor → getRoleFromAdidProcessor | — | regExp(${function_sub_code})=BULK_DATA; regExp(${function_sub_code})=DEFAULT |
| `getSecondaryAllocation` | extractOfficeIdProcessor → getVtcListForOfficeIdProcessor → getVtcListForAgentIdProcessor → applySpecialFiltersOnCollectionsProcessor → productTypeFilterProcessor → applySubClientCodeFilterProcesso... | — | regExp(${function_sub_code}_${function_code})=SECONDARY_DEFAULT |
| `getSecondaryReAllocation` | extractOfficeIdProcessor → getVtcListForOfficeIdProcessor → getVtcListForAgentIdProcessor → applySpecialFiltersOnCollectionsProcessor → productTypeFilterProcessor → applySubClientCodeFilterProcesso... | — | regExp(${function_sub_code}_${function_code})=REALLOCATE_SECONDARY |
| `getSubClientCodeDetailsList` | getSubClientCodeDetailsListProcessor → dummyProcessor | — | — |
| `getVtcList` | getVtcListProcessor | — | regExp(${function_sub_code})=COLLECTIONS; regExp(${function_sub_code})=UN_MAPPED_VTCs; regExp(${function_sub_code})=VIEW_LINKED_VTCs |
| `linkOffices` | officeLinkageProcessor | — | — |
| `notifyUndepositedCashBatch` | notifyUndepositedCashBatchProcessor | — | — |
| `smsCollectorSummaryBatch` | getEmployeeListProcessor → getEmployeeListByRoleProcessor → smsCollectorSummaryBatchProcessor | — | — |
| `smsCollectorSummaryBatch` | getEmployeeListProcessor → getEmployeeListByRoleProcessor → smsCollectorSummaryBatchProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/orc_mfi.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 154

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `allocateMeetingCenter` | getUseCaseProcessor → validateMeetingCenterAllocationProcessor → validateAllocatingEmployeeProcessor → getMakerCheckerEnabledForUseCaseProcessor → prepareDataForApproval → constructRequestDataForAp... | submitApplication, updateApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=APPROVE; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DELETE; regExp(${function_sub_code})=UPDATE … (+26) |
| `autoSecondaryReallocate` | autoSecondaryMfiReallocateProcessor | — | regExp(${function_sub_code})=SEC_REALLOCATE; regExp(${function_sub_code}_${function_code})=SEC_REALLOCATE_MFI_COLLECTION |
| `bankEmployeeDormancyJob` | employeeDormancyBatchProcessor → bankEmployeeDormancyJobProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `bulkFileToSGBehaviourScoreJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGEmployeeLocationUpdateJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGEmployeeTargetJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGHdfcHrmsJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGStateDistrictMasterJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGVillageCreationJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkFileToSGVrmCategoryJob` | bulkFileToStagingTableJobProcessor | — | — |
| `bulkSGToBehaviourScoreJob` | bulkSGToBehaviourScoreJobProcessor | — | — |
| `bulkSGToEmployeeLocationUpdateJob` | bulkSGToEmployeeLocationUpdateJobProcessor | — | — |
| `bulkSGToEmployeeTargetJob` | bulkSGToEmployeeTargetJobProcessor | — | — |
| `bulkSGToHdfcHrmsJob` | bulkSGToHdfcHRMSJobProcessor | — | — |
| `bulkSGToStateDistrictMasterJob` | bulkSGToStateDistrictMasterJobProcessor | — | — |
| `bulkSGToVillageCreationJob` | bulkSGToVillageCreationJobProcessor | — | — |
| `bulkSGToVrmCategoryJob` | bulkSGToVrmCategoryJobProcessor | — | — |
| `createMfiCustomer` | createMfiActorProcessor → createMfiCustomerProcessor → createMfiCustomerContactDetailsProcessor → createMfiCustomerAddressDetailsProcessor → createMfiCustomerCurrentAndBusinessAddressDetailsProcessor | — | regExp(${actor_type})!GROUP |
| `createOrUpdateBankEmployee` | getLoggedUserIdForHdfcIsacProcessor → validateBankEmployeeUserId → populateUserDetails → getBankUserCorporateProcessor → convertToUpperCaseProcessor → populateTenantCorporateDetailsProcessor → vali... | createUserRoleMapping, submitApplication, updateUserRoleMapping | if(${client_code})=hdfcisac; if(${function_sub_code})=UPDATE; if(${role_code})=SO; regExp(${client_code})!hdfcisac; regExp(${client_code})=hdfcisac; regExp(${create_bank_employee})=true; regExp(${default_handle_type})!ADID; regExp(${function_code})=APPROVE … (+39) |
| `createOrUpdateCsdHierElmVtc` | csdHierElmVtcValidateProcessor → createOrUpdateCsdHierElmVtcProcessor → updateSubDistrictInVtcProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=UPDATE_SUBDISTRICT |
| `createOrUpdateCsdVtc` | createOrUpdateCsdVtcProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `createOrUpdateCustomerLoanDetails` | createOrUpdateCustomerLoanDetailsProcessor | — | regExp(${function_sub_code})=GROUP |
| `createOrUpdateEmpWorkAreaLinkage` | validateEmployeeWorkAreaLinkage → getMakerCheckerEnabledForUseCaseProcessor → generateTaskDetailsForApprovalProcessor → constructRequestDataForApproval → createTaskForApprovalApplicationProcessor →... | submitApplication, updateApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+7) |
| `createOrUpdateEmployee` | dummyProcessor → populateTenantCorporateDetailsProcessor → getEmployeeUserValidationFlagProcessor → getUserCorporateProcessor → validateEmployeeRoleDetailsProcessor → checkPreferredLanguageProcesso... | createUserRoleMapping, submitApplication, updateUserRoleMapping, verifyDocuments | regExp(${create_user_during_update})=false; regExp(${create_user_during_update})=true; regExp(${employee_user_validation_flag})=false; regExp(${employee_user_validation_flag})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=RESUBMIT … (+62) |
| `createOrUpdateMeetingCenter` | generateMeetingCenterNameProcessor → validateMeetingCenterProcessor → getMfiUserRoleDetailsProcessor → validateUserToCreateMeetingCenterProcessor → getMakerCheckerEnabledForUseCaseProcessor → gener... | submitApplication, updateApplication | (); regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=REJECT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE_NAME … (+32) |
| `createOrUpdateOfficeWorkAreaLinkage` | getMfiUserRoleDetailsProcessor → validateOfficeVtcLinkageProcessor → generateTaskDetailsForApprovalProcessor → getMakerCheckerEnabledForUseCaseProcessor → constructRequestDataForApproval → officeWo... | submitApplication, updateApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=APPROVE; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE … (+14) |
| `createOrUpdatePromoCode` | populateUserDetails → getMakerCheckerEnabledForUseCaseProcessor → generateDataForPromoCode → deleteDraftProcessor → dummyProcessor → createOrUpdatePromoCodeProcessor → populateUserDetails → generat... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+6) |
| `createOrUpdateVtcToHamletsMapping` | validateVtcToHamletMapping → createOrUpdateHamletsToVtcMappingProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `customerMobileDedupe` | customerMobileDedupeProcessor → customerMobileAddNumberDedupeProcessor | — | regExp(${function_sub_code})=ADD_NUMBER; regExp(${function_sub_code})=DEFAULT |
| `deleteBankEmployee` | getLoggedUserIdForHdfcIsacProcessor → populateUserDetails → validateBankEmployeeUserId → convertToUpperCaseProcessor → getBankEmployeeEntityFromEmployeeIdProcessor → dummyProcessor → captureAuditDa... | submitApplication | if(${client_code})=hdfcisac; regExp(${client_code})!hdfcisac; regExp(${client_code})=hdfcisac; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|WITHOUT_CHECKER; regExp(${function_code})=WITHOUT_CHECKER; regExp(${function_sub_code})=DEFAULT … (+5) |
| `deleteEmployee` | populateUserDetails → getEmployeeIdFromEmployeeCodeProcessor → dummyProcessor → getMakerCheckerEnabledForUseCaseProcessor → dummyProcessor → dummyProcessor → dummyProcessor → populateResponseProces... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=DEFAULT … (+4) |
| `deleteMeetingCenter` | getMeetingCenterUsecaseProcessor → validateDeletionOfMeetingCenterProcessor → getMakerCheckerEnabledForUseCaseProcessor → meetingCenterDataForApprovalProcessor → deleteDraftProcessor → populateUser... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=DELETE; regExp(${maker_checker_enabled})=1 |
| `deletePromoCodeDetails` | getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → processPromocodeDataForDelete → deleteDraftProcessor → dummyProcessor → deletePromoCodeDetailsProcessor → populateUserDetails → pro... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `downloadBehaviourScoreUploadedFile` | downloadBehaviourScoreUploadedFileProcessor | — | — |
| `downloadEmployeeLocationUpdateUploadedFile` | downloadEmployeeLocationUpdateUploadedFileProcessor | — | — |
| `downloadEmployeeTargetUploadedFile` | downloadEmployeeTargetUploadedFileProcessor | — | — |
| `downloadHdfcHrmsUploadedFile` | downloadHdfcHRMSUploadedFileProcessor | — | — |
| `downloadStateDistrictMasterUploadedFile` | downloadStateDistrictMasterUploadedFileProcessor | — | — |
| `downloadVillageCreationUploadedFile` | downloadVillageCreationUploadedFileProcessor | — | — |
| `downloadVrmCategoryUploadedFile` | downloadVrmCategoryUploadedFileProcessor | — | — |
| `employeeDormancyJob` | employeeDormancyBatchProcessor | — | — |
| `employeeMeetingCenterList` | employeeMeetingCenterListProcessor → getEmployeeMeetingCenterListProcessor | — | regExp(function_sub_code)=DEFAULT; regExp(function_sub_code)=UNDER_VTC |
| `fetchEmployeeMeetingCenterAllocation` | fetchEmployeeMeetingCenterAllocationProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT |
| `fetchEmployeeMeetingCenterAllocationDetails` | getLoggedInUserRoleForFetchingEmployeesMfiProcessor → employeeMeetingCenterListProcessor → fetchEmployeeMeetingCenterAllocationDetailsProcessorV2 → employeeMeetingCenterListProcessor → fetchEmploye... | — | regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DELETE; regExp(${function_sub_code})=UNDER_VTC_REALLOCATE; regExp(${function_sub_code})=UNDER_VTC|UNDER_VTC_REALLOCATE|OFFICE_WISE |
| `fetchEmployeeMtgCenterAllocationList` | getLoggedInUserRoleForFetchingEmployeesMfiProcessor → fetchEmployeeMtgCenterAllocationProcessor → fetchEmployeeMtgCenterAllocationProcessor → prepareEmployeeMeetingCenterDataForExportProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=REPORTS; regExp(${function_sub_code})=REPORTS|SUBMITTED_FOR_APPROVAL|PENDING_APPROVAL |
| `findDistBetweenMeetingCenterCoordinates` | distanceBetweenCoordinatesProcessor | — | — |
| `getActiveOfficeIdsWithExternalBranchCodes` | getActiveOfficeIdsWithExternalBranchCodesProcessor | — | — |
| `getActorBasicDetails` | getActorBasicDetailsProcessor | — | — |
| `getActorHomeAndOfficeLocation` | getActorHomeAndOfficeLocationProcessor | — | — |
| `getAddressFromVtc` | getAddressFromVtcProcessor | — | — |
| `getAllOfficesForUserIdList` | getAllOfficesForUserIdListProcessor | — | — |
| `getAttendanceInfo` | — | — | regExp(${function_sub_code})=ACTIVE_DAYS |
| `getBankEmployeeDetails` | validateEmployeeHierarchyProcessor → convertToUpperCaseProcessor → preProcessEmployeeIdProcessor → populateBankEmployeeAndActorProcessor → populateBankEmployeeByIdAndActorProcessor → getActorUserPr... | — | regExp(${client_code})!hdfcisac; regExp(${client_code})=hdfcisac; regExp(${function_code})=STRICT; regExp(${function_sub_code})=BY_ID; regExp(${function_sub_code})=BY_USER_ID; regExp(${function_sub_code})=DEFAULT; regExp(${user_id_str})=[0-9]{1,11} … (+2) |
| `getBankEmployeeList` | getBankEmployeeListByRoleIdListProcessor → getBankEmployeeListProcessor → populateUserStoryProcessor → populateUserStoryProcessor | — | regExp(${client_code})!hdfcisac; regExp(${client_code})=hdfcisac; regExp(${function_code})=BY_ROLE_ID_LIST; regExp(${function_code})=DEFAULT |
| `getBaseOfficeDetailsByCustomerId` | getBaseOfficeDetailsByCustomerIdProcessor | — | — |
| `getBulkEmployeeDetails` | getEmployeeIdsFromFormattedIdsProcessor → getBulkEmployeeDetailsProcessor | — | regExp(${function_sub_code})=BY_CODE |
| `getBulkUserDetails` | getBulkUserFormattedIdsProcessor → getBulkUserBasicDetails | — | regExp(${function_sub_code})!LOAN_APPLICATION_LIST; regExp(${function_sub_code})=LOAN_APPLICATION_LIST |
| `getCensusVillageDetails` | getCensusVillageDetailsProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getCensusVillageList` | checkForIsAdminProcessor → getCensusVillageDetailsListProcessor | — | regExp(${function_sub_code})=COLLECTION_DROPDOWN; regExp(${function_sub_code})=DEFAULT|USER_SCOPED |
| `getCountryStateCityCode` | getCountryStateCityCodeProcessor | — | — |
| `getCustomerAndOfficeDetailsFromId` | getCustomerAndOfficeAddressProcessor | — | — |
| `getCustomerBehaviourScore` | getCustomerBehaviourScoreProcessor | — | — |
| `getCustomerContactNumbers` | getCustomerContactNumbersProcessor → getCustomerContactNumbersBulkProcessor | — | regExp(${function_sub_code})=BULK; regExp(${function_sub_code})=DEFAULT |
| `getCustomerDetails` | getUserDetailsForLoginProcessor → getCustomerDetailsForLoginProcessor → getCustomerDetailsProcessor → getCustomerCorporateProcessor → getUserDetailsFromCustomerProcessor → getUserHandleDetailsProce... | — | regExp(${customer_type})=BUSINESS; regExp(${customer_type})=IND; regExp(${function_code})=DEFAULT; regExp(${function_code})=HANDLE; regExp(${function_sub_code})=BASIC_DETAILS; regExp(${function_sub_code})=CUSTOMER_DETAILS; regExp(${function_sub_code})=DEFAULT … (+1) |
| `getCustomerDetailsByAccountNo` | getCustomerDetailsByAccountNoProcessor | — | — |
| `getCustomerDetailsList` | getCustomerListProcessor | — | — |
| `getCustomerDistanceFromMeetingCenter` | getDistanceBetweenCustomerAndMeetingCenterProcessorV2 | — | — |
| `getCustomerDistanceFromOffice` | getDistanceBetweenCustomerAndOfficeProcessor | — | — |
| `getCustomerStateDetails` | getCustomerStateDetailsProcessor | — | — |
| `getDSAEmployeeInVillage` | getDSAEmployeeInVillageProcessor | — | — |
| `getDetailsForAutoAllocation` | extractCustomerForMfiProcessor → getPrimaryAllocationDataProcessor → getSecondaryAllocationDataProcessor → extractCustomerForMfiProcessor → autoPrimaryAllocateNPLoansProcessor → autoSecondaryAlloca... | — | regExp(${function_sub_code})=PRIMARY|DEFAULT; regExp(${function_sub_code})=SECONDARY; regExp(${function_sub_code}_${function_code})=DEFAULT_MFI_COLLECTION; regExp(${function_sub_code}_${function_code})=PRIMARY_MFI_COLLECTION; regExp(${function_sub_code}_${function_code})=SECONDARY_MFI_COLLECTION |
| `getDetailsFromVtcId` | getDetailsFromVtcIdProcessor | — | — |
| `getDistanceBetweenBranchAndAddress` | getDistanceBetweenBranchAndAddressProcessor | — | — |
| `getDistanceBetweenCustomers` | getDistanceBetweenCustomersProcessor | — | — |
| `getDistanceBetweenMeetingCenterAndCustomer` | getDistanceBetweenMeetingCenterAndCustomerProcessor | — | — |
| `getDistanceBetweenMeetingCenterAndOffice` | getDistanceBetweenMeetingCenterAndOfficeProcessor | — | — |
| `getEmpWorkAreaDetails` | getEmployeeWorkAreaDetailsProcessor → fetchEmployeeWorkAreaDetailsProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=OFFICE_WISE |
| `getEmpWorkAreaMappingList` | getLoggedInUserRoleForFetchingEmployeesMfiProcessor → getEmpListWithWorkAreaProcessor → getEmpListWithWorkAreaProcessor → getApprovedEmployeeWorkAreaReport | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=REPORT |
| `getEmployeeActorUserIds` | getEmployeeActorUserIdProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_sub_code}_${function_code})=DEFAULT_MFI_COLLECTION |
| `getEmployeeDetails` | mfiCheckCorporateEmployeeIdProcessor → mfiGetEmployeeActorProcessor → getActorUserProcessor → mfiGetEmployeeDetailsProcessor → mfiGetEmploymentDetailsProcessor → getEmployeeExtensionDetailsProcesso... | — | if(${employee_status_change_reason})=PARENT_BLOCKED; if(${employee_status_change_reason})=PARENT_DEACTIVATED; if(${employee_status_change_reason})=PARENT_UNBLOCKED; if(${employee_status})=ACTIVE; if(${employee_status})=BLOCKED; if(${employee_status})=DEACTIVATED; regExp(${employee_status_change_reason})!; regExp(${employee_status_change_reason})!PARENT_BLOCKED … (+5) |
| `getEmployeeListByRoleAndOffice` | getListOfEmployeeByOfficeIdProcessor → getListOfEmployeeByVtcIdProcessor | — | regExp(${function_sub_code})=FILTER_BY_VTC |
| `getEmployeeNameList` | getEmployeeNameListProcessor | — | — |
| `getEmployeeParentIds` | getEmployeeParentIdsProcessor | — | — |
| `getEmployeeUnderServicableOffice` | getEmployeeUnderServicableOfficeProcessor → dummyProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getEmployeeUnderServicableOffice` | getEmployeeUnderServicableOfficeProcessor → dummyProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getEmployeesIdListUnderUserId` | checkForIsAdminProcessor → getRoleListProcessor → getCreditUnderwritingEmployeeListProcessor → getRoleListProcessor → getMfiEmployeeListProcessor → getCheckerAndMakerEmployeeListProcessor → getChec... | — | regExp(${function_sub_code})=DEFAULT|MORE_INFO; regExp(${function_sub_code})=EMP_DROP_DOWN; regExp(${function_sub_code})=IMMEDIATE_CHILD; regExp(${function_sub_code})=IMMEDIATE_CHILD_BY_STATE; regExp(${function_sub_code})=IMMEDIATE_CHILD_REPORTS; regExp(${function_sub_code})=TASK_DELEGATION; regExp(${logged_in_user_role})=CPU_CHECKER|CPU_MAKER; regExp(${logged_in_user_role})=CPU_MAKER_FIN|CPU_CHECKER_FIN … (+7) |
| `getEmployeesUnderEmployeeV2` | getEmployeesUnderEmployeeProcessor → dummyProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getGeofenceInfo` | geoFencingInfoProcessor | — | — |
| `getLanguageByUserId` | fetchLanguageForConsentProcessor | — | — |
| `getLanguageByUserId` | fetchLanguageForConsentProcessor | — | — |
| `getLastUpdatedEmployeeWorkArea` | lastUpdatedEmployeeWorkAreaProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getLastUpdatedMeetingCenter` | lastUpdatedMeetingCenterProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getLastUpdatedOfficeWorkArea` | lastUpdatedOfficeWorkAreaProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getListOfMeetingCenters` | getEmployeesUnderUserIdProcessor → getListOfMeetingCentersUnderVtcProcessor → prepareMeetingCentersListProcessorV2 → dummyProcessor → getEmployeesUnderUserIdProcessor → getListOfMeetingCentersUnder... | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=EXPORT_DATA; regExp(${function_sub_code})=UNDER_VTC |
| `getMeetingCenterDetails` | getMeetingCenterDetailsProcessor | — | — |
| `getMeetingCenterDetailsList` | getMeetingCenterDetailsListProcessor | — | — |
| `getMeetingCenterLists` | getMeetingCenterListProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=MEETING_CENTER; regExp(${function_sub_code})=VTC |
| `getMeetingCentreCountForEmployeeByVillage` | getMeetingCentreCountForEmployeeByVillageProcessor | — | — |
| `getMfiVtcListForOfficeIdAndEmployeeId` | getMfiVtcListForOfficeIdAndEmployeeIdProcessor | — | — |
| `getOfcToWrkAreaMappingDetail` | getOfcToWrkAreaMappingDetailProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getOfficeByVtcId` | getOfficeByVtcIdProcessor | — | — |
| `getOfficeFromEmployeeId` | getOfficeExternalCodeProcessor | — | — |
| `getOfficeNameByEmployeeId` | getOfficeNameByEmployeeIdProcessor | — | — |
| `getOfficeWorkAreaLinkageList` | checkForIsAdminProcessor → getOfficeWorkAreaLinkageListProcessor → getOfficeWorkAreaLinkageListFilterProcessor → getOfficeWorkAreaListProcessor → dummyProcessor → getOfficeWorkAreaLinkageListProces... | — | regExp(${function_code})=EXPORT_DATE; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT|SERVICEABLE_OFFICE; regExp(${function_sub_code})=SERVICEABLE_OFFICE |
| `getOfficesForCustomerInteraction` | getOfficesForCustomerInteractionProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getParentEmployeeContactsDetailAtLevel` | getParentEmployeeContactsDetailAtLevelProcessor → dummyProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getParentOfUserId` | getParentOfUserIdProcessor | — | — |
| `getPromoCodeDetails` | getPromoCodeDetailsProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT |
| `getPromoCodeDetailsList` | getPromoCodeDetailsByListOfPromoCodeProcessor | — | — |
| `getPromoCodeList` | getPromoCodeListProcessor | — | regExp(${function_code})=DEFAULT|ALL; regExp(${function_sub_code})=DEFAULT |
| `getReallocateToEmployeeList` | getReallocateToEmployeeListProcessor | — | regExp(function_sub_code)=DEFAULT; regExp(function_sub_code)=REALLOCATE |
| `getSalesPromoCodeByLoanProduct` | getSalesPromoCodeByLoanProductProcessor | — | — |
| `getSalesPromoCodeByLoanProduct` | getSalesPromoCodeByLoanProductProcessor | — | — |
| `getServiceableProductsForOffices` | getServiceableProductsForOfficesProcessor → dummyProcessor | — | — |
| `getSoAllocationDetails` | getSoAllocationDetailsProcessor | — | — |
| `getSupersetDashboardById` | — | — | — |
| `getSupersetDashboardList` | — | — | — |
| `getSupersetGuestToken` | — | — | — |
| `getUserBasicDetails` | getUserBasicDetailsProcessor → getEmployeeBasicInfoProcessor → getUserBasicDetailsProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=EMPLOYEE_INFO |
| `getUserIdListByEmployeeIds` | getUserIdListByEmployeeIdsProcessor | — | — |
| `getVillageDetails` | getVillageDetailsByCensusCodeProcessor | — | regExp(${function_sub_code})=CENSUS_CODE |
| `getVillageRiskMapping` | getVillageRiskMappingProcessor | — | — |
| `getVillageRiskMappingForVtcList` | getVillageRiskMappingForVtcListProcessor | — | — |
| `getVtcByEmployeeId` | getVtcByEmployeeIdProcessor | — | — |
| `getVtcDetailsById` | getVtcDetailsByIdProcessor | — | — |
| `getVtcDetailsByUserOrOfficeId` | getVtcDetailsByOfficeIdProcessor → getVtcDetailsByUserIdProcessor | — | regExp(${function_code})=OFFICE; regExp(${function_code})=USER |
| `getVtcListForOfficeId` | getVtcListForOfficeIdProcessor | — | — |
| `getVtcNameListBasedOnIds` | getVtcNameListBasedOnIdsProcessor | — | — |
| `getWorkAreaByEmployeeId` | getParticularEmployeeWorkAreaProcessor → getOfficeWiseParticularEmployeeWorkAreaProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT|DEFAULT_WITH_FALSE; regExp(${function_sub_code})=OFFICE_WISE |
| `mapMyIndiaDistanceMatrix` | getDistanceFromLatLong | — | — |
| `mapMyIndiaDistanceMatrix` | getDistanceFromLatLong | — | — |
| `mapMyIndiaGeocode` | getLongitudeAndLatitudeFromAddress | — | — |
| `mapMyIndiaGeocode` | getLongitudeAndLatitudeFromAddress | — | — |
| `mapMyIndiaRevGeocode` | getAddressFromLongitudeAndLatitude | — | — |
| `mapMyIndiaRevGeocode` | getAddressFromLongitudeAndLatitude | — | — |
| `performInternalDedupe` | performInternalDedupeProcessor | — | — |
| `reallocateMeetingCenter` | getUseCaseProcessor → getMakerCheckerEnabledForUseCaseProcessor → prepareDataForApproval → generateTaskDetailsForApprovalProcessor → constructRequestDataForApproval → createTaskForApprovalApplicati... | submitApplication, updateApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=REALLOCATE; regExp(${function_sub_code})=REALLOCATE|CREATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+5) |
| `revokeBankEmployee` | getLoggedUserIdForHdfcIsacProcessor → populateUserDetails → convertToUpperCaseProcessor → getBankEmployeeEntityFromEmployeeIdProcessor → validateEmployeeForRevokeProcessor → dummyProcessor → captur... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1; regExp(${client_code})!hdfcisac; regExp(${client_code})=hdfcisac; regExp(${function_code})=DEFAULT|WITHOUT_CHECKER; regExp(${function_code})=WITHOUT_CHECKER … (+7) |
| `revokeEmployee` | populateUserDetails → getEmployeeIdFromEmployeeCodeInclDeletedProcessor → validateEmployeeForRevokeProcessor → dummyProcessor → getMakerCheckerEnabledForUseCaseProcessor → dummyProcessor → dummyPro... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=DEFAULT … (+4) |
| `updateBankEmployeeStatus` | getLoggedUserIdForHdfcIsacProcessor → populateUserDetails → validateBankEmployeeUserId → convertToUpperCaseProcessor → getBankEmployeeEntityFromEmployeeIdProcessor → updateFunctionSubCodeForEnableR... | submitApplication | if(${client_code})=hdfcisac; if(${employee_status})=ACTIVE; if(${employee_status})=BLOCKED; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=ACTIVATE; if(${function_sub_code})=BLOCK; if(${function_sub_code})=ENABLE … (+48) |
| `updateEmployeeRole` | populateUserDetails → getEmployeeIdFromEmployeeCodeProcessor → dummyProcessor → getMakerCheckerEnabledForUseCaseProcessor → dummyProcessor → dummyProcessor → dummyProcessor → populateResponseProces... | submitApplication | if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${maker_checker_enabled})=0; if(${maker_checker_enabled})=1; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=DEFAULT … (+4) |
| `updateEmployeeStatus` | populateUserDetails → getEmployeeIdFromEmployeeCodeProcessor → validateDataUsingStatusMatrixProcessor → dummyProcessor → dummyProcessor → getMakerCheckerEnabledForUseCaseProcessor → dummyProcessor ... | submitApplication | if(${employee_status})=ACTIVE; if(${employee_status})=BLOCKED; if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=BLOCK; if(${function_sub_code})=UNBLOCK; if(${maker_checker_enabled})=0 … (+25) |
| `updateMFICustomerDetails` | updateMFICustomersProcessor → addSecondaryContactDetailForCustomerProcessor → changePrimaryContactDetailForCustomerProcessor → editMfiCustomerAddressDetailsProcessor → updatePermanentAddressForCust... | — | regExp(${function_sub_code})=ADD_ADDRESS; regExp(${function_sub_code})=ADD_ADDRESS|EDIT_ADDRESS; regExp(${function_sub_code})=ADD_CONTACT; regExp(${function_sub_code})=CHANGE_PRIMARY_CONTACT; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=EDIT_ADDRESS; regExp(${function_sub_code})=VERIFY_AND_ADD_CONTACT; regExp(${otp_verified})=true … (+4) |
| `updateMfiMeetingCenter` | updateMfiMeetingCenterProcessor → deleteCachedKeysProcessor | — | — |
| `validateNewMeetingCentreForEmployee` | validateNewMeetingCentreForEmployeeProcessor | — | — |
| `verifyMobileNumber` | generateOTPProcessor → dummyProcessor → generateOTPProcessor → generateOTPProcessor → validateOTPProcessor → dummyProcessor | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE; regExp(${function_sub_code})=CONSENT; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=FAMILY_MEMBER; regExp(${run_mode})=REAL |
| `verifyOtpAndUpdateCustomerDetails` | validateCustomerAndUserServiceableOfficeProcessor → validateOtpForMobileProcessor → addSecondaryContactDetailForCustomerProcessor | — | regExp(${function_sub_code})=ADD_CONTACT; regExp(${otp_verified})=true |
| `viewBulkBehaviourScoreFileStatus` | viewBulkBehaviourScoreFileStatusProcessor | — | — |
| `viewBulkEmployeeLocationUpdateFileStatus` | viewBulkEmployeeLocationUpdateFileStatusProcessor | — | — |
| `viewBulkEmployeeTargetFileStatus` | viewBulkEmployeeTargetFileStatusProcessor | — | — |
| `viewBulkHdfcHrmsFileStatus` | viewBulkHdfcHRMSFileStatusProcessor | — | — |
| `viewBulkStateDistrictMasterFileStatus` | viewBulkStateDistrictMasterFileStatusProcessor | — | — |
| `viewBulkVillageCreationFileStatus` | viewBulkVillageCreationFileStatusProcessor | — | — |
| `viewBulkVrmCategoryFileStatus` | viewBulkVrmCategoryFileStatusProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/orc_mfi2.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 81

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `allowCashLimitAndDepExtReq` | checkOfficeCollectionTypeProcessor → dummyProcessor | — | — |
| `bulkFileToSGUcicUpdateJob` | populateUserDetails → bulkFileToSGUCICUpdateJobProcessor | — | — |
| `bulkSGToUcicUpdateJob` | bulkSGToUCICUpdateJobProcessor | — | — |
| `checkADIDAndDeviceStatus` | getMockDataForDeviceRegProcessor → getAdidDetailsProcessor → checkEmployeeStatusProcessor → validateUserHandleTypeProcessor → getActorContactDetailProcessor → getContactDetailProcessor → inspectEmp... | — | if(${channel_code})=ANDROID; if(${is_contact_verified})=true |
| `checkPFTSFRequestStatusForVillage` | checkPFTSFRequestStatusForVillageProcessor | — | — |
| `createOrUpdateAgency` | validateAgencyProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → fetchBulkUniqueMasterData → constructRequestForApprovalUsingApprovalTemplate → deleteDraftProcessor → pop... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+4) |
| `createPortfolioTransferRequest` | getMakerCheckerEnabledForUseCaseProcessor → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → initiatePortfolioTransferRequestProcessor → persistPortfolioTransferDelegatesProcesso... | getVillagePortfolioSummary, submitApplication | if(${function_code})=DEFAULT; if(${maker_checker_enabled})=1; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_sub_code})=CREATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+13) |
| `deleteAgency` | validateAgencyProcessor → getMakerCheckerEnabledForUseCaseProcessor → populateUserDetails → getAgencyDetailsProcessor → fetchBulkUniqueMasterData → constructRequestForApprovalUsingApprovalTemplate ... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `downloadUcicUpdateUploadedFile` | downloadUCICUpdateUploadedFileProcessor | — | — |
| `executePortfolioTransfer` | executePortfolioTransferProcessor | — | — |
| `exportEmployeeWorkAreaData` | checkForIsAdminProcessor → getMfiOfficeListForReportsProcessor → exportEmployeeWorkAreaDataProcessor → dummyProcessor | — | — |
| `exportMeetingCenterManagementData` | checkForIsAdminProcessor → getApplicationDataForRequest → createCsvFileForExportProcessor | — | — |
| `exportOfficeWorkAreaData` | checkForIsAdminProcessor → getMfiOfficeListForReportsProcessor → exportOfficeWorkAreaDataProcessor → dummyProcessor | — | — |
| `fetchEmployeeMeetingCenterAllocationList` | getLoggedInUserRoleForFetchingEmployeesMfiProcessor → employeeMeetingCenterListProcessor → fetchEmployeeMeetingCenterAllocationListProcessor → filterMeetingCenterAllocationDetails → filterOfficeWis... | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=OFFICE_WISE |
| `fetchEmployeeMtgCenterAllocationDetails` | getUserIdAndRoleForEmpIdProcessor → fetchEmployeeMtgCenterAllocationDetailsProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `fetchPortfolioTransferList` | fetchPortfolioTransferListProcessor → fetchPortfolioTransferListProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=REPORTS |
| `getAccountNumbersForCustomers` | getAccountNumbersForActorsProcessor | — | — |
| `getAgencyCodeAndAdidList` | getBulkAgencyCodeAndAdidProcessor → getAgencyCodeAndAdidListProcessor | — | regExp(${function_sub_code})=BULK_DATA; regExp(${function_sub_code})=DEFAULT |
| `getAgencyDetails` | getAgencyDetailsProcessor → fetchBulkUniqueMasterData | — | regExp(${function_sub_code})=BY_CODE; regExp(${function_sub_code})=DEFAULT |
| `getAgencyList` | getAgencyListProcessor | — | — |
| `getApplicationToBeReallocated` | getCustomerForReallocationProcessor → fetchCollectionRecordsProcessor → getApplicationToBeReallocatedProcessor | — | — |
| `getCheckerEmployeesByRoleAndOffices` | getEmployeesProcessor | — | — |
| `getChildElementsByHierarchyLevel` | getChildElementsByHierarchyLevelProcessor | — | — |
| `getContactDetailsForCollection` | getContactDetailsForIndividualCollectionProcessor → getContactDetailsForGroupCollectionProcessor → populateDistanceBetweenUserAndCustomerProcessor → getContactDetailsForExtIndividualCollectionProce... | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL; regExp(${sub_client_code})=FINNONE; regExp(${sub_client_code})=NOVOPAY |
| `getCreatedByEmployeeList` | getListOfEmployeeByOfficeIdProcessor | — | — |
| `getCreatedByUserListByUserStory` | getCreatedByUserListByUserStoryProcessor | — | — |
| `getCustomerAddressDetails` | getCustomerAddressProcessor → getCustomerAddressDetailsProcessor | — | — |
| `getCustomerInteractionForCollectionListOld` | getRoleCodeForLoggedInUserActorProcessor → getRequiredCollectorIdsProcessor → getCustomerInteractionForCollectionListProcessor | — | — |
| `getCustomerLoanDetails` | getCustomerLoanDetailsProcessor → getCustomerLoanDetailsByLanProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=LOAN_DETAILS |
| `getDataForOfflineColletions` | setCommonAttributesProcessor → getDataForOfflineColletionsProcessor | — | — |
| `getEmployeeCashLimitDetails` | getEmployeeCashLimitDetailsProcessor | — | regExp(${function_code})=DEFAULT |
| `getEmployeeCashLimitList` | getEmployeeCashHoldLimitList | — | regExp(${function_sub_code})=BRANCH_DROPDOWN; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT|BRANCH_DROPDOWN |
| `getEmployeeHierarchyDetails` | setEmployeeIdsForUser → getEmployeeHierarchyDetailsProcessor | — | regExp(${function_sub_code})=BY-USER |
| `getEmployeeListByRoleAndOfficeV2` | getEmployeeListByRoleAndOfficeAndUserProcessor → getDestEmployeeListByRoleAndOfficeAndProductProcessor → getDestEmployeeListByRoleAndSrcOfficeAndProductProcessor | — | regExp(${match_by_emp_id})!^$|^null$|^undefined$|^\$\{match_by_emp_id\}$|^.*\$\{match_by_emp_id\}.*$; regExp(${match_by_office_id})!^$|^null$|^undefined$|^\$\{match_by_office_id\}$|^.*\$\{match_by_office_id\}.*$ |
| `getEmployeeListByVtcId` | getEmployeeListByVtcIdProcessor | — | — |
| `getEmployeeMappedOffices` | getEmployeeMappedOfficesProcessor | — | — |
| `getEmployeeOfficeDetails` | getEmployeeOfficeDetailsProcessor | — | — |
| `getEmployeesByOfficeIdAndVtcId` | getEmployeesByOfficeIdAndVtcIdProcessor | — | — |
| `getEmployeesListToDelegateTask` | checkForIsAdminProcessor → getRoleListProcessor → getCreditUnderwritingEmployeeListProcessor → getRoleListProcessor → getMfiEmployeeListProcessor → getCheckerAndMakerEmployeeListProcessor → getChec... | — | regExp(${logged_in_user_role})=CPU_CHECKER|CPU_MAKER; regExp(${logged_in_user_role})=CPU_MAKER_FIN|CPU_CHECKER_FIN; regExp(${logged_in_user_role})=LMSOPS; regExp(${role_group})!CU|LOSOPS|UAM|LMSOPS|EMA; regExp(${role_group})=CU; regExp(${role_group})=EMA; regExp(${role_group})=LOSOPS; regExp(${role_group})=LOSOPS|UAM|LMSOPS|EMA … (+1) |
| `getHierarchyForUserId` | getHierarchyForUserIdProcessor | — | — |
| `getMeetingCenterActivityContributorDetails` | checkForIsAdminProcessor → getEmployeesUnderUserIdProcessor → getMeetingCenterActivityContributorDetailsProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getMeetingCenterByBranchOrVillage` | getMeetingCenterByBranchOrVillageProcessor | — | — |
| `getMeetingCenterForDemandListSearch` | getMeetingCenterForDemandListSearchProcessor | — | — |
| `getMeetingCentersByLevel` | getMeetingCentersByLevelProcessor | — | regExp(${function_sub_code})=BY_OFFICE; regExp(${function_sub_code})=BY_STATE; regExp(${function_sub_code})=BY_VILLAGE |
| `getMeetingCentersUnderVillage` | getMeetingCentersUnderVillageProcessor | — | — |
| `getMfiChildHierarchyElements` | checkForIsAdminProcessor → validateAndPopulateElementDetails → populateHierarchyElementsByLevelProcessor → getUserServiceableOfficesProcessor → getMfiChildHierarchyElementsProcessor → dummyProcessor | — | regExp(${function_sub_code})=REPORTS |
| `getMfiOfficeListForReports` | checkForIsAdminProcessor → getMfiOfficeListForReportsProcessor | — | — |
| `getNearByCollection` | getNearByCollectionConsolidatedProcessor | — | — |
| `getOfficesUnderState` | getOfficesUnderStateProcessor → getUserServiceableOfficesProcessor → getFilterOfficesUnderStateProcessor | — | regExp(${function_sub_code})=SERVICEABLE_OFFC |
| `getPortFolioRequest` | getPortfolioRequestSummaryByCodeProcessor | — | — |
| `getPromoCodeDetailsFromVtc` | getPromoCodeDetailsFromVtcProcessor | — | — |
| `getRoutes` | getRoutesProcessor | — | — |
| `getSOVillages` | getSOOfficesProcessor → filterVillagesForPortfolioTransferProcessor | — | regExp(${function_code})!BRANCH |
| `getSOVillagesWithPortfolioSummary` | filterVillagesForPortfolioTransferProcessor → prepareVillageIdsForPortfolioAPIProcessor → combineVillagesWithPortfolioSummaryProcessor | getVillagePortfolioSummary | — |
| `getSosUnderEmployee` | getSosUnderEmployeeProcessor | — | — |
| `getSubordinateEmployeeList` | checkForIsAdminProcessor → getSubordinateEmployeeListProcessor | — | — |
| `getTaskDataFromCollection` | getTaskDataFromCollectionProcessor | — | — |
| `getUserInfoList` | getUserInfoListProcessor | — | — |
| `getUsersByOfficeAndRole` | getUsersByOfficeAndRoleProcessor | — | — |
| `getUsersRegionsIds` | getUsersRegionsIdsProcessor | — | — |
| `getVillageList` | getVillageListProcessor | — | regExp(${function_sub_code})=BY_OFFICE; regExp(${function_sub_code})=BY_STATE |
| `getVillageListForOfficeIds` | getVillageListForOfficeIdsProcessor | — | — |
| `getVillagePortfolioSummary` | getVillagePortfolioSummaryProcessor | getVillageAccountingPortFolioSummary, getVillageLOSPortfolioSummary | — |
| `getVillageReallocationHistory` | getVillageReallocationHistoryProcessor → deleteCachedKeysProcessor | — | — |
| `getVtcForDemandListSearch` | getVtcForDemandListSearchProcessor | — | — |
| `getVtcPincodeDumpFileName` | getVtcPincodeDumpFileNameProcessor | — | — |
| `increaseOrDecreaseCashInHandForDay` | checkOfficeCollectionTypeProcessor → validateRequestExtendAndRaiseDateProcessor → checkForTaskrequestRaisedProcessor → createEmployeeCashInHandLimitProcessor → getMakerCheckerEnabledForUseCaseProce... | — | regExp(${function_code})!APPROVE|REJECT; regExp(${function_code})=APPROVE; regExp(${function_code})=APPROVE|REJECT; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=APPROVE; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE … (+14) |
| `reallocateVtc` | getEmpDetailsForReallocationProcessor → sendVillageReallocationDetailsForApproval → getCustomersActiveLoansProcessor → getMakerCheckerEnabledForUseCaseProcessor → constructRequestDataForApproval → ... | submitApplication, updateApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_sub_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1; regExp(${send_for_approval})=false; regExp(${send_for_approval})=true … (+4) |
| `registerDevice` | getMockDataForDeviceRegProcessor → getAdidDetailsProcessor → checkEmployeeStatusProcessor → validateUserHandleTypeProcessor → validateUserDeviceBindingProcessor → getActorContactDetailProcessor → g... | — | — |
| `requestToExtendDepositCutoffTime` | checkOfficeCollectionTypeProcessor → validateDepositTimeExtendAndRaiseDateProcessor → checkForTaskrequestRaisedProcessor → createEmployeeDepositCutoffTimeProcessor → getMakerCheckerEnabledForUseCas... | updateScheduledBatchExpiryDate | regExp(${function_code})!APPROVE|REJECT; regExp(${function_code})=APPROVE; regExp(${function_code})=APPROVE|REJECT; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=APPROVE; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0 … (+5) |
| `triggerVtcPincodeDump` | triggerUploadVtcDumpProcessor | — | — |
| `updateApplicationKeyJob` | updateApplicationKeyJobProcessor | — | — |
| `updateApproverForAOO` | updateApproverForAOOProcessor | — | regExp(${usecase})=MEETING-CENTER |
| `updateEmpCashLimitStatus` | — | — | — |
| `updateEmployeeCashInHandLimit` | validateRequestExtendAndRaiseDateProcessor → getSupervisorDetAndCashLimDetails → getMakerCheckerEnabledForUseCaseProcessor → createPermanentLimitIncreaseDataProcessor → createTaskForEmployeeCashInH... | submitApplication, updateApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=PERMANENT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=UPDATE; regExp(${function_sub_code}_${function_code})=CREATE_APPROVE; regExp(${function_sub_code}_${function_code})=CREATE_PERMANENT … (+12) |
| `validateCustomerId` | validateCustomerIdProcessor → addAdditionalCustomerDetailsProcessor | — | — |
| `validateFinnoneInboundData` | validateFinnoneInboundDataProcessor | — | — |
| `verifyUserContactHandler` | getMockDataForDeviceRegProcessor → getAdidDetailsProcessor → checkEmployeeStatusProcessor → validateUserHandleTypeProcessor → getActorContactDetailProcessor → getContactDetailProcessor → verifyUser... | — | if(${channel_code})=ANDROID; if(${is_contact_verified})=true |
| `viewBulkUcicUpdateFileStatus` | viewBulkUCICUpdateFileStatusProcessor | — | — |
| `viewEmployeePortfolioTransfer` | fetchActorTransferRequestProcessor | — | — |
| `villagelinkingAndDelinkingToOfficeCheck` | villagelinkingAndDelinkingToOfficeCheckProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/product_agent_employee_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 4

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateAgentEmployee` | populateUserDetails → checkEmployeeParentAgentIdProcessor → checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → populateEmployeeParentAgentDetailsProcessor → checkPreferredLanguageProcess... | createUserRoleMapping, deleteRole, submitApplication, updateUserRoleMapping, verifyDocuments | regExp(${create_new_role_flag})=true; regExp(${delete_existing_role_flag})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0 … (+24) |
| `getAgentEmployeeDetails` | checkAgentEmployeeIdProcessor → getEmployeeActorProcessor → getActorUserProcessor → getUserRoleDetailsProcessor → getUserDetailsProcessor → getEmployeeDetailsProcessor → getEmployeeParentAgentProce... | — | if(${employee_status_change_reason})=PARENT_BLOCKED; if(${employee_status_change_reason})=PARENT_DEACTIVATED; if(${employee_status_change_reason})=PARENT_UNBLOCKED; if(${employee_status})=ACTIVE; if(${employee_status})=BLOCKED; if(${employee_status})=DEACTIVATED; regExp(${employee_status_change_reason})!; regExp(${employee_status_change_reason})!PARENT_BLOCKED … (+2) |
| `getAgentEmployeeList` | checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → getAgentIdsForACorporateProcessor → getAgentEmployeeListProcessor → populateUserStoryProcessor | — | regExp(${function_code})=BY_AGENTS; regExp(${function_code})=DEFAULT |
| `updateAgentEmployeeStatus` | populateUserDetails → checkAgentEmployeeIdProcessor → getEmployeeUserIdProcessor → checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → populateActorStatusConfigProcessor → dummyProcessor ... | submitApplication | if(${employee_status_change_reason})=PARENT_BLOCKED; if(${employee_status})=ACTIVE; if(${employee_status})=BLOCKED; if(${employee_status})=DEACTIVATED; if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=BLOCK … (+43) |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/product_agent_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 4

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateAgent` | dummyProcessor → checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → populateUserDetails → checkAgentStatusProcessor → checkCorporateCodeProcessor → checkEmployeeIdProcessor → validateHan... | createOrUpdateCorporateRoleMapping, createUserRoleMapping, submitApplication | regExp(${create_new_role_flag})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${is_validate_user})=true … (+19) |
| `getAgentDetails` | checkAgentIdProcessor → getAgentActorProcessor → dummyProcessor → populateAgentIdProcessor → getCorporateProcessor → getActorAccountsProcessor → getCorporateDetailsProcessor → getParentAgentAndCorp... | — | if(${corporate_status})=ACTIVE; if(${corporate_status})=BLOCKED; if(${corporate_status})=DEACTIVATED; if(${status_change_reason})=PARENT_BLOCKED; if(${status_change_reason})=PARENT_DEACTIVATED; if(${status_change_reason})=PARENT_UNBLOCKED; regExp(${function_sub_code})=DEFAULT; regExp(${status_change_reason})! … (+3) |
| `getAgentList` | checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → getAgentListProcessor → dummyProcessor | — | — |
| `updateAgentStatus` | populateUserDetails → checkAgentIdProcessor → checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → populateActorStatusConfigProcessor → dummyProcessor → dummyProcessor → dummyProcessor → g... | submitApplication | if(${corporate_status})=ACTIVE; if(${corporate_status})=BLOCKED; if(${corporate_status})=DEACTIVATED; if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=BLOCK; if(${function_sub_code})=DEACTIVATE … (+43) |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/product_corporate_employee_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 4

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateCorporateEmployee` | populateUserDetails → checkCorporateStatusProcessor → checkPreferredLanguageProcessor → checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → getCorporateProcessor → fetchBulkUniqueMasterDa... | createUserRoleMapping, deleteRole, submitApplication, updateUserRoleMapping, verifyDocuments | regExp(${create_new_role_flag})=true; regExp(${delete_existing_role_flag})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${generate_mpin})=true … (+38) |
| `getCorporateEmployeeDetails` | checkCorporateEmployeeIdProcessor → getEmployeeActorProcessor → getActorUserProcessor → getUserRoleDetailsProcessor → getUserDetailsProcessor → getEmployeeDetailsProcessor → getEmploymentDetailsPro... | — | if(${employee_status_change_reason})=PARENT_BLOCKED; if(${employee_status_change_reason})=PARENT_DEACTIVATED; if(${employee_status_change_reason})=PARENT_UNBLOCKED; if(${employee_status})=ACTIVE; if(${employee_status})=BLOCKED; if(${employee_status})=DEACTIVATED; regExp(${employee_status_change_reason})!; regExp(${employee_status_change_reason})!PARENT_BLOCKED … (+2) |
| `getCorporateEmployeeList` | checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → getCorporateEmployeeHierarchyListProcessor → getCorporateEmployeeListProcessor → getClusterLinkedToCorpEmployeeListProcessor → populate... | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=HIER_LIST |
| `updateCorporateEmployeeStatus` | populateUserDetails → getUserCorporateProcessor → checkCorporateEmployeeIdProcessor → getEmployeeUserIdProcessor → populateActorStatusConfigProcessor → dummyProcessor → dummyProcessor → dummyProces... | submitApplication | if(${employee_status_change_reason})=PARENT_BLOCKED; if(${employee_status})=ACTIVE; if(${employee_status})=BLOCKED; if(${employee_status})=DEACTIVATED; if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=BLOCK … (+43) |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/product_corporate_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 4

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateCorporate` | validateRoleGroupProcessor → checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → populateUserDetails → validateCorporateProcessor → checkCorporateStatusProcessor → checkCorporateCodeProce... | createOrUpdateCorporateRoleMapping, createUserRoleMapping, submitApplication, verifyDocuments | regExp(${create_new_role_flag})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${is_validate_user})=true; regExp(${maker_checker_enabled})=0 … (+22) |
| `getCorporateDetails` | populateTenantCorporateDetailsProcessor → dummyProcessor → getCorporateProcessor → fetchBulkUniqueMasterData → checkCorporateIdProcessor → getCorporateProcessor → getCorporateDetailsProcessor → get... | — | if(${corporate_status})=ACTIVE; if(${corporate_status})=BLOCKED; if(${corporate_status})=DEACTIVATED; if(${status_change_reason})=PARENT_BLOCKED; if(${status_change_reason})=PARENT_DEACTIVATED; if(${status_change_reason})=PARENT_UNBLOCKED; regExp(${function_code})=DEFAULT; regExp(${function_code})=TENANT … (+7) |
| `getCorporateList` | dummyProcessor → dummyProcessor → checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → getCorporateListProcessor → dummyProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=WITHOUT_TENANT; regExp(${function_sub_code})=DEFAULT | WITHOUT_INSURANCE  |
| `updateCorporateStatus` | populateUserDetails → getUserCorporateProcessor → checkCorporateIdProcessor → populateActorStatusConfigProcessor → dummyProcessor → dummyProcessor → dummyProcessor → getMakerCheckerEnabledForUseCas... | submitApplication | if(${corporate_status})=ACTIVE; if(${corporate_status})=BLOCKED; if(${corporate_status})=DEACTIVATED; if(${function_code})=APPROVE; if(${function_code})=DEFAULT; if(${function_code})=RESUBMIT; if(${function_sub_code})=BLOCK; if(${function_sub_code})=DEACTIVATE … (+43) |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/product_customer_orc_xml.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 3

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateCustomer` | populateUserDetails → dummyProcessor → checkPreferredLanguageProcessor → checkCorporateIdProcessor → getTenantCorporateProcessor → validateAddressDetailsProcessor → validateDocumentDetailsProcessor... | createUserRoleMapping, getRoleDetails, submitApplication, updateUserRoleMapping, verifyDocuments | regExp(${corporate_id})=; regExp(${customer_type})=BUSINESS; regExp(${customer_type})=IND; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|RESUBMIT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE … (+40) |
| `getCustomerDetails` | getUserDetailsForLoginProcessor → getCustomerDetailsForLoginProcessor → getCustomerDetailsProcessor → getCustomerCorporateProcessor → getUserDetailsFromCustomerProcessor → getUserHandleDetailsProce... | — | regExp(${customer_type})=BUSINESS; regExp(${customer_type})=IND; regExp(${function_code})=DEFAULT; regExp(${function_code})=HANDLE; regExp(${function_sub_code})=DEFAULT |
| `getCustomerList` | customerListProcessor → getCustomerListByAccountNumbersProcessor → populateUserStoryProcessor | — | regExp(${function_sub_code})=BY_ACCOUNT_NUMBERS; regExp(${function_sub_code})=DEFAULT |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/waas_card_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 10

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `checkCardAvailability` | getActiveCardCountProcessor → sendEmailAlertForCardAvailibilityProcessor | — | regex(${send_alert_email})=true |
| `getCVV` | getCVVProcessor | — | — |
| `getCardDetails` | getCustomerDetailsProcessor → customGetCardDetailsProcessor → getActorContactDetailProcessor → getContactDetailProcessor → generateOTPProcessor → validateOTPProcessor → viewCardDetailsProcessor | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=VIEW |
| `getCardPinEncryptionKey` | getCardPinEncryptionKeyProcessor | — | — |
| `linkCard` | getCustomerIdProcessor → getCustomerDetailsProcessor → getActorContactDetailProcessor → getContactDetailProcessor → generateOTPProcessor → dummyProcessor → validateOTPProcessor → linkNewCardProcess... | — | if(${function_code})=CONFIRM; if(${function_code})=INITIATE; regExp(${function_sub_code})!ONBOARDING; regExp(${function_sub_code})=ONBOARDING; regExp(${operation_mode})!ASSISTED |
| `linkCardBatch` | linkCardBatchProcessor | — | — |
| `lockOrUnlockCard` | getCustomerDetailsProcessor → getCardDetailsProcessor → getUserDetailsFromCustomerProcessor → authenticateUserForLoginProcessor → lockCardProcessor → fetchBulkUniqueMasterData → partnerBankBlockCar... | — | if(${function_code})=LOCK; if(${function_code})=UNLOCK; regExp(${function_code})=LOCK |
| `replaceCard` | getCustomerDetailsProcessor → getCardDetailsForReplaceCardProcessor → getActorContactDetailProcessor → getContactDetailProcessor → generateOTPProcessor → validateOTPProcessor → partnerBankReplaceCa... | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=CONFIRM|DEFAULT; regExp(${function_code})=INITIATE |
| `requestNewCardInternal` | getCustomerDetailsProcessor → getActorContactDetailProcessor → getContactDetailProcessor → requestNewCardProcessor → getCardDetailsProcessor → blockCardProcessor → fetchBulkUniqueMasterData → partn... | — | regExp(${card_status})!BLOCKED |
| `setCardPin` | getCustomerDetailsProcessor → getActorContactDetailProcessor → getContactDetailProcessor → validateCustomerDetailsProcessor → generateOTPProcessor → validateOTPProcessor → getCardDetailsProcessor →... | — | if(${function_code})=CONFIRM; if(${function_code})=INITIATE |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/waas_corporate.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 1

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateCorporate` | validateRoleGroupProcessor → checkIfCorporateEmployeeAndGetCorporateAgentIdListProcessor → populateUserDetails → validateCorporateProcessor → checkCorporateCodeProcessor → checkEmployeeIdProcessor ... | createOrUpdateCorporateRoleMapping, createUserRoleMapping, submitApplication, verifyDocuments | regExp(${create_new_role_flag})=true; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${is_validate_user})=true; regExp(${maker_checker_enabled})=0 … (+23) |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/waas_customer_faq.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 4

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `createOrUpdateFAQ` | checkFAQExistsOrNotProcessor → createOrUpdateFAQProcessor | — | if(${function_sub_code})=UPDATE |
| `deleteFAQ` | checkFAQExistsOrNotProcessor → deleteFAQProcessor | — | — |
| `getFAQDetails` | getFAQDetailsProcessor | — | — |
| `searchFAQ` | searchFAQProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/waas_customer_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 6

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `blockOrUnblockCustomer` | authenticateAssitedUpdateProcessor → checkBlockOrUnblockProcessor → checkBlockOrUnblockProcessor → dummyProcessor → blockOrUnblockProcessor → populateUserDetails → getMakerCheckerEnabledForUseCaseP... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=BLOCK_SUPPORT|UNBLOCK_SUPPORT; regExp(${function_sub_code})=BLOCK|BLOCK_SUPPORT; regExp(${function_sub_code})=UNBLOCK|UNBLOCK_SUPPORT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+3) |
| `checkATMTransactionEnabled` | getCustomerDetailsProcessor → checkATMTransactionEnabledProcessor | — | — |
| `customerContactSync` | customerContactSyncProcessor | — | — |
| `customerLogin` | getUserDetailsForLoginProcessor → getCustomerDetailsForLoginProcessor → throwNovopayFatalExceptionProcessor → isCustomerMPINSetProcessor → generateOTPProcessor → checkForNewDeviceProcessor → dummyP... | — | regExp(${byod})=FALSE; regExp(${byod})=TRUE; regExp(${customer_status})=BLOCK; regExp(${is_device_registered})=FALSE; regExp(${is_device_registered})=TRUE; regExp(${is_mpin_set})=FALSE; regExp(${is_mpin_set})=TRUE; regExp(${is_pin_expired})=FALSE … (+8) |
| `enableOrDisableATMTransactions` | getCustomerDetailsProcessor → enableOrDisableATMTransactionsProcessor | — | — |
| `getCustomerDetails` | getUserDetailsForLoginProcessor → getCustomerDetailsForLoginProcessor → getCustomerDetailsForExternalIdProcessor → getCustomerDetailsProcessor → getUserDetailsFromCustomerProcessor → getUserHandleD... | getRemitterDetails | regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|REMITTER; regExp(${function_code})=EXTERNAL_ID; regExp(${function_code})=HANDLE; regExp(${function_code})=REMITTER; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=TRANSACTION … (+4) |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/waas_ekyc_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 25

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `biometricValidationDummy` | dummyProcessor | — | — |
| `createBankLead` | createBankLeadProcessor | — | — |
| `createCustomerAtBank` | createCustomerAtBankProcessor | — | — |
| `createEkycCustomer` | populateCreateCustomerDataProcessor | createOrUpdateCustomer | — |
| `createEkycCustomerBatch` | createEkycCustomerBatchProcessor | — | — |
| `createLead` | createActorProcessor → createLeadProcessor | — | — |
| `createSR` | createSRProcessor | — | — |
| `customerDedupe` | customerDedupeProcessor | — | — |
| `customerDedupeAndNLCheck` | dedupeCustomerProcessor → dedupeCustomerNLProcessor → dedupeCustomerNLTRProcessor | — | — |
| `customerLoginWithOtp` | generateOTPProcessor → validateOTPProcessor | — | regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE; regExp(${run_mode})=REAL |
| `doEkyc` | doEkycProcessor | postEkycTransaction | — |
| `generateApplicationForm` | applicationFormProcessor | — | — |
| `generateForm60` | form60Processor → leadDocumentGenerationProcessor | uploadLeadDocument | — |
| `generateVernacularDeclaration` | vernacularDeclarationProcessor → leadDocumentGenerationProcessor | uploadLeadDocument | — |
| `getCorporateListForOnboarding` | getCorporateListForOnboardingProcessor | — | — |
| `getScannedDoc` | getScannedDocProcessor | — | — |
| `leadGeneration` | createActorProcessor → leadGenerationProcessor | — | — |
| `updateBankLead` | updateBankLeadProcessor | — | — |
| `updateLead` | updateLeadProcessor → vernacularDeclarationProcessor → leadDocumentGenerationProcessor | uploadLeadDocument | regExp(${function_sub_code})=FORM |
| `updateLeadDigiDocument` | equitasUpdateDigiDocumentProcessor | — | — |
| `uploadEkycDocs` | uploadEkycDocsProcessor | — | — |
| `uploadLeadDocument` | uploadLeadDocumentProcessor → createDocumentWithContentProcessor → createActorDocumentProcessor → verifyDocumentProcessor | — | — |
| `uploadLeadDocumentToBank` | form60Processor → leadDocumentGenerationProcessor → uploadDocumentToBankProcessor | uploadLeadDocument | regExp(${function_sub_code})=FORM |
| `validatePan` | panValidationProcessor | — | — |
| `verifyMobileNumber` | customerDedupeProcessor → generateOTPProcessor → validateOTPProcessor → createActorProcessor → createLeadProcessor | — | regExp(${dedupe_status})=DOES_NOT_EXIST; regExp(${function_code})=CONFIRM; regExp(${function_code})=INITIATE; regExp(${run_mode})=REAL |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-actor/deploy/application/orchestration/waas_login_orc.xml`
**Owner service:** `novopay-platform-actor` 
**Root element:** `Actor`  
**Requests:** 3

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `changeAuthValue` | getUserDetailsForLoginProcessor → authenticateUserForLoginProcessor → getConfigValueProcessor → setAuthValueProcessor | — | — |
| `forgotAuthValue` | getUserDetailsForLoginProcessor → getCustomerDetailsForLoginProcessor → throwNovopayFatalExceptionProcessor → checkForNewDeviceProcessor → generateOTPProcessor → dummyProcessor → byodFailureProcess... | — | regExp(${byod})=FALSE; regExp(${byod})=TRUE; regExp(${function_code})=CONFIRM; regExp(${function_code})=CONFIRM_REGISTER; regExp(${function_code})=CONFIRM|CONFIRM_REGISTER; regExp(${function_code})=INITIATE; regExp(${handle_type})=MSISDN; regExp(${is_device_registered})=FALSE … (+3) |
| `registerDevice` | validateOTPProcessor → getUserDetailsForLoginProcessor → registerDeviceProcessor → createMobileInventoryItemDetailsProcessor → dummyProcessor | — | regExp(${function_code})=CONFIRM |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-api-gateway/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-api-gateway` 
**Root element:** `Actor`  
**Requests:** 11

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `clientKeyRotationJob` | clientKeyRotationServiceProcessor | — | — |
| `createOffice` | dummyProcessor → validateOfficeHierarchyProcessor → createContactDetailProcessor → createOfficeProcessor → createAddressProcessor → createOfficeAddressProcessor → createOfficeAttributesProcessor → ... | — | regExp(${function_code})=CORPORATE; regExp(${function_code})=TENANT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `createUser` | createUserProcessor → createAddressProcessor → createUserAddressProcessor → createUserHandleProcessor → updateUserProcessor → updateAddressProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `deleteUser` | deleteUserProcessor | — | — |
| `getCorporateHierarchyLevels` | dummyProcessor → getHierarchyTemplateForCorporateProcessor → getHierarchyLevelsProcessor → dummyProcessor | — | regExp(${function_code})=TENANT |
| `getOfficeDetails` | getOfficeProcessor → getContactDetailProcessor → getOfficeAddressProcessor → getAddressDetailsProcessor → getOfficeAttributesProcessor → dummyProcessor | — | — |
| `getOfficeList` | dummyProcessor → getOfficeListProcessor → dummyProcessor | — | regExp(${function_code})=CORPORATE; regExp(${function_code})=TENANT |
| `getUser` | getUserDetailsProcessor → dummyProcessor | — | — |
| `getUsers` | listUserProcessor → dummyProcessor | — | — |
| `internalLogout` | logoutUserProcessor → dummyProcessor | — | — |
| `validateUserHandleType` | validateUserHandleProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-approval/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-approval` 
**Root element:** `Approval`  
**Requests:** 9

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `approveApplication` | checkActionPermissionProcessor → getUserDetailsPostProcessor → checkDifferentUserProcessor → checkSuperVisorRemarksProcessor → checkApplicationStatusProcessor → approveApplicationProcessor → auditA... | getNotificationMessageByNotificationCode, getUserDetails | — |
| `createOrUpdateDraftApplication` | createDraftApplicationProcessor → dummyProcessor → updateDraftApplicationProcessor → dummyProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=UPDATE; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `deleteDraftApplication` | deleteDraftApplicationProcessor → dummyProcessor | — | — |
| `getApplicationCount` | getUseCaseAndPermissionsProcessor → applicationByHierarchyPreProcessor → getApplicationCountProcessor | — | regExp(${function_code})=APPLICATION_BY_HIERARCHY |
| `getApplicationList` | getUseCaseAndPermissionsProcessor → getApplicationListProcessor → getSubmittedForApprovalApplicationListProcessor → getDraftListProcessor → applicationByHierarchyPreProcessor → getApplicationListPr... | — | regExp(${function_code})=APPLICATION; regExp(${function_code})=APPLICATION_BY_HIERARCHY; regExp(${function_code})=DRAFT; regExp(${function_sub_code})=APPROVAL; regExp(${function_sub_code})=DEFAULT … (+3) |
| `rejectApplication` | validateRejectApplicationInputProcessor → rejectReasonValidatorPerUseCaseProcessor → checkActionPermissionProcessor → getUserDetailsPostProcessor → checkDifferentUserProcessor → fetchBulkUniqueMast... | getNotificationMessageByNotificationCode, getUserDetails, verifyDocuments | if(${callback_on_reject})=true; regExp(${id})=.*[^\\s].*; regExp(${verify_documents})=YES |
| `sendApplicationForClarification` | checkActionPermissionProcessor → getUserDetailsPostProcessor → checkDifferentUserProcessor → sendApplicationForClarificationProcessor → auditApplicationDetailsProcessor → verifyDocumentsPreProcesso... | getNotificationMessageByNotificationCode, getUserDetails, verifyDocuments | regExp(${verify_documents})=YES |
| `submitApplication` | dummyProcessor → checkDedupeApplication → submitApplicationProcessor → verifyDocumentsPreProcessor → checkSameUserProcessor → reSubmitApplicationProcessor → verifyDocumentsPreProcessor | getUseCaseDetails, verifyDocuments | regExp(${function_code})=RESUBMIT; regExp(${function_code})=SUBMIT; regExp(${verify_documents})=YES |
| `updateApprover` | updateApproverProcessor → auditApplicationDetailsProcessor → getResponseCodeProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-approval/deploy/application/orchestration/orc_mfi.xml`
**Owner service:** `novopay-platform-approval` 
**Root element:** `Approval`  
**Requests:** 7

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `checkIfApplicationIsPending` | getPendingApplicationProcessor | — | — |
| `getApplicationCount` | getUseCaseAndPermissionsProcessor → applicationByHierarchyPreProcessor → checkForFlagUsecaseProcessor → getMfiApplicationCountProcessor | — | regExp(${function_code})=APPLICATION_BY_HIERARCHY |
| `getApplicationList` | getUseCaseAndPermissionsProcessor → checkForFlagUsecaseProcessor → getApplicationListProcessor → checkForFlagUsecaseProcessor → getSubmittedForApprovalApplicationListProcessor → getDraftListProcess... | — | regExp(${function_code})=APPLICATION; regExp(${function_code})=APPLICATION_BY_HIERARCHY; regExp(${function_code})=DRAFT; regExp(${function_sub_code})=APPROVAL; regExp(${function_sub_code})=DEFAULT … (+3) |
| `getApprovalApplicationListCriteriaBased` | getApprovalApplicationListCriteriaBasedProcessor | — | regExp(${function_sub_code})=IDENTIFIER_PREFIX |
| `updateAooApplicationDetailsNewApprover` | updateAooApplicationDetailsNewApproverProcessor | — | — |
| `updateApplication` | updateApplicationProcessor | — | — |
| `updateAssigneeByTaskId` | updateMfiApplicationApproverByTaskIdProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-audit/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-audit` 
**Root element:** `Audit`  
**Requests:** 7

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `getApiResponseByStan` | getApiResponseByStanProcessor | — | — |
| `getAuditDetails` | getAuditDetailsProcessor | — | — |
| `getAuditDetailsForUsers` | getAuditDetailsForUsersProcessor | — | — |
| `getAuditEsDataByQuery` | getAuditEsDataByQueryProcessor → auditTimeLineActionProcessor | — | — |
| `getAuditEsDataByUserStory` | getAuditEsDataByUserStoryProcessor → auditTimeLineActionProcessor | — | regExp(${function_code})!WITHOUT_TIMELINE |
| `getLatestAuditDataForUsers` | getLatestAuditDataForUsersProcessor | — | — |
| `postAuditData` | postAuditDataProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-authorization/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-authorization` 
**Root element:** `Authorization`  
**Requests:** 20

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `checkPermissionByUsecase` | checkPermissionProcessor → checkApprovalPermissionProcessor | — | regExp(${function_code})=APPROVAL; regExp(${function_code})=DEFAULT |
| `createOrUpdateCorporateRoleMapping` | createCorporateRoleProcessor → updateCorporateRoleProcessor → deleteCachedKeysProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `createOrUpdateRole` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkCorporateStatusProcessor → populateCorporateDetailsProcessor → checkRoleGroupAndPopulateValueProcessor → checkDataForCreateRolePr... | getCorporateDetails, getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `createUserRoleMapping` | createUserRoleMappingProcessor → deleteCachedKeysProcessor | — | — |
| `deleteRole` | getUserDetailsPostProcessor → getUseCaseDetailsPostProcessor → checkDataForDeleteRoleProcessor → populateCorporateDetailsProcessor → checkRoleGroupAndPopulateValueProcessor → sendForApprovalLogical... | getCorporateDetails, getNotificationMessageByNotificationCode, getUseCaseDetails, getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `getBulkRoleCodeFromUserIdList` | getRoleCodeFromUserIdListProcessor | — | — |
| `getPermissionList` | getPermissionListProcessor → getPermissionListForUserProcessor → getPermissionListForCorporateProcessor → getUserRoleCodeProcessor | — | regExp(${function_code})=CORPORATE; regExp(${function_code})=DEFAULT; regExp(${function_code})=USER |
| `getPermissionListByCategories` | getPermissionListByCategoryProcessor | — | — |
| `getPermissionListFromUserId` | getPermissionListFromUserIdProcessor | — | — |
| `getRoleDetails` | getRoleDetailsProcessor → getRoleDetailsByCodeProcessor → populateCorporateDetailsProcessor → checkRoleGroupAndPopulateValueProcessor → setUserStoryForResponseProcessor → dummyProcessor | getCorporateDetails, getNotificationMessageByNotificationCode | regExp(${function_code})=DEFAULT|GET_BY_ID; regExp(${function_code})=GET_BY_CODE; regExp(${function_sub_code})=DEFAULT |
| `getRoleDetailsByCorporateId` | getRoleDetailsByCorporateIdProcessor → getRoleDetailsProcessor | — | — |
| `getRoleDetailsByUserId` | getRoleDetailsByUserIdProcessor → getRoleDetailsProcessor | — | — |
| `getRoleDetailsByUserIdList` | getRoleDetailsByUserIdListProcessor → getRolesForUserIdsProcessor → getUsersForRoleCodeProcessor | — | regExp(${function_sub_code}_${function_code})!USER_ROLE_CODE_DEFAULT; regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT; regExp(${function_sub_code}_${function_code})=USER_ID_LIST_DEFAULT; regExp(${function_sub_code}_${function_code})=USER_ROLE_CODE_DEFAULT |
| `getRoleHierarchy` | getRoleHierarchyProcessor | — | — |
| `getRoleList` | getRoleListProcessor → populateCorporateDetailsByIdMapProcessor → populateCorporateDetailsInListProcessor → populateRoleGroupMasterDataMapProcessor → populateRoleGroupValueInListProcessor → setUser... | getCorporateDetails, getCorporateList, getNotificationMessageByNotificationCode | regExp(${function_code})=TENANT; regExp(${function_sub_code})=DEFAULT |
| `getTopDownRoleHierarchy` | getTopDownRoleHierarchyProcessor | — | — |
| `getUseCaseAndPermissionsInternalAPI` | getUserStoryAndRoleProcessor → getPermissionsFromRoleIdProcessor → getUseCaseListFromPermissionIdAndUserStoryIdProcessor | — | — |
| `getUseCaseDetails` | getUseCaseDetailsProcessor | — | — |
| `getUserIdsByRoleCode` | getUserIdsByRoleCodeProcessor | — | — |
| `updateUserRoleMapping` | updateUserRoleByRoleCodeProcessor → updateUserRoleMappingProcessor → updateUserRoleProcessor → deleteCachedKeysProcessor | — | regExp(${function_code})!USER; regExp(${function_code})=USER; regExp(${function_sub_code})!ROLE_CODE; regExp(${function_sub_code})=ROLE_CODE |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-authorization/deploy/application/orchestration/orc_mfi.xml`
**Owner service:** `novopay-platform-authorization` 
**Root element:** `Authorization`  
**Requests:** 8

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `getMapMyIndiaAccessToken` | getMapMyIndiaAccessTokenProcessor | — | — |
| `getParentUserIdByRole` | getParentIdByRoleIdProcessor → getParentIdByRoleCodeProcessor → getUserIdsForRoleIdProcessor | — | regExp(${function_code})=GET_BY_CODE; regExp(${function_code})=GET_BY_ID |
| `getRoleByUserIdList` | getRoleByUserIdListProcessor | — | — |
| `getRoleCodesForFeatureAndEpic` | getRoleCodesForFeatureAndEpicProcessor | — | — |
| `getRoleDetailsByUserIdList` | getRoleDetailsByUserIdListProcessor → getRolesForUserIdsProcessor → getUsersForRoleCodeProcessor | — | regExp(${function_sub_code}_${function_code})!USER_ROLE_CODE_DEFAULT; regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT; regExp(${function_sub_code}_${function_code})=USER_ID_LIST_DEFAULT; regExp(${function_sub_code}_${function_code})=USER_ROLE_CODE_DEFAULT |
| `getRoleNamesForRoleCodes` | getRoleNamesForRoleCodesProcessor → getAllRoleNamesProcessor | — | if(${function_sub_code})=ALL; if(${function_sub_code})=DEFAULT |
| `getUserIdListForRoleIdList` | getUserIdListForRoleIdListProcessor | — | — |
| `validateRoleAndDepartment` | validateRoleAndDepartmentProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-batch/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-batch` 
**Root element:** `Batch`  
**Requests:** 22

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `bulkBatchSubmitApplication` | bulkBatchSubmitApplicationProcessor | — | — |
| `bulkUploadBatch` | bulkUploadBatchProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=VALIDATE |
| `createOrUpdateBatchGroup` | createBatchGroupProcessor → updateBatchGroupProcessor → scheduleBatchGroupProcessor → cancelBatchGroupProcessor | — | regExp(${function_sub_code})=CANCEL; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=SCHEDULE; regExp(${function_sub_code})=UPDATE; regExp(${function_sub_code})=UPDATE|SCHEDULE|CANCEL |
| `createOrUpdateBatchJob` | createBatchJobProcessor → updateBatchJobProcessor → restartBatchJobProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=RESTART; regExp(${function_sub_code})=RESTART_SINGLE; regExp(${function_sub_code})=RESTART|RESTART_SINGLE; regExp(${function_sub_code})=UPDATE |
| `createOrUpdateBatchSchedule` | createBatchScheduleProcessor → updateBatchScheduleProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `deleteBatchGroup` | logicalDeleteBatchGroupProcessor | — | — |
| `deleteBatchJob` | logicalDeleteBatchJobProcessor | — | — |
| `deleteBatchSchedule` | logicalDeleteBatchScheduleProcessor | — | — |
| `downloadBatchUploadedFile` | downloadBatchUploadedFileProcessor | — | — |
| `getAllBulkBatchUploadTypes` | getAllBulkBatchUploadTypesProcessor | — | — |
| `getBatchGroupDetails` | getBatchGroupDetailsProcessor | — | — |
| `getBatchGroupList` | getBatchGroupListProcessor | — | — |
| `getBatchJobDetails` | getBatchJobDetailsProcessor | — | — |
| `getBatchJobLastInstance` | getBatchJobLastInstanceProcessor | — | — |
| `getBatchJobList` | getBatchJobListProcessor | — | — |
| `getBatchJobStatus` | getBatchJobStatusProcessor | — | — |
| `getBatchJobStatusByRefNo` | getBatchJobStatusByRefNoProcessor | — | — |
| `getBatchScheduleDetails` | getBatchScheduleDetailsProcessor | — | — |
| `getBatchScheduleList` | getBatchScheduleListProcessor | — | — |
| `getBulkBatchUploadTemplate` | getBulkBatchUploadTemplateProcessor | — | — |
| `updateFileUpload` | updateFileUploadProcessor | — | — |
| `viewBulkBatchUploadFileStatus` | viewBulkBatchUploadFileStatusProcessor → viewBulkBatchValidateFileStatusProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=VALIDATE |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-dms/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-dms` 
**Root element:** `DMS`  
**Requests:** 6

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `downloadDocument` | getLatestVersionProcessor → getStorageLocationProcessor → getDocumentProcessor → getFileProcessor → downloadDocumentCustomProcessor | — | regExp(${doc_location})=FILE_SYSTEM; regExp(${doc_location})=S3_SYSTEM; regExp(${version})!^[1-9]\d*$ |
| `getDocumentDetails` | getLatestVersionProcessor → getDocumentDetailsProcessor | — | regExp(${version})!^[1-9]\d*$ |
| `mergeDocuments` | mergeDocumentsProcessor | — | — |
| `uploadDocument` | generateDocumentCodeProcessor → extractDocumentDetailsProcessor → saveDocumentProcessor → getStorageLocationProcessor → uploadDocumentToAWSProcessor → populateCustomFilesProcessor → saveFilesProces... | — | regExp(${doc_location})=FILE_SYSTEM; regExp(${doc_location})=S3_SYSTEM; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=REPORT_UPLOAD; regExp(${function_sub_code})=UPDATE … (+2) |
| `validateDocuments` | validateDocumentsProcessor | — | — |
| `verifyDocuments` | verifyDocumentsProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-masterdata-management/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-masterdata-management` 
**Root element:** `MasterData`  
**Requests:** 34

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `checkForHoliday` | checkHolidayProcessor | — | — |
| `createOrUpdateConfiguration` | populateUserDetails → validateForCreateConfiguration → getMakerCheckerEnabledForUseCaseProcessor → constructRequestDataForApproval → deleteDraftProcessor → populateUserStoryProcessor → createConfig... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+12) |
| `createOrUpdateMasterData` | dummyProcessor → dummyProcessor → convertDataTypeAndSubTypeToUpperCase → convertFromHdfcToNovo → getUserIdProcessor → getUserDetailsPostProcessor → validateCodeMasterDataProcessor → validateAuditDe... | getUserDetails, submitApplication | if(${allowed_client_code})=hdfcema; regExp(${allowed_client_code})!hdfcema; regExp(${allowed_client_code})=hdfcema; regExp(${client_code})=hdfcema; regExp(${create_record})=1; regExp(${function_code})!WITHOUT_CHECKER; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT … (+36) |
| `deleteMasterData` | dummyProcessor → getUserIdProcessor → getUserDetailsPostProcessor → convertFromHdfcToNovo → checkDataForLogicalDeleteMasterDataProcessor → getMakerCheckerEnabledForUseCaseProcessor → dummyProcessor... | getUserDetails, submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})!DELETE_BY_DATATYPE; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=DELETE_BY_DATATYPE; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 … (+2) |
| `getApyConfiguration` | getApyConfigurationProcessor | — | — |
| `getBankDetails` | getBankDetailsProcessor | — | — |
| `getBankDocumentMasterList` | getBankDocumentMasterListProcessor | — | — |
| `getBankList` | getBankListProcessor | — | — |
| `getBranchDetails` | getBranchDetailsProcessor → getBankAndBranchNamesProcessor | — | regExp(${function_sub_code})=BRANCH_CODE|BRANCH_NAME; regExp(${function_sub_code})=BRANCH_NAME|IFSC; regExp(${function_sub_code})=DEFAULT|BRANCH_CODE; regExp(${function_sub_code})=DEFAULT|IFSC |
| `getBranchGeoList` | getBranchStateListProcessor → getBranchDistrictListProcessor → getBranchCityListProcessor | — | regExp(${function_code})=CITY; regExp(${function_code})=CITY|DISTRICT; regExp(${function_code})=DISTRICT; regExp(${function_code})=STATE |
| `getBranchList` | getBranchListProcessor → getBranchListWithPartialSearchProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=PARTIAL_SEARCH |
| `getBulkBranchDetails` | getBulkBranchDetailsProcessor | — | — |
| `getBulkCodeMaster` | getIncrementalCodeMasterProcessor | — | — |
| `getBulkDatatypeMaster` | getBulkDatatypeMasterProcessor | — | — |
| `getBulkUniqueMasterData` | getBulkUniqueMasterDataProcessor | — | — |
| `getCodeMasterListBasedOnGroup` | getCodeMasterListBasedOnGroupProcessor | — | — |
| `getConfigurationDetails` | getConfigurationDetailsProcessor → getConfigurationDetailsByPropKeyAndServiceProcessor → dummyProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=PROP-KEY |
| `getConfigurationList` | getConfigurationListProcessor → populateUserStoryProcessor | — | — |
| `getConfigurationListBasedOnGroup` | getConfigurationListBasedOnGroupProcessor | — | — |
| `getDatatypeMaster` | getDatatypeMasterProcessor | — | — |
| `getIfscCodeList` | getIfscCodeListProcessor | — | — |
| `getInitialConfiguration` | getInitialConfigurationProcessor | — | — |
| `getMappedDistrict` | getMappedDistrictProcessor | — | regExp(${data_quantity})!ALL |
| `getMasterDataDetails` | convertDataTypeAndSubTypeToUpperCase → convertFromHdfcToNovo → getMasterDataDetailsProcessor → convertFromNovoToHdfc → dummyProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=GET_BY_DATATYPE |
| `getMasterDataList` | getMasterDataListProcessor → dummyProcessor | — | — |
| `getPLPMatrix` | getPLPMatrixProcessor | — | — |
| `getProductConfigurationDetails` | getProductConfigurationDetailsProcessor | — | — |
| `getProductDocumentDetails` | getProductDocumentDetailsProcessor | — | — |
| `getProductMappingDocuments` | getProductMappingDocumentsProcessor | — | — |
| `getPslMaster` | pslMasterProcessor | — | — |
| `getUniqueMasterData` | getUniqueMasterDataProcessor | — | — |
| `keyRotationJob` | keyRotationJobProcessor | — | — |
| `updateBusinessDate` | updateBusinessDateBatchProcessor | — | — |
| `validateSliApkVersion` | validateSliApkVersionProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-notifications/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-notifications` 
**Root element:** `Notifications`  
**Requests:** 17

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `clearNotifications` | clearNotificationsProcessor | — | regExp(${function_sub_code})=BY_ID |
| `getAppTemplateDetails` | getAppTemplateDetailsProcessor | — | — |
| `getEmailTemplateDetails` | emailTemplateDetailsProcessor | — | — |
| `getFCMTokens` | getFCMTokensProcessor | — | — |
| `getMessage` | getMessageProcessor | — | — |
| `getNotificationMessageByNotificationCode` | getNotificationMessageByNotificationCode | — | — |
| `getNotifications` | getNotificationsProcessor | — | — |
| `getNotificationsCount` | getNotificationsCountProcessor | — | — |
| `getResponseCodeByUsecaseAndSubusecase` | getResponseCodeByUsecaseAndSubusecaseProcessor | — | — |
| `getTimelineAction` | getTimelineActionProcessor | — | — |
| `sendEmail` | emailNotificationProcessor | — | — |
| `sendFCMNotification` | parseFCMDataProcessor → sendFCMNotificationProcessor → getFCMTokenFromActorProcessor → customSendFCMNotificationProcessor → getFCMTokenFromActorProcessor → sendFCMNotificationProcessor | — | regExp(${function_code})=FCM; regExp(${function_sub_code})=CUSTOM; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=TEMPLATE |
| `sendFcm` | fcmNotifierProcessor | — | — |
| `sendSMS` | sendSMSNotificationProcessor | — | — |
| `updateFCMTokenForUser` | updateFCMTokenForUserProcessor | — | — |
| `updateNotificationLog` | updateNotificationLogProcessor | — | — |
| `updateTokensForTopic` | updateTokensForTopicInternalProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-notifications/deploy/application/orchestration/custom_mfi.xml`
**Owner service:** `novopay-platform-notifications` 
**Root element:** `Request`  
**Requests:** 1

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `sendMfiSms` | sendSMSProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-notifications/deploy/application/orchestration/idfcp_otp.xml`
**Owner service:** `novopay-platform-notifications` 
**Root element:** `Notifications`  
**Requests:** 2

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `generateOTP` | generateOTPForIDFCProcessor | — | — |
| `validateOTP` | validateOTPForIDFCProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-notifications/deploy/application/orchestration/product_otp.xml`
**Owner service:** `novopay-platform-notifications` 
**Root element:** `Notifications`  
**Requests:** 3

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `fetchNotificationCode` | fetchNotificationCodeProcessor | — | — |
| `generateOTP` | generateOTPNotificationProcessor → sendSMSNotificationProcessor → populateOtpInEmailMessage → emailNotificationProcessor | — | if(${notification_mode})=EMAIL; regExp(${is_static_otp})!YES; regExp(${notification_mode})=SMS |
| `validateOTP` | validateOTPNotificationProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-payments/deploy/application/orchestration/orc_collections.xml`
**Owner service:** `novopay-platform-payments` 
**Root element:** `Payments`  
**Requests:** 71

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `ackCollectionRecordForRecon` | ackCollectionRecordForReconProcessor → dummyProcessor | — | — |
| `autoAllocateCollections` | collectionAutoAllocationProcessor → autoAllocateCollectionsJobProcessor | — | regExp(${function_sub_code})=PRIMARY|SECONDARY|DEFAULT; regExp(${function_sub_code}_${function_code})=BATCH_DEFAULT; regExp(${function_sub_code}_${function_code})=DEFAULT_MFI_COLLECTION; regExp(${function_sub_code}_${function_code})=PRIMARY_MFI_COLLECTION; regExp(${function_sub_code}_${function_code})=PRIMARY_MFI_COLLECTION|SECONDARY_MFI_COLLECTION|DEFAULT_MFI_COLLECTION; regExp(${function_sub_code}_${function_code})=SECONDARY_MFI_COLLECTION |
| `cancelBatchDeposit` | cancelBatchDepositProcessor | — | — |
| `collectionCashinQueueBatch` | collectionCashinQueueBatchProcessor | — | — |
| `collectionPaymentSettlementBatch` | collectionSettlementPaymentProcessor | — | — |
| `collectionReminderBatch` | collectionReminderBatchProcessor | — | — |
| `collectorCashInHand` | collectorCashInHandProcessor | — | regExp(${function_sub_code}_${function_code})=CASH_COLLECTION |
| `createCollection` | populateCollectionProcessor → validateCustomerIdandGroupProductProcessor → createOrUpdateCollectionProcessor | — | regExp(${function_code})=DEFAULT|COLLECTION; regExp(${function_code})=MFI_COLLECTION |
| `createCollectionAttempt` | createCollectionAttemptProcessor | — | regExp(${function_code})=DEFAULT|COLLECTIONS; regExp(${function_code})=EXTERNAL_PAYMENT_VISIT_CAPTURE; regExp(${function_code})=MFI_COLLECTION |
| `createOrUpdateBulkCollection` | collectionExtractorProcessor | — | regExp(${function_sub_code}_${function_code})=CREATE_MFI_BULK_COLLECTION|UPDATE_MFI_BULK_COLLECTION |
| `createOrUpdateCollectionLeadTask` | createOrUpdateCollectionLeadTaskProcessor | — | — |
| `createOrUpdateCollectionPaymentTrack` | createOrUpdateCollPaymTrackDetailsProcessor | — | regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT; regExp(${function_sub_code}_${function_code})=CREATE_DEFAULT|UPDATE_DEFAULT|DELETE_DEFAULT; regExp(${function_sub_code}_${function_code})=UPDATE_DEFAULT|DELETE_DEFAULT |
| `createOrUpdateTaskForCollectionBatch` | createOrUpdateTaskForCollectionBatchProcessor | — | — |
| `createRazorpayOrder` | createRazorpayOrderProcessor | — | — |
| `createTaskForNewMfiCollections` | createTaskForNewMfiCollectionsProcessor → createTaskForNewCollectionsJobProcessor | — | regExp(${function_sub_code}_${function_code})=BATCH_DEFAULT; regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT |
| `doCollections` | generateOTPProcessor → dummyProcessor → validateOTPProcessor → dummyProcessor → doCollectionsProcessor | — | regExp(${function_sub_code})=CONFIRM; regExp(${function_sub_code})=INITIATE; regExp(${function_sub_code})=SUBMIT |
| `doMfiCollections` | validateMfiCollectionProcessor → validateCollectorCashInHandProcessor → doMfiCollectionsProcessor → updateCollectionInCollectionTempDataProcessor → activityTrackerProcessor → validateDoMfiWebCollec... | — | regExp(${channel_code})=FIELD; regExp(${channel_code})=WEB |
| `enquiryPaymentStatus` | enquiryPaymentStatusProcessor | — | regExp(${function_sub_code}_${function_code})=DIGITAL_PAYMENT_COLLECTION |
| `expirePastCollections` | expirePastCollectionsJobProcessor | — | — |
| `fetchCollectionRecords` | getCollectionRecordsAsListProcessor → getDerivedTaggingForLoanAccountProcessor → filterCollectionSentToExternalProcessor → addPTPFlagToCollectionsProcessor → getAttemptsCountProcessor → addPriority... | — | regExp(${function_sub_code})!COUNT; regExp(${function_sub_code})=PRIMARY; regExp(${function_sub_code})=PRIORITY|DEFAULT; regExp(${function_sub_code})=PTP; regExp(${function_sub_code})=SECONDARY; regExp(${function_sub_code})=SECONDARY_ALLOCATED |
| `fetchCollectionRecordsForRecon` | fetchCollectionRecordsForReconProcessor → dummyProcessor | — | — |
| `generatePaymentTrackingDetails` | generateRectifiedPaymentTrackingDetailsProcessor → generatePaymentTrackingDetailsProcessor → generatePaymentTrackingForWholeGroupProcessor | — | regExp(${function_sub_code})=COLLECT_ALL; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=CREATE|UPDATE|MOBILE_RECTIFY; regExp(${function_sub_code})=MOBILE_RECTIFY; regExp(${function_sub_code})=UPDATE; regExp(${offline_recorded})!true; regExp(${offline_recorded})=true … (+8) |
| `getAllocationStatusDetails` | getAllocationStatusDetailsProcessor → paginateCollectionProcessor | — | — |
| `getAllocationStatusSummary` | getAllocationStatusSummaryProcessor | — | — |
| `getCollection` | getCollectionProcessor → getCollectionActivityProcessor → getCollectionAttemptsProcessor → dummyProcessor | — | regExp(${function_sub_code}_${function_code})=FETCH_COLLECTION |
| `getCollectionAttemptsReportDetails` | getCollectionAttemptsReportDetailsProcessor | — | — |
| `getCollectionBatchDetails` | getCollectionBatchDetailsProcessor | — | — |
| `getCollectionGeoSummary` | getCollectionGeoSummaryProcessor | — | — |
| `getCollectionMISReportDetails` | getCollectionMISReportDetailsProcessor | — | — |
| `getCollectionOverview` | getCollectionOverviewProcessor | — | — |
| `getCollectionPaymentTrack` | getCollectionPaymentTrackProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_DIGITAL|DEFAULT_DEFAULT; regExp(${function_sub_code}_${function_code})=DIGITAL_DEFAULT|DEFAULT_DEFAULT |
| `getCollectionStatusDetails` | getCollectionStatusDetailsProcessor → paginateCollectionProcessor | — | — |
| `getCollectionStatusSummary` | getCollectionStatusSummaryProcessor | — | — |
| `getCollectionSummary` | getCollectionSummaryProcessor | — | — |
| `getCollectionTransactionList` | getCollectionTransactionListProcessor | — | — |
| `getCollectionTrendSummary` | getCollectionTrendSummaryProcessor | — | — |
| `getCollectorSummaryList` | getCollectorSummaryListProcessor | — | — |
| `getCustomerCollectionInteraction` | getCustomerCollectionInteractionProcessor | — | — |
| `getCustomersIdSetForCollector` | getCustomersIdSetForCollectorProcessor | — | — |
| `getDayWiseVisitDetails` | getDayWiseVisitDetailsProcessor → paginateCollectionProcessor | — | — |
| `getDayWiseVisitSummary` | getDayWiseVisitSummaryProcessor | — | — |
| `getDpdBucketDetails` | getDpdBucketDetailsProcessor → paginateCollectionProcessor | — | — |
| `getDpdBucketSummary` | getDpdBucketSummaryProcessor | — | — |
| `getModeOfCollectionDetails` | getModeOfCollectionDetailsProcessor → paginateCollectionProcessor | — | — |
| `getModeOfCollectionSummary` | getModeOfCollectionSummaryProcessor | — | — |
| `getOverThresholdCollection` | getOverThresholdCollectionProcessor | — | — |
| `getPaymentStatusDetails` | getPaymentStatusDetailsProcessor → paginateCollectionProcessor | — | — |
| `getPaymentStatusSummary` | getPaymentStatusSummaryProcessor | — | — |
| `getTraceCustomerReportDetails` | getTraceCustomerReportDetailsProcessor | — | regExp(${function_sub_code})=WEB_REPORT |
| `getTransactionsForCollector` | getTransactionsForCollectorProcessor | — | — |
| `getUpdatedAmountOfCollection` | getUpdatedAmountOfCollectionProcessor | — | regExp(${function_sub_code}_${function_code})=UPDATEDAMOUNT_COLLECTION |
| `initiateEasebuzzPayment` | initiatePaymentProcessor | — | — |
| `markCollectionsAsSettled` | fetchCollCmsSettlementEntityProcessor → markDigitialCollectionSettledProcessor → dummyProcessor | — | — |
| `notifyClose` | getCollectionProcessor → getCollectionActivityProcessor → getCollectionAttemptsProcessor → createPayloadForCloseCollectionProcessor | — | regExp(${function_sub_code}_${function_code})=NOTIFYCLOSE_COLLECTION |
| `notifyCloseInBatch` | notifyCloseInBatchProcessor | — | — |
| `primaryAllocateCollection` | primaryAllocationJobProcessor | — | — |
| `readCmsMail` | collectionCmsFileDownloadProcessor → saveCsvRecToSettlementReportProcessor | — | — |
| `reconcileCollectionPayments` | doCollectionReconcileProcessor → doInterBankTransferForCollectionProcessor → dummyProcessor | — | — |
| `secondaryAllocateCollection` | secondaryAllocationJobProcessor | — | — |
| `sendPtpMessage` | fetchAllPtpRecordsProcessor → getCollectorsDetailsProcessor → getCustomerInfoProcessor → sendPtpMessageProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_COLLECTION |
| `sendPtpMessageBatch` | sendPtpMessageBatchProcessor | — | — |
| `submitDocumentsForPayment` | submitDocumentsForPaymentProcessor | — | regExp(${document_type})=PAN; regExp(${function_sub_code})=SUBMIT |
| `updateAllocationStatus` | updateAllocationStatusProcessor | — | regExp(${function_sub_code}_${function_code})=ALLOCSTATUS_COLLECTION |
| `updateCollection` | populateCollectionProcessor → createOrUpdateCollectionProcessor → createOrUpdateCollectionOfficeInfoProcessor | — | regExp(${function_code})=MFI_COLLECTION; regExp(${function_sub_code})!=SECONDARY_REALLOCATE|ALLOCATIONDATA; regExp(${function_sub_code})=CREATE|UPDATE|CEASE|UNALLOCATE|PRIMARY_AND_SECONDARY; regExp(${function_sub_code}_${function_code})!=PRIMARY_AND_SECONDARY_BULK_UPLOAD; regExp(${function_sub_code}_${function_code})=PRIMARY_AND_SECONDARY_BULK_UPLOAD |
| `updateCollectionTransactions` | updateCollectionTransactionsProcessor | — | — |
| `updateDpdBucketBatch` | updateDpdBucketProcessor | — | — |
| `updateLocationForTaskIds` | updateLocationForTaskIdsProcessor | — | — |
| `updateRazorpayOrderStatus` | updateRazorpayOrderStatusProcessor | — | — |
| `uploadCollectionDocs` | uploadCollectionDocsProcessor | — | — |
| `viewCollectors` | viewCollectorsProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_COLLECTION |
| `viewUniqueCollector` | viewUniqueCollectorProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_COLLECTION |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-payments/deploy/application/orchestration/orc_mfi.xml`
**Owner service:** `novopay-platform-payments` 
**Root element:** `Payments`  
**Requests:** 178

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `addContactForExternalCollectionCustomer` | validateOtpForMobileProcessor → updateContactDetailsForExternalCustomerProcessor → dummyProcessor → updateContactDetailsForExternalCustomerProcessor → dummyProcessor | — | regExp(${function_sub_code})!ADD_FINNONE_CONTACT; regExp(${function_sub_code})=ADD_FINNONE_CONTACT; regExp(${otp_verified})=true |
| `bulkFileToSGConfirmPaymentJob` | bulkFileToSGConfirmPaymentJobProcessor | — | — |
| `bulkFileToSGDynamicOneJob` | bulkFileToSGDynamicOneJobProcessor | — | — |
| `bulkFileToSGDynamicTwoJob` | bulkFileToSGDynamicTwoJobProcessor | — | — |
| `bulkFileToSGExcelAgencyUploadJob` | bulkFileToSGExcelAgencyUploadJobProcessor | — | — |
| `bulkFileToSGFinnoneLoanCorrectionJob` | bulkFileToSGFinnoneLoanCorrectionJobProcessor | — | — |
| `bulkFileToSGFinoneReverseJob` | bulkFileToSGFinoneReverseJobProcessor | — | — |
| `bulkFileToSGLoanCategoryUploadJob` | bulkFileToSGLoanCategoryUploadJobProcessor | — | — |
| `bulkFileToSGLoanExceptionUploadJob` | bulkFileToSGLoanExceptionUploadJobProcessor | — | — |
| `bulkFileToSGNpHandoffJob` | bulkFileToSGNpHandoffJobProcessor | — | — |
| `bulkFileToSGNpRevTrailsJob` | bulkFileToSGNpRevTrailsJobProcessor | — | — |
| `bulkFileToSGPriorityCalendarJob` | bulkFileToSGPriorityCalendarJobProcessor | — | — |
| `bulkFileToSGRescheduleDataUploadJob` | bulkFileToSGRescheduleDataUploadJobProcessor | — | — |
| `bulkFileToSGStaticDtTypeJob` | bulkFileToSGStaticDtTypeJobProcessor | — | — |
| `bulkOutboundNpAgencyExtractJob` | npAgencyExtractJobProcessor | — | — |
| `bulkOutboundNpCollReportJob` | npCollReportJobProcessor | — | — |
| `bulkOutboundNpHandOffFileJob` | npHandOffFileJobProcessor | — | — |
| `bulkOutboundNpRacCasesJob` | npRacCasesJobProcessor | — | — |
| `bulkOutboundNpReverseHandoffJob` | npReverseHandOffJobProcessor | — | — |
| `bulkOutboundNpTrialHistoryJob` | npTrialHistoryJobProcessor | — | — |
| `bulkSGToConfirmPaymentJob` | bulkSGToConfirmPaymentJobProcessor | — | — |
| `bulkSGToDynamicOneJob` | setCommonAttributesProcessor → bulkSGToDynamicOneJobProcessor | — | — |
| `bulkSGToDynamicTwoJob` | setCommonAttributesProcessor → bulkSGToDynamicTwoJobProcessor | — | — |
| `bulkSGToExcelAgencyUploadJob` | setCommonAttributesProcessor → bulkSGToExcelAgencyUploadJobProcessor | — | — |
| `bulkSGToFinnoneLoanCorrectionJob` | bulkSGToFinnoneLoanCorrectionJobProcessor | — | — |
| `bulkSGToFinoneReverseJob` | setCommonAttributesProcessor → bulkSGToFinoneReverseJobProcessor | — | — |
| `bulkSGToLoanCategoryUploadJob` | setCommonAttributesProcessor → bulkSGToLoanCategoryUploadJobProcessor | — | — |
| `bulkSGToLoanExceptionUploadJob` | setCommonAttributesProcessor → bulkSGToLoanExceptionUploadJobProcessor | — | — |
| `bulkSGToNpHandoffJob` | setCommonAttributesProcessor → bulkSGToNpHandoffJobProcessor | — | — |
| `bulkSGToNpRevTrailsJob` | setCommonAttributesProcessor → bulkSGToNpRevTrailsJobProcessor | — | — |
| `bulkSGToPriorityCalendarJob` | setCommonAttributesProcessor → bulkSGToPriorityCalendarJobProcessor | — | — |
| `bulkSGToRescheduleDataUploadJob` | setCommonAttributesProcessor → bulkSGToRescheduleDataUploadJobProcessor | — | — |
| `bulkSGToStaticDtTypeJob` | setCommonAttributesProcessor → bulkSGToStaticDtTypeJobProcessor | — | — |
| `bulkUploadFile` | bulkUploadFileProcessor → bulkUploadForApprovalProcessor → getMakerCheckerEnabledForUseCaseProcessor → dummyProcessor → processBulkUploadFileUncheckedProcessor → dummyProcessor | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT; regExp(${maker_checker_enabled})=0; regExp(${maker_checker_enabled})=1 |
| `cancelCds` | cancelCdsProcessor | — | — |
| `cancelCollectionForeClosure` | closeForeclosureCollectionProcessor → updateLMSAboutCancelForeclosureProcessor | — | — |
| `cancelCollections` | updateCollectionsForClosureProcessor | — | — |
| `captureForeclosureState` | captureForeclosureStateInititatedProcessor → dummyProcessor → captureForeclosureStateUpdatedProcessor → dummyProcessor | — | regExp(${function_sub_code})=INITIATED; regExp(${function_sub_code})=UPDATED |
| `cashDepositCutoffTimeElapsedForCollectorJob` | cashDepositCutoffTimeElapsedForCollectorJobProcessor | — | — |
| `checkForCollectionRestriction` | checkForCollectionRestrictionProcessor → calculateAvailableAmountForCollectionProcessor | — | regExp(${function_sub_code})=CALCULATE_REMAINING |
| `checkIfLatestCollectionForRectification` | checkIfLatestCollectionForRectificationProcessor | — | — |
| `checkPaymentStatus` | checkPaymentStatusProcessor | — | — |
| `collToStagNpAgentSyncJob` | collToStagNpAgentSyncJobProcessor | — | — |
| `collToStagNpCollReportSyncJob` | collToStagNpCollReportSyncJobProcessor | — | — |
| `collToStagNpHandOffFileSyncJob` | collToStagNpHandOffFileSyncJobProcessor | — | — |
| `collToStagNpRacCasesSyncJob` | collToStagNpRacCasesSyncJobProcessor | — | — |
| `collToStagNpTrialHistorySyncJob` | collToStagNpTrialHistorySyncJobProcessor | — | — |
| `collectAmountAfterRectification` | collectAmountAfterRectificationProcessor → dummyProcessor | — | regExp(${function_code})=GROUP; regExp(${function_sub_code})=DEFAULT |
| `collectNowFinalFlowSubmission` | collectNowFinalFlowSubmissionProcessor | — | — |
| `collectNowGenerateReceiptNotificationCHJob` | collectNowGenerateReceiptNotificationCHJobProcessor | — | — |
| `collectNowGenerateReceiptNotificationJob` | collectNowGenerateReceiptNotificationJobProcessor | — | — |
| `collectNowGenerateReceiptNotificationRMJob` | collectNowGenerateReceiptNotificationRMJobProcessor | — | — |
| `createCollectionOfficeInfo` | createCollectionOfficeInfoProcessor → dummyProcessor | — | — |
| `createOrUpdateCollectionRectification` | checkIfLatestCollectionForRectificationProcessor → createOrUpdateCollectionRectificationProcessor → dummyProcessor | — | regExp(${reason_for_rectification})=OTHERS|Others|others |
| `createOrUpdateCollectionTempData` | createOrUpdateCollectionTempDataProcessor → completeTempActionDataProcessor → dummyProcessor | — | regExp(${function_sub_code})=COMPLETE; regExp(${function_sub_code})=CREATE|UPDATE; regExp(${function_sub_code})=DELETE |
| `createOrUpdateRecordAttempt` | setCommonAttributesProcessor → validateDropDownValuesForRecAttemptProcessor → validateCollectionIdInListProcessor → validateGroupAttemptDataProcessor → currentDateFormatterProcessor → givenDateForm... | — | regExp(${address_to_be_created})=1; regExp(${channel_code})=FIELD; regExp(${channel_code})=FIELD|NOVOPAY; regExp(${channel_code})=WEB; regExp(${function_code})=GRP_MFI_REC_ATTEMPT; regExp(${function_code})=MFI_REC_ATTEMPT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=CREATE|UPDATE … (+14) |
| `createOrUpdateRecordAttempt1` | setCommonAttributesProcessor → validateCollectionIdInListProcessor → validateGroupAttemptDataProcessor → currentDateFormatterProcessor → givenDateFormatterProcessor → checkAddressToCreateForMfiProc... | — | regExp(${address_to_be_created})=1; regExp(${channel_code})=FIELD; regExp(${channel_code})=FIELD|NOVOPAY; regExp(${channel_code})=WEB; regExp(${contact_mode})=VISIT|SUPERVISORY_REVIEW; regExp(${contact_mode})=VISIT|SUPERVISORY_REVIEW|IN_CALL|OUT_CALL; regExp(${function_code})=GRP_MFI_REC_ATTEMPT; regExp(${function_code})=MFI_REC_ATTEMPT … (+28) |
| `createOrUpdateVisitDetails` | createVisitDetailsProcessor → dummyProcessor | — | regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE |
| `createSupervisorReviewTaskDetails` | createSupervisorReviewTaskDetailsProcessor → createSupervisorReviewPtpTaskDataProcessor | deleteTask | — |
| `deleteUploadedFile` | deleteUploadedFileProcessor | — | — |
| `doMfiBranchCollection` | validateDoMfiWebCollectionProcessor → populateBasicUserDetailsProcessor → doWebCollectionsProcessor → tempProcessToRemoveDenominationPlaceholders → generateReportProcessor → createCollReferenceAddi... | — | — |
| `doMfiFieldCollection` | validateMfiCollectionProcessor → validateCollectorCashInHandProcessor → doMfiCollectionsProcessor → updateCollectionInCollectionTempDataProcessor → generateGeoAuditActivityProcessor | — | — |
| `downloadConfirmPaymentUploadedFile` | downloadConfirmPaymentUploadedFileProcessor | — | — |
| `downloadExcelAgencyUploadUploadedFile` | downloadExcelAgencyUploadUploadedFileProcessor | — | — |
| `downloadFinnoneLoanCorrectionUploadedFile` | downloadFinnoneLoanCorrectionFileProcessor | — | — |
| `downloadLoanCategoryUploadUploadedFile` | downloadLoanCategoryUploadUploadedFileProcessor | — | — |
| `downloadLoanExceptionUploadUploadedFile` | downloadLoanExceptionUploadUploadedFileProcessor | — | — |
| `downloadPriorityCalendarUploadedFile` | downloadPriorityCalendarUploadedFileProcessor | — | — |
| `downloadRescheduleDataUploadUploadedFile` | downloadRescheduleDataUploadedFileProcessor | — | — |
| `downloadUploadedFile` | downloadUploadedFileProcessor | — | — |
| `executeLCSPortfolioTransfer` | transferLCSPortfolioByVillageProcessor | — | regExp(${transfer_type})=PRTFL_TRNSFR_EMPL |
| `fetchCdsRecords` | fetchCdsRecordsProcessor | — | — |
| `fetchLMSUpdate` | fetchLMSUpdateProcessor | — | — |
| `fetchLMSUpdatesForCollections` | fetchLMSUpdatesForCollectionsProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `forwardSupervisoryReview` | nextSupervisorDetailsProcessor → saveSupervisoryReviewProcessor → getSupervisoryReviewTaskDetailsProcessor → createSupervisroyReviewTaskProcessor → updatedTaskStatusProcessor → dummyProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT; regExp(${supervisor_not_present})=false; regExp(${supervisor_not_present})=true |
| `generateBatch` | getCollectionsForBatchCreationProcessor → setCommonAttributesProcessor → generateBatchProcessor → updateChallanDetailsToLMSProcessor → createDenominationDetailsForBatchReferenceProcessor → activity... | — | — |
| `generateCDSForCasaPayment` | generateCDSForCasaPaymentProcessor → tempProcessToRemoveDenominationPlaceholders → generateReportProcessor → createCollectionGroupCasaCdslDetailsProcessor | — | — |
| `generatePaymentLink` | cancelExistingPaymentLinkProcessor → generatePaymentLinkProcessor | — | regExp(${function_sub_code})=REGENERATE |
| `getAgencyCode` | getAgencyCodeProcessor | — | — |
| `getAttemptsTrialMode` | getAttemptsTrialModeProcessor → dummyProcessor | — | — |
| `getAttemptsTrialNextAction` | getAttemptsTrialNextActionProcessor → dummyProcessor | — | — |
| `getAttemptsTrialNonPayReason` | getAttemptsTrialNonPayReasonProcessor → dummyProcessor | — | — |
| `getAttemptsTrialOutcome` | getAttemptsTrialOutcomeProcessor → dummyProcessor | — | — |
| `getAttemptsTrialPersonContacted` | getAttemptsTrialPersonContactedProcessor → dummyProcessor | — | — |
| `getAttemptsTrialPlaceContacted` | getAttemptsTrialPlaceContactedProcessor → dummyProcessor | — | — |
| `getBatchInquiryReport` | getBatchIdsStatusProcessor → getBatchInquiryReportProcessor | — | regExp(${function_sub_code})=BY_BATCH_IDS; regExp(${function_sub_code})=DEFAULT |
| `getBulkUploadTemplate` | getBulkUploadTemplateProcessor | — | — |
| `getCdsLoanCollectionDetails` | getDetailsByBatchReferenceNumberProcessor → fetchLMSUpdatesForCollectionsProcessor → getGroupLoanCollectionDetailsProcessor → getLoanCollectionDetailsProcessor → mergeLoanCollectionDetailsProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `getCollListForDelegation` | getCollListForDelegationProcessor → dummyProcessor | — | — |
| `getCollectedDetailsForRectification` | getCollectedDetailsForRectificationProcessor → dummyProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getCollectionCalendarCountDetails` | fetchGroupProductsProcessor → getCalendarCountForGroupProcessor → getCalendarCountForIndividualProcessor → formatCountDetailsProcessor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDL |
| `getCollectionDemandBannerDetails` | getIndlDemandBannerDetailsV2Processor → getGroupDemandBannerDetailsV2Processor | — | regExp(${function_sub_code})=GROUP; regExp(${function_sub_code})=INDIVIDUAL |
| `getCollectionDetailsForCustomerInteractionListOLd` | setCommonAttributesProcessor → getCollectionDetailsForCustomerInteractionListProcessor → addPriorityDataToInteractionListProcessor | — | — |
| `getCollectionDetailsForInfoIcon` | getCollectionDetailsForInfoIconProcessor → getFinnoneCollectionDetailsForInfoIconProcessor → dummyProcessor | — | regExp(${function_sub_code})=FINNONE; regExp(${function_sub_code})=NOVOPAY |
| `getCollectionInfoListOld` | validateOfficeProcessor → getCollectionInfoListProcessor → getCollectionPayableDetailsProcessor → populatePriorityDataInDetailsProcessor → sortPriorityDetailsProcessor → dummyProcessor | — | regExp(${calender_type})=PRIO_CLNDR; regExp(${function_sub_code})=BY_ADVANCE_SEARCH |
| `getCollectionPayableDetails` | getCollectionPayableDetailsProcessor | — | — |
| `getCollectionTempData` | getCollectionTempDataProcessor → dummyProcessor | — | — |
| `getCollectionsForBatchCreation` | getCollectionsForBatchCreationProcessor | — | — |
| `getContactDetailsForFinnoneCustomer` | getContactDetailsForFinnoneCustomerProcessor → dummyProcessor → getContactDetailsForFinnoneCustomerProcessor → getContactDetailsForFinnoneGroupProcessor | — | regExp(${function_sub_code})=BY_CUSTOMER; regExp(${function_sub_code})=BY_GROUP; regExp(${function_sub_code})=DEFAULT |
| `getCustomerInteractionForCollectionList` | setCommonAttributesProcessor → getCustomerInteractionListProcessorV2 → addPriorityDataToInteractionListProcessor | — | — |
| `getCustomerInteractionHistoryList` | getCustomerInteractionHistoryListProcessor | — | — |
| `getCustomerLoanAccountList` | getCustomerLoanAccountDetailsWrapperProcessor | — | — |
| `getCustomerWithInsufficientCasaBalance` | getCustomerWithInsufficientCasaBalanceProcessor | — | — |
| `getDemandListForField` | — | — | regExp(${function_sub_code})=DEFAULT |
| `getDenominationDetailsForReferences` | getDenominationDetailsForReferencesProcessor | — | — |
| `getEmployeeListToReassignSupervisoryReview` | getEmployeeListToReassignSupervisoryReviewProcessor | — | — |
| `getFinnoneCustomerDetailsByLAN` | getFinnoneCustomerDetailsByLAN | — | — |
| `getFinnoneKeyMemberDetailsForGroup` | getFinnoneKeyMemberDetailsForGroupProcessor | — | — |
| `getForeclosureAmountForFinnoneCollection` | getForeclosureAmountForFinnoneCollectionProcessor | — | — |
| `getGroupCollBannerDetails` | getGroupCollBannerV2Processor → dummyProcessor | — | regExp(${function_sub_code})!GROUP_ID_LIST; regExp(${function_sub_code})=GROUP_ID_LIST |
| `getGroupCollectionDemandList` | getGroupCollectionDemandListV2Processor | — | regExp(${function_sub_code})=DEFAULT |
| `getGroupCollectionInfoList` | validateOfficeProcessor → getGroupCollectionInfoListProcessor | — | regExp(${function_sub_code})=BY_ADVANCE_SEARCH |
| `getGroupDetailsWithInsufficientCasaBalance` | getGroupDetailsWithInsufficientCasaBalanceProcessor | — | — |
| `getGroupLoanCollectionDetails` | fetchLMSUpdatesForCollectionsProcessor → getGroupLoanCollectionDetailsProcessor | — | — |
| `getGroupLoanDemandDetails` | getGroupLoanDemandDetailsProcessorV2 | — | — |
| `getGroupMemberName` | getGroupMemberNameProcessor | — | — |
| `getGroupPaymentInfoList` | getGroupPaymentInfoListProcessorV2 | — | — |
| `getGroupsWithInsufficientCasaBalance` | getGroupsWithInsufficientCasaBalanceProcessor | — | — |
| `getIndividualCollectionDemandList` | getIndividualCollectionDemandListProcessorV2 | — | regExp(${function_sub_code})=DEFAULT |
| `getIndlLoanDemandDetails` | getIndlLoanDemandDetailsProcessorV2 | — | — |
| `getIndvidualCollBannerDetails` | getIndvidualCollBannerDetailsV2Processor → dummyProcessor | — | — |
| `getLastRecordAttemptForCollection` | getLastRecordAttemptForCollectionProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `getLoanCollectionDetails` | fetchLMSUpdatesForCollectionsProcessor → getLoanCollectionDetailsProcessor | — | — |
| `getMembersDetailsWithInsufficientCasaBalance` | getMembersDetailsWithInsufficientCasaBalanceProcessor | — | — |
| `getNearByCollectionDetails` | getNearByCollectionDetailsProcessor | — | — |
| `getPastCollectionIdsForCollectionIds` | getPastCollectionIdsForCollectionIdsProcessor | — | — |
| `getPriorityCollectionDetailsOld` | setCommonAttributesProcessor → getNonGroupedProrityCalendarLoanProcessor → addDetailsToPriorityLoanProcessor → applyFilterOnPriorityProcessor → getPriorityDetailsProcessor → reStructurePriorityDeta... | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=WEB; regExp(${operation_mode})=MOBILE |
| `getPriorityCountForCalendarOld` | setCommonAttributesProcessor → getProrityCalendarLoanProcessor → getPriorityCountForCalendarProcessor → dummyProcessor | — | — |
| `getPtpCalendarCountDetails` | fetchGroupProductsProcessor → getPtpCalenderCountProcessor → formatCountDetailsProcessor | — | — |
| `getRecordAttemptDetails` | getRecordAttemptsDetailsProcessor | — | — |
| `getScheduleDetails` | getScheduleDetailsProcessor | — | — |
| `getScheduledBatchList` | getScheduledBatchDetailsProcessor | — | — |
| `getVillagePaymentPortfolioSummary` | getVillagePaymentPortfolioSummaryProcessor | — | — |
| `getVisitStatus` | setCommonAttributesProcessor → getVisitStatusForEmployeeProcessor → dummyProcessor | — | — |
| `getVymoNovopayMasterCode` | getVymoNovopayMasterCodeProcessor → getVymoCodeMapMasterDataProcessor | — | regExp(${function_sub_code})=GET_DATA_TYPE_DETAILS; regExp(${function_sub_code})=GET_MASTER_DATA |
| `increaseCDSPrintCount` | increaseCDSPrintCountProcessor | — | — |
| `loanAccountCollection` | checkForExistingForeClosureProcessor → createForeclosueCollectionProcessor → createPaymentTrackingProcessor → createPaymentActivityProcessor → createCollectionReferenceDetailsProcessor → updateStat... | — | regExp(${function_sub_code})=FIELD; regExp(${function_sub_code})=WEB; regExp(${purpose})=FORECLOSURE |
| `panNameMatchLogicValidation` | panNameMatchLogicValidationProcessor → dummyProcessor | — | — |
| `processBulkUploadFile` | processBulkUploadFileProcessor → dummyProcessor | — | — |
| `pushPendingLMSUpdates` | pushLMSUpdateProcessor → pushPendingLMSUpdatesBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `reassignSupervisoryReview` | nextSupervisorDetailsProcessor → saveSupervisoryReviewProcessor → updatedTaskStatusProcessor → populateNotificationParamsForPushNotifAndSMSProcessor → dummyProcessor → getSupervisoryReviewTaskDetai... | — | regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=REASSIGN; regExp(${task})=CLOSE; regExp(${task})=CLOSE_AND_CREATE |
| `rejectUploadedFile` | rejectUploadedFileProcessor | — | — |
| `reminderForPtpCalenderCustomerJob` | reminderForPtpCalenderCustomerJobProcessor | — | — |
| `reminderForPtpCalenderUserJob` | reminderForPtpCalenderUserJobProcessor | — | — |
| `reminderForPtpCalenderUserJobRm` | reminderForPtpCalenderUserJobRmProcessor | — | — |
| `reviewerVerificationHistory` | nextSupervisorDetailsProcessor → getSupReviewBulkMasterDataProcessor → getSupervisorReviewsUnderUserProcessor → dummyProcessor → getSupervisorReviewsUserProcessor → dummyProcessor | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=USER |
| `rollbackLCSPortfolioTransfer` | rollbackLCSPortfolioTransferProcessor | — | — |
| `runFinoneReverseJob` | runFinoneReverseJobProcessor | — | — |
| `runInboundFinoneJob` | runInboundFinoneJobProcessor | — | — |
| `runInboundNpHandoffJob` | runInboundNpHandoffJobProcessor | — | — |
| `runInboundNpRevTrailsJob` | runInboundNpRevTrailsJobProcessor | — | — |
| `runInboundStaticFinoneJob` | runInboundStaticFinoneJobProcessor | — | — |
| `saveCollectionConsentInfo` | saveCollectionConsentInfoProcessor | — | — |
| `saveCustomerContactDetails` | saveCustomerContactDetailsProcessor | — | — |
| `sendAttemptReportAfterThresholdAttempt` | validateCollectionIdInListProcessor → sendRecordAttemptReportProcessor | — | — |
| `submitCollForDelegation` | submitCollForDelegationProcessor → dummyProcessor | — | — |
| `submitSupervisoryReview` | nextSupervisorDetailsProcessor → submitSupervisoryReviewProcessor → updatedSupervisoryReviewTaskStatusProcessor → dummyProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=DEFAULT |
| `updateCancelCds` | updateCancelCdsProcessor → updatedTaskStatusProcessor → dummyProcessor → dummyProcessor | — | regExp(${function_sub_code})=APPROVE; regExp(${function_sub_code})=REJECT |
| `updateCollectionCustomerInfo` | updateCollectionCustomerInfoInBulkProcessor → updateCollectionCustomerInfoProcessor | — | regExp(${function_sub_code})=BULK; regExp(${function_sub_code})=EDIT_DEMOGRAPHICS |
| `updateCollectionOfficeInfo` | updateCollectionOfficeInfoProcessor → dummyProcessor | — | — |
| `updateCollectionRectificationOnApproval` | updateCollectionRectificationOnApprovalProcessor → dummyProcessor → dummyProcessor | — | regExp(${function_sub_code})=APPROVE; regExp(${function_sub_code})=REJECT; regExp(${reject_reason_code})=OTHERS|Others|others |
| `updateCustomerPan` | UpdateCustomerPanProcessor | — | regExp(${function_sub_code})=DEFAULT |
| `updateDpdBatch` | updateDpdProcessor | — | — |
| `updateExpiredScheduledBatchStatus` | updateExpiredScheduledBatchStatusProcessor → updateExpiredScheduledBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `updateOfflineCollectedReceipt` | updateOfflineCollectedReceiptProcessor | — | — |
| `updatePaymentStatus` | updatePaymentStatusProcessor | — | — |
| `updateSchedulePayment` | updateSchedulePaymentProcessor → sendSmsNotificationForBranchCollection | — | — |
| `updateScheduledBatchExpiryDate` | updateScheduledBatchCutExpiryDateProcessor | — | — |
| `updateSupervisoryReviewStatus` | updateSupervisoryReviewStatusProcessor → dummyProcessor | — | — |
| `validateLCSRestrictedActivitiesForPTrfr` | validateLCSRestrictedActivitiesForPTrfrProcessor | — | regExp(${transfer_type})=PRTFL_TRNSFR_EMPL |
| `viewBulkConfirmPaymentFileStatus` | viewBulkConfirmPaymentFileStatusProcessor | — | — |
| `viewBulkExcelAgencyUploadFileStatus` | viewBulkExcelAgencyUploadFileStatusProcessor | — | — |
| `viewBulkFinnoneLoanCorrectionFileStatus` | viewBulkFinnoneLoanCorrectionFileStatusProcessor | — | — |
| `viewBulkLoanCategoryUploadFileStatus` | viewBulkLoanCategoryUploadFileStatusProcessor | — | — |
| `viewBulkLoanExceptionUploadFileStatus` | viewBulkLoanExceptionUploadFileStatusProcessor | — | — |
| `viewBulkPriorityCalendarFileStatus` | viewBulkPriorityCalendarFileStatusProcessor | — | — |
| `viewBulkRescheduleDataUploadFileStatus` | viewBulkRescheduleDataUploadFileStatusProcessor | — | — |
| `viewBulkUploadFileStatus` | viewBulkUploadFileStatusProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-payments/deploy/application/orchestration/orc_mfi_cross_schema.xml`
**Owner service:** `novopay-platform-payments` 
**Root element:** `Payments`  
**Requests:** 7

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `getCollectionCountForCollectorV2` | getCollectionCountForCollectorV2Processor → dummyProcessor | — | regExp(${function_code})=FIELD |
| `getCollectionInfoList` | validateOfficeProcessor → getCollectionInfoListProcessorV2 → getCollectionPayableDetailsProcessorV2 → populatePriorityDataInDetailsProcessorV2 → sortPriorityDetailsProcessor → dummyProcessor | — | regExp(${calender_type})=PRIO_CLNDR; regExp(${function_sub_code})=BY_ADVANCE_SEARCH |
| `getCollectionsList` | getCollectionsListV2Processor | — | regExp(${for_offline_collection})!true; regExp(${for_offline_collection})=true; regExp(${function_code})=MFI_COLLECTION; regExp(${function_code})=PRIORITY; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=MFI_NEARBY; regExp(${function_sub_code})=PTP; regExp(${nearby_collection_flag})=1 … (+4) |
| `getGroupCollectionDetailsV2` | fetchLMSUpdatesForCollectionsProcessor → getGroupCollectionDetailsV2Processor | — | regExp(${for_offline_collection})!true; regExp(${for_offline_collection})=true |
| `getIndividualCollectionDetailsV2` | fetchLMSUpdatesForCollectionsProcessor → getIndividualCollectionDetailsV2Processor | — | regExp(${for_offline_collection})!true; regExp(${for_offline_collection})=true |
| `getPriorityCollectionDetails` | setCommonAttributesProcessor → getNonGroupedProrityCalendarLoanProcessorV2 → addDetailsToPriorityLoanProcessorV2 → applyFilterOnPriorityProcessor → getPriorityDetailsProcessor → reStructurePriority... | — | regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=WEB; regExp(${operation_mode})=MOBILE |
| `getPriorityCountForCalendar` | setCommonAttributesProcessor → getProrityCalendarLoanV2Processor → getPriorityCountForCalendarV2Processor → dummyProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-payments/deploy/application/orchestration/product_accounting.xml`
**Owner service:** `novopay-platform-payments` 
**Root element:** `Payments`  
**Requests:** 2

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `collectionLoanRepayment` | collectionRepaymentProcessor | — | — |
| `recurringPayment` | recurringPaymentProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-task/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `novopay-platform-task` 
**Root element:** `Task`  
**Requests:** 22

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `bulkCreateTask` | setCommonAttributesProcessor → bulkTaskCreateProcessor | — | — |
| `bulkUpdateTaskStatus` | setCommonAttributesProcessor → bulkUpdateTaskStatusProcessor → populateUserstoryProcessor | — | — |
| `createOrUpdateTask` | duplicateTaskValidator → populateUserDetails → populateTaskDetailsProcessor → setCommonAttributesProcessor → getMakerCheckerEnabledForTaskTypeProcessor → constructRequestDataForApproval → deleteDra... | submitApplication | regExp(${function_code})!APPROVE; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=false; regExp(${maker_checker_enabled})=true … (+15) |
| `createTaskWorkflow` | populateUserDetails → createTaskWorkFlowProcessor | — | — |
| `deleteTask` | populateUserDetails → setCommonAttributesProcessor → getTaskDetailsProcessor → getTaskTypeDetailsProcessor → getTaskLocationDetailsProcessor → getTaskActivityDetailsProcessor → constructTaskFieldsD... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_sub_code})=DEFAULT; regExp(${function_sub_code})=TASKTYPEIDENTIFIER; regExp(${maker_checker_enabled})=false; regExp(${maker_checker_enabled})=true |
| `deleteTaskType` | deleteTaskTypeProcessor | — | — |
| `getEmployeeChildren` | getEmployeeFromUserID → getEmployeeDetailsProcessor → getImmediateChildrenOfOfficeProcessor → getEmployeeDetailsForOfficeList → getEmployeeProfiles → getEmployeeDetailsProcessor → getAllChildrenOfO... | — | regExp(${children_type})=ALL; regExp(${children_type})=TEAM |
| `getLifecycleList` | getLifecycleListProcessor | — | — |
| `getOfficeBreadcrumbs` | getOfficeBreadcrumbHierarchyProcessor → populateUserstoryProcessor | — | — |
| `getPendingTaskForUserId` | getPendingTaskForUserIdProcessor | — | — |
| `getTaskDetails` | getTaskDetailsProcessor → getTaskTypeDetailsProcessor → getTaskLocationDetailsProcessor → getTaskActivityDetailsProcessor → constructTaskFieldsDetailsProcessor → populateUserstoryProcessor | — | — |
| `getTaskList` | validateAdminPermissionProcessor → setCommonAttributesProcessor → populateUserDetails → getEmployeeFromUserID → dummyProcessor → getUserTeamList → getUserAllTeamList → populateOfficeIdsHierBasedOnL... | — | regExp(${function_sub_code})!ROLE; regExp(${function_sub_code})=ORDEREDBYFIELD; regExp(${function_sub_code})=USER_ID; regExp(${search_domain})=USER; regExp(${search_domain})=USER_ALL; regExp(${search_domain})=USER_TEAM |
| `getTaskListCount` | populateOfficeIdsHierBasedOnLoggedInUserRoleProcessor → getTaskListCountProcessor | — | — |
| `getTaskTypeDetails` | getTaskTypeDetailsProcessor | — | — |
| `getTaskTypeList` | getTaskTypeListProcessor → getTaskTypeListForDelegationProcessor | — | regExp(${function_sub_code})=TASK_DELEGATION |
| `getTaskTypeVersion` | getTaskTypeVersionProcessor | — | — |
| `rejectExpiredBatchJob` | populateUserDetails → rejectExpiredBatchJobProcessor | — | — |
| `reopenClosedTask` | reopenClosedTaskProcessor | — | — |
| `triggerNotifications` | triggerNotificationsProcessor → triggerNotificationsBatchProcessor | — | regExp(${function_sub_code})=BATCH; regExp(${function_sub_code})=DEFAULT |
| `updateTaskStatus` | populateTaskDetails → setCommonAttributesProcessor → validateUserTaskStatusProcessor → validateUserForAssigningTaskProcessor → assignTaskProcessor → populateTaskActivityProcessor → populateUserstor... | — | regExp(${function_sub_code})=WEB |
| `updateTaskStatusForTaskIds` | updateTaskStatusForTaskIdsProcessor | — | — |
| `updateTaskWorkflow` | populateUserDetails → dummyProcessor → dummyProcessor → dummyProcessor → dummyProcessor → updateTaskWorkflowProcessor → populateNotificationDataProcessor → taskPushNotificationProducer → taskApprov... | — | regExp(${function_code})=DEFAULT; regExp(${function_code})=REJECT; regExp(${function_code})=UPDATE; regExp(${notify_status})=REJECT; regExp(${reject_flow})=false; regExp(${reject_flow})=true |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-task/deploy/application/orchestration/mfi_orchestration.xml`
**Owner service:** `novopay-platform-task` 
**Root element:** `Task`  
**Requests:** 24

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `approveTaskForCollection` | approveTaskForCollectionProcessor | — | — |
| `calculateUserTatBatch` | calculateUserTatBatchProcessor | — | — |
| `createOrUpdateMfiTaskByCode` | setCommonAttributesProcessor → checkIfTaskIdPresentProcessor → removeTaskIdAndUpdateCurrentStatusProcessor → createOrUpdateMfiTaskByCodeProcessor → populateUserstoryProcessor | updateTaskStatus | regExp(${function_sub_code})=CLOSE_AND_CREATE; regExp(${previous_task_present})=true |
| `createOrUpdateTaskMfi` | populateUserDetails → populateTaskDetailsProcessor → populateTaskFieldDetailsMfiProcessor → setCommonAttributesProcessor → getMakerCheckerEnabledForTaskTypeProcessor → constructRequestDataForApprov... | submitApplication | regExp(${function_code})!APPROVE; regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=DEFAULT|MFI_ATTEMPT_REC; regExp(${function_code})=RESUBMIT; regExp(${function_sub_code})=CREATE|CLOSE_AND_CREATE; regExp(${function_sub_code})=UPDATE; regExp(${maker_checker_enabled})=false … (+7) |
| `createTaskBatch` | createTaskBatchProcessor | — | — |
| `createTaskDelegation` | setCommonAttributesProcessor → createTaskDelegationProcessor → approvalTaskDelegationPreProcessor → createOrUpdateTaskForApprovalProcessor → updateTaskDelegationProcessor → taskDelegatorProcessor →... | — | regExp(${function_sub_code})=CREATE |
| `deleteTaskMfi` | populateUserDetails → setCommonAttributesProcessor → getTaskDetailsProcessor → getTaskTypeDetailsMfiProcessor → getTaskLocationDetailsProcessor → getTaskActivityDetailsProcessor → constructTaskFiel... | submitApplication | regExp(${function_code})=APPROVE; regExp(${function_code})=DEFAULT; regExp(${function_code})=ROLLBACK; regExp(${maker_checker_enabled})=false; regExp(${maker_checker_enabled})=true |
| `executeTaskPortfolioTransfer` | transferTaskPortfolioByVillageProcessor | — | regExp(${transfer_type})=PRTFL_TRNSFR_EMPL |
| `getHomeScreenCount` | getHomeScreenCountProcessor | — | — |
| `getLosTaskCount` | getLosTaskCountProcessor | — | regExp(${function_code})=DEFAULT; regExp(${function_sub_code})=FILTER |
| `getLosTaskList` | getLosTaskListProcessor → paginateLOSTaskListProcessor | — | regExp(${function_sub_code}_${function_code})=DEFAULT_DEFAULT; regExp(${function_sub_code}_${function_code})=SEARCH_DEFAULT |
| `getPoolTasks` | getPoolTasksProcessor | — | — |
| `getRoleCodesByTaskIds` | getRoleCodesByTaskIdsProcessor | — | — |
| `getTaskDetailsMfi` | getTaskDetailsProcessor → getTaskTypeDetailsMfiProcessor → getTaskLocationDetailsProcessor → getTaskActivityDetailsProcessor → constructTaskFieldsDetailsProcessor → populateUserstoryProcessor | — | — |
| `getTaskSubTypeList` | getTaskSubTypeListProcessor | — | — |
| `getTasklistForDelegation` | getTaskListForDeligationProcessor | — | — |
| `notifyUsersForPendingTasksJob` | notifyUsersForPendingTasksJobProcessor | — | — |
| `rejectTaskForCollection` | rejectTaskForCollectionProcessor | — | — |
| `rollbackTaskPortfolioTransfer` | rollbackTaskPortfolioTransferProcessor | — | — |
| `sendMeetingCenterPendingNoti` | sendMeetingCenterPendingNotiProcessor | — | — |
| `updateDataCurrentTaskAndCreateNewTask` | updateDataCurrentTaskAndCreateNewTaskProcessor → dummyProcessor | — | — |
| `updateTaskDelegation` | setCommonAttributesProcessor → updateTaskDelegationProcessor → updateTaskDelegationProcessor → updateTaskDelegationProcessor → createOrUpdateTaskForApprovalProcessor → updateLosAssigneeContributorP... | — | regExp(${function_sub_code})=APPROVE; regExp(${function_sub_code})=APPROVE|REJECT; regExp(${function_sub_code})=REJECT; regExp(${function_sub_code})=UPDATE |
| `updateTaskStatusAndCallApi` | populateTaskDetails → setCommonAttributesProcessor → assignTaskProcessor → populateTaskActivityProcessor → callApiAfterUpdateProcessor | — | — |
| `validateCashLimitIncreaseTaskForSo` | validateCashLimitIncreaseTaskForSoProcessor | — | regExp(${transfer_type})=PRTFL_TRNSFR_EMPL |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `novopay-platform-task/deploy/application/orchestration/orc_collection.xml`
**Owner service:** `novopay-platform-task` 
**Root element:** `Task`  
**Requests:** 5

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `getCollectionDepositTimeExtensionHistory` | getCollectionDepositTimeExtensionHistoryProcessor → dummyProcessor | — | — |
| `getCollectionLimitIncreaseHistory` | getCollectionLimitIncreaseHistoryProcessor → dummyProcessor | — | — |
| `getTaskActivityList` | getTaskActivityListProcessor | — | — |
| `getTaskListByIds` | getTaskListByIdsProcessor | — | — |
| `updateAooTaskDetailsNewApprover` | updateAooTaskDetailsNewApproverProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.

## `trustt-platform-reporting/deploy/application/orchestration/ServiceOrchestrationXML.xml`
**Owner service:** `trustt-platform-reporting` 
**Root element:** `Reporting`  
**Requests:** 116

| API / Request name | Processors (beans, order) | Internal/API calls | Control branches (summary) |
|--------------------|----------------------------|--------------------|----------------------------|
| `almActiveLoanDailyExtractJob` | almActiveLoanDailyExtractJobProcessor | — | — |
| `almClosedLoanDailyExtractJob` | almClosedLoanDailyExtractJobProcessor | — | — |
| `assetBaseFileSyncJob` | assetBaseFileSyncJobProcessor | — | — |
| `bulkFileToSGNeftTransactionSummaryJob` | bulkFileToSGNeftTransactionSummaryJobProcessor | — | — |
| `bulkOutboundAssetBaseFileJob` | outboundAssetBaseFileJobProcessor | — | — |
| `bulkOutboundAssetBaseSummCntJob` | outboundAssetBaseSummCntJobProcessor | — | — |
| `bulkOutboundCoBorrowerFileJob` | outboundCoBorrowerFileJobProcessor | — | — |
| `bulkOutboundCoborrowerSummJob` | outboundCoborrowerSummaryFileJobProcessor | — | — |
| `bulkOutboundConsumerBaseFileJob` | outboundConsumerBaseFileJobProcessor | — | — |
| `bulkSGToNeftTransactionSummaryJob` | bulkSGToNeftTransactionSummaryJobProcessor | — | — |
| `cddOtrJob` | generateCddOtrJobProcessor | — | — |
| `chequeBounceExtractJob` | chequeBounceExtractJobProcessor | — | — |
| `cicMonthlyGroupLevelExtractJob` | setCommonAttributesProcessor → cicMonthlyGroupLevelExtractJobProcessor | — | — |
| `cicMonthlyMemberLevelExtractJob` | setCommonAttributesProcessor → cicMonthlyMemberLevelExtractJobProcessor | — | — |
| `collectionEfficiencyExtractJob` | generateCollectionEfficiencyJobProcessor | — | — |
| `createUAMPopReport` | uamPopulationReportProcessor | — | — |
| `creditProductivityExtractJob` | setCommonAttributesProcessor → creditProductivityExtractJobProcessor | — | — |
| `dpdBucketJob` | dpdBucketJobProcessor | — | — |
| `edBaseJob` | edBaseJobProcessor | — | — |
| `fetchGroupRenewalDetails` | groupRenewalPolicyUploadDetailsProcessor | — | — |
| `fileTransferAndDownloadBatchJob` | fileTransferAndDownloadBatchJobProcessor | — | — |
| `flatLanAppGrpStageTatJob` | flatLoanAppGrpStageTatJobProcessor | — | — |
| `generateAPYBaseNetDataExtractJob` | setCommonAttributesProcessor → generateAPYBaseNetDataExtractJobProcessor | — | — |
| `generateConsolidatedReports` | generateConsolidatedReportsProcessor | — | regExp(${function_code})=REPORTS; regExp(${function_sub_code})=SCHEDULED_REPORTS |
| `generateCreditBaseGroupDataJob` | generateCreditBaseGroupDataJobProcessor | — | — |
| `generateCreditBaseIndvLoanDataJob` | generateCreditBaseIndvLoanDataJobProcessor | — | — |
| `generateCreditRawDumpExtractJob` | generateCreditRawDumpExtractJobProcessor | — | — |
| `generateCreditReportingExtractJob` | generateCreditReportsExtractJobProcessor | — | — |
| `generateCscVleDataExtractJob` | setCommonAttributesProcessor → generateCscVleDataExtractJobProcessor | — | — |
| `generateCustomerLevelDataExtractJob` | generateCustomerLevelDataExtractJobProcessor | — | — |
| `generateCustomerLevelDumpExtractJob` | setCommonAttributesProcessor → generateCustomerLevelDumpExtractJobProcessor | — | — |
| `generateDemandListReportExtractJob` | setCommonAttributesProcessor → generateDemandListReportExtractJobProcessor | — | — |
| `generateDeviceDetailsExtractJob` | setCommonAttributesProcessor → generateDeviceDetailsProcessor | — | — |
| `generateDisbursementAdviceReportExtractJob` | generateDisbursementAdviceReportExtractJobProcessor | — | — |
| `generateEditBetReportJob` | generateEditBetReportJobProcessor | — | — |
| `generateEmployeeRoleHierarchyExtractJob` | generateEmployeeRoleHierarchyExtractJobProcessor | — | — |
| `generateGroupDataExtractJob` | setCommonAttributesProcessor → generateGroupDataExtractJobProcessor | — | — |
| `generateGroupLevelDemandListReportExtractJob` | setCommonAttributesProcessor → generateGroupLevelDemandListReportExtractJobProcessor | — | — |
| `generateGroupLevelDumpExtractJob` | setCommonAttributesProcessor → generateGroupLevelDumpExtractJobProcessor | — | — |
| `generateGroupLevelPosExtractJob` | setCommonAttributesProcessor → generateGroupLevelPosExtractJobProcessor | — | — |
| `generateHhiReportJob` | generateHhiReportJobProcessor | — | — |
| `generateInsuranceReportJob` | generateInsuranceReportProcessor | — | — |
| `generateJobStatisticsReport` | generateJobStatisticsExtractJobProcessor | — | — |
| `generateLoanCardFactSheet` | generateFactSheetExtractJobProcessor | — | — |
| `generateLoanCardIndividualReportExtractJob` | setCommonAttributesProcessor → generateLoanCardIndividualReportExtractJobProcessor | — | — |
| `generateLoginBaseGroupDumpExtractJob` | setCommonAttributesProcessor → generateLoginBaseGroupDumpExtractJobProcessor | — | — |
| `generateLoginGroupBaseExtractJob` | setCommonAttributesProcessor → generateLoginGroupBaseDataExtractJobProcessor | — | — |
| `generateMergeReportExtractJob` | setCommonAttributesProcessor → generateMergeReportExtractJobProcessor | — | — |
| `generateNrlmNonRegisteredGroupReportJob` | setCommonAttributesProcessor → generateNRLMNonRegisteredGroupJobProcessor | — | — |
| `generateOnePlusExtractJob` | generateOnePlusExtractJobProcessor | — | — |
| `generateOpsDumpDataExtractJob` | setCommonAttributesProcessor → generateOpsDumpDataExtractJobProcessor | — | — |
| `generatePanEnquiryVolumeReportJob` | generatePanEnquiryVolumeReportProcessor | — | — |
| `generatePerformanceSummaryJob` | generatePerformanceSummaryJobProcessor | — | — |
| `generatePosReportExtractJob` | setCommonAttributesProcessor → generatePosExtractJobProcessor | — | — |
| `generatePosidexBadFileExtractJob` | generatePosidexBadFileExtractJobProcessor | — | — |
| `generatePosidexGoodFileExtractJob` | generatePosidexGoodFileExtractJobProcessor | — | — |
| `generatePosidexRejectFileExtractJob` | generatePosidexRejectFileExtractJobProcessor | — | — |
| `generateRBIAdfAccountDetailsExtractJob` | generateRbiAdfAccountDetailsExtractJobProcessor | — | — |
| `generateRBIAdfAccountDetailsExtractJobV2` | generateRbiAdfAccountDetailsExtractJobProcessorV2 | — | — |
| `generateRBIAdfAddressDetailsExtractJob` | generateRbiAdfAddressDetailsExtractJobProcessor | — | — |
| `generateRBIAdfBankDetailsExtractJob` | generateRbiAdfBankDetailsExtractJobProcessor | — | — |
| `generateRBIAdfCustomerDetailsExtractJob` | generateRbiAdfCustomerDetailsExtractJobProcessor | — | — |
| `generateRBIAdfCustomerLinkageExtractJob` | generateRbiAdfCustomerLinkageExtractJobProcessor | — | — |
| `generateRBIAdfDailyBlankExtractJob` | generateRbiAdfDailyBlankExtractJobProcessor | — | — |
| `generateRBIAdfGlDetailsExtractJob` | generateRbiAdfGlDetailsExtractJobProcessor | — | — |
| `generateRBIAdfInterestIncomeExtractJob` | generateRbiAdfInterestIncomeExtractJobProcessor | — | — |
| `generateRBIAdfLegalSecurityExtractJob` | generateRbiAdfLegalSecurityExtractJobProcessor | — | — |
| `generateRBIAdfMonthlyBlankExtractJob` | generateRbiAdfMonthlyBlankExtractJobProcessor | — | — |
| `generateRaftaExtractJob` | generateRaftaExtractJobProcessor | — | — |
| `generateRepaymentScheduleExtractJob` | setCommonAttributesProcessor → generateRepaymentScheduleReportExtractJobProcessor | — | — |
| `generateReport` | generateReportProcessor → spanSoControlProcessor → spanRmControlProcessor → generateSOPerformanceSummaryProcessor → generateAPYSummaryProcessor → generateFinnOneRevTrialProcessor → generateBatchIdI... | — | regExp(${report_category})=CUSTOM; regExp(${report_category})=DEFAULT; regExp(${report_code})=AOO_EMPLOYEE_WORK_AREA_REPORT; regExp(${report_code})=AOO_OFFICE_WORK_AREA_REPORT; regExp(${report_code})=APY-SUMRY; regExp(${report_code})=BATCH-ID-INQ-STATUS; regExp(${report_code})=BRANCH-CODE-LVL-TB-REPORT; regExp(${report_code})=CAD-LIMIT … (+46) |
| `generateSIOTRExtractJob` | setCommonAttributesProcessor → generateSiotrExtractJobProcessor | — | — |
| `generateSOBaseExtractJob` | setCommonAttributesProcessor → generateSOBaseExtractJobProcessor | — | — |
| `generateSOPLPBaseExtractJob` | setCommonAttributesProcessor → generateSOPLPBaseExtractJobProcessor | — | — |
| `generateSRSGovernanceReportJob` | generateSRSGovernanceReportProcessor | — | — |
| `generateSRSNPGlBalanceReportJob` | generateSRSNPGlBalanceReportProcessor | — | — |
| `generateSRSNPGlTransactionsReportJob` | generateSRSNPGlTransactionsReportProcessor | — | — |
| `generateSoJrExtractJob` | generateSoJrExtractJobProcessor | — | — |
| `generateTrendAndReviewDashboardJob` | generateTrendAndReviewDashboardJobProcessor | — | — |
| `generateUAMAdminActivityExtractJob` | setCommonAttributesProcessor → generateUAMAdminActivityExtractJobProcessor | — | — |
| `generateUAMLoginLogoutExtractJob` | setCommonAttributesProcessor → generateUAMLoginLogoutExtractJobProcessor | — | — |
| `generateUAMPopulationExtractJob` | setCommonAttributesProcessor → generateUAMPopulationExtractJobProcessor | — | — |
| `generateUAMRoleRightExtractJob` | setCommonAttributesProcessor → generateUAMRoleRightExtractJobProcessor | — | — |
| `generateVillageCreationTrailReportJob` | generateVillageCreationTrailReportJobProcessor | — | — |
| `getGeneratedDocumentDetails` | getGeneratedDocumentDetailsProcessor | — | — |
| `getGroupList-v2` | getGroupListProcessor | — | regExp(${function_code}_${function_sub_code})=DEFAULT_DEFAULT; regExp(${function_sub_code})=FILTER; regExp(${function_sub_code})=SEARCH |
| `getLoanAccountDerivedData` | getLoanAccountDerivedDataProcessor | — | — |
| `getLoanApplicationList-v2` | getLoanApplicationListProcessor | — | — |
| `getMonthlyDetailsForCasaAccounts` | getMonthlyDetailsForCasaAccountsProcessor | — | — |
| `getReportsNameAndCode` | getReportsNameAndCodeProcessor | — | — |
| `getStatusEnquiryForScheduledReports` | getStatusEnquiryForScheduledReportsProcessor | — | — |
| `inboundPosidexDailyExtractJob` | inboundPosidexDailyExtractJobProcessor | — | — |
| `loanAppAdditionalDetailsJob` | loanAppAdditionalDetailsJobProcessor | — | — |
| `loanAppFinancialDetails` | loanAppFinancialDetailsJobProcessor | — | — |
| `loanAppGrpStageTatJob` | loanAppGrpStageTatJobProcessor | — | — |
| `loanAppStageJob` | loanAppStageJobProcessor | — | — |
| `loanGroupTatCalculationAndSnapshotJob` | loanGroupTatJobProcessor | — | — |
| `novopayMisExtractJob` | novopayMisJobProcessor | — | — |
| `nrlmClaimAmountReportJob` | setCommonAttributesProcessor → generateNRLMClaimAmountReportJobProcessor | — | — |
| `nrlmClosedAcntMarkingReportJob` | createNrlmClosedAccountMarkingJobProcessor | — | — |
| `nrlmMasterDataReportJob` | setCommonAttributesProcessor → generateNRLMMasterDataFileJobProcessor | — | — |
| `outboundPosidexDailyExtractJob` | outboundPosidexDailyExtractJobProcessor | — | — |
| `posidexDailyReverseHandoffJob` | posidexDailyReverseHandoffJobProcessor | — | — |
| `posidexDailyWeeklyReconcilationJob` | posidexDailyWeeklyReconcilationJobProcessor | — | — |
| `regenerateKeyFactSheet` | regenerateKeyFactSheetExtractJobProcessor | — | — |
| `regenerateLoanCardFactSheet` | regenerateFactSheetExtractJobProcessor | — | — |
| `runNeftTransactionUploadJob` | runNeftTransactionUploadJobProcessor | — | — |
| `saveUploadedDocumentDetails` | saveUploadedDocumentDetailsProcessor | — | — |
| `soJrJob` | soJrJobProcessor | — | — |
| `spanRmJob` | spanRmJobProcessor | — | — |
| `spanSoJob` | spanSoJobProcessor | — | — |
| `supervisorDashboardLoanCategoryTaggingJob` | supervisorDashboardLoanCategoryTaggingJobProcessor | — | — |
| `supervisorDashboardSkippedPTPTaggingJob` | supervisorDashboardPtpSkippedTaggingJobProcessor | — | — |
| `supervisorReviewTaskJob` | supervisorReviewTaskJobProcessor | — | — |
| `unmannedPortfolioJob` | unmannedPortfolioJobProcessor | — | — |
| `villageDetailsAooJob` | villageDetailsAooJobProcessor | — | — |

**Flow description:** Requests execute validators (not expanded in table) → processors/APIs top-to-bottom; `Control` gates nest validators and processor chains. Undo processors and explicit transactions are defined in XML outside this summary — open the source XML for full fidelity.
