<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.mdc only routes here. -->

## Accounting batchnew jobs (what each one does) - verified mappings

### Interest (regular)
- `interestAccrualCalculation` (InterestAccrualCalculationBatchService / job code `LMS-IAC`)
  - What it does: calculates accrued interest periods and writes/updates `interest_accrual_details` (`InterestAccrualDetailsEntity`).
  - It does NOT call `postTransaction`.
- `interestAccrualPosting` (InterestAccrualBookingBatchService / job code `LMS-IAP`)
  - What it does: computes `bookingAmount = totalAccruedAmount - totalAccrualPostedAmount` and then calls `postTransaction` as:
    - `transaction_type = "INTEREST"`, `transaction_sub_type = "NORMAL_ACCRUAL"`
  - Eligibility (normal booking): `InterestAccrualBookingBatchService.isAccrualPostingDate(accountId, endDate)` returns `true` when:
    - `endDate` is last day of month, OR
    - `loanDueDetailsDAOService.getLoanDueDetailsForDueDate(accountId, endDate)` returns non-null.
  - Forceful mode: `InterestAccrualBookingProcessor` sets `executionContext["forceful_booking"]` (boolean) and `InterestAccrualBookingBatchService.processIndividualActiveAccount(...)` branches to forceful vs normal booking based on that flag.
  - `postTransaction` payload construction (in `InterestAccrualBookingBatchService.doInterestBooking`):
    - sets placeholder `account_details=[{placeholder:"LOAN_ACCOUNT", account_number:<accountNumber>, narration:""}]`
    - sets `client_reference_number`, `currency`, `amount=<bookingAmount>`, `value_date=<dueDate.time>`, `originating_office_id` + `office_id`
    - calls internal API `postTransaction` (v1) using template `"postTransaction"`
  - NPA branching:
    - if `npaStagingDate`/`secNpaTaggingDate` is present and `stagingDate.compareTo(dueDate) < 0`, it updates the first interest txn `transaction_sub_type` to `"NPA_ACCRUAL"`.
    - when `stagingDate != null && stagingDate.compareTo(dueDate) < 0`, it also calls `postNPABooking(...)` which posts an extra interest txn for the interest due amount (from `loanDueDetailsDAOService.getDueDetailsForDueDateAndComponentType(accountId, dueDate, AssetsConstants.INTEREST)`) with `transaction_sub_type = "NPA_ACCRUAL_BOOKING"`.

### Interest (penal)
- `penalInterestAccrualCalculation` (PenalInterestAccrualCalculationBatchService / job code `LMS-PIAC`)
  - What it does: calculates penal accrual and persists `penal_interest_accrual_details` (`PenalInterestAccrualDetailsEntity`).
  - It also updates installment/flag records needed by booking.
  - It does NOT call `postTransaction`.
- `penalInterestAccrualBooking` (PenalInterestAccrualBookingBatchService / job code `LMS-PIAB`)
  - What it does (booking stage): it does NOT call `postTransaction`; for eligible accrual rows (or when forceful booking is enabled) it creates `loan_due_details` rows with:
    - `component_type = "PINT"`, `paid_amount = 0`, `waived_amount = 0`
    - `chargeCode` and either `chargeRate` (when penalRate != null) or `chargeFixedAmount` (when penalRate is null)
    - `baseAmount`, `dueAmount`, `dueDate`, `overdueDate`, and `loanInstallmentDetailsId`
  - Eligibility and forceful control:
    - `PenalInterestAccrualBookingProcessor` reads `forceful_booking` and sets `forceful_booking_posting` (boolean) and adjusts the selected loan/account status list for booking.
    - `PenalInterestAccrualBookingBatchService` creates due rows when `isPostingEligibleForEndDate(...) || forceFulBooking` is true.
  - Persistence + child handling:
    - `PenalInterestAccrualBookingItemWriter` persists `loan_due_details` via `loanDueDetailsDAOService.saveOne(...)` and updates `penal_interest_accrual_details` via `penalInterestAccrualDetailsDaoService.savePenalInterestAccrualDetails(...)`.
    - if the accrual is marked `hasChildAccounts`, it calls `ChildLoanPenalInterestBookingService.bookChildLoans(...)` for the created penal `LoanDueDetailsEntity`.

### Billing (dues generation)
- `loanAccountBilling` (LoanAccountBillingBatchService / partitions ACTIVE loans)
  - What it does:
    - partitions ACTIVE loans (`WHERE la.loan_status = 'ACTIVE'`)
    - creates `loan_account_billing_details` (`LoanAccountBillingDetailsEntity`) only if a billing detail does not already exist for `loan_installment_details_id` (checked via `loanAccountBillingDetailsDaoService.findByLoanInstallmentDetailsId(...)`)
    - posts GL/ledger via `billing_postTransaction` as:
      - `transaction_type = "BILLING"`, `transaction_sub_type = "NORMAL_BILLING"`
  - `postTransaction` payload construction (in `LoanAccountBillingBatchService.processLoanAccountBilling(...)`):
    - sets placeholder `account_details=[{placeholder:"LOAN_ACCOUNT", account_number:<accountNumber>, narration:""}]`
    - sets `principal_amount` + `interest_amount` both as execution locals and as `additional_amount_details` entries (`reference_code="principal_amount"` / `"interest_amount"`)
    - sets `amount=principal+interest`, `principal_amount`, `interest_amount`, `value_date`, `currency`, `originating_office_id`
    - calls internal API `postTransaction` with template `"billing_postTransaction"` and returns `transaction_reference_number` from `exec.getAPIResponse("billing_postTransaction")`.

### NPA: delinquency + asset movement
- `loanAccountDpdCalc` (LoanAccountDpdCalcBatchProcessor)
  - What it does: updates delinquency markers on `loan_account` (e.g., `past_due_days`, `delinq_string`).
  - No direct GL posting in this processor.
- `loanAccountAssetCriteria` (LoanAccountAssetCriteriaProcessor)
  - What it does:
    - decides forward vs reverse NPA movement based on slab group + tagging eligibility
    - updates `loan_account` NPA fields (e.g., `asset_criteria_slabs_id`, `npa_ageing_start_date`, `npa_tagging_date`, `sec_npa_tagging_date`, `interest_suspense_amount`)
  - GL/ledger impact:
    - Forward path:
      - triggers NPA accrual recalculation + posting by calling:
        - `interestAccrualCalculation` then `interestAccrualPosting`
      - then calls `postTransaction` for the movement using execution-context driven values:
        - `transaction_type = forward_movement_transaction_type`
        - `transaction_sub_type = forward_movement_transaction_sub_type`
      - amount details come from interest suspense + AIR components in `additional_amount_details` (reference codes from exec keys).
    - Reverse path:
      - calls `postTransaction` using:
        - `transaction_type = reverse_movement_transaction_type`
        - `transaction_sub_type = reverse_movement_transaction_sub_type`
      - amount details are built from interest suspense + AIR for reversal.

### Auto-closure
- `LoanAccountAutoClosureBatchProcessor` / LoanAccountClosureService
  - What it does:
    - verifies interest accrual + booking are up to date before closure
    - settles unpaid components (including waiver handling)
    - triggers closure-related forward/reverse NPA movement legs
    - sets `loan_account.loan_status = CLOSED` and updates closure/status fields

### Death foreclosure insurance (batch entrypoints)
- `OutboundDeathForeclosureInsuranceJobProcessor`
  - What it does: selects `PENDING` rows in `death_foreclosure_insurance_staging_details` and creates outbound insurer CSV.
  - This processor does not directly call `postTransaction`; it delegates to bulk/outbound mechanisms.
- `InboundDeathForeclosureInsuranceJobProcessor`
  - What it does: runs inbound file upload processing using the staged/original filename and routes rows to inbound processing logic.

### Proactive excess refund
- Proactive Excess Amount Refund job (ProactiveExcessRefundService + ProactiveExcessAmountRefundItemWriter)
  - What it does:
    - calculates `total_refund_amount` using:
      - `loan_account.excess_amount` minus outstanding due computed as `due_amount - paid_amount - waived_amount` across `loan_due_details`
    - posts GL via `accounting_postTransaction` as:
      - `transaction_type = "EXCESS_AMT_REFUND"`
      - `transaction_sub_type = "LOAN_ACCOUNT"`
    - updates `loan_account.excess_amount` and records success/failure in excess-refund staging tables.

### Derived fields (reporting inputs, not GL posting)
- **API / Spring job name** `updateLoanAccountDerivedFieldsJob` (`mfi_orc.xml` → `loanAccountDerivedFieldsJobProcessor`; `LADerivedFieldsBatchConfigService.JOB_NAME`)
  - What it does: selects accounts from `account` + `loan_account` and filters using `loan_account_derived_fields` where `is_calculated_for_closed = false OR IS NULL`.
  - It then runs `ParallelCommonBatchJob.runJob(...)` for the partitions.
- **API / Spring job name** `updateLoanAccountDerivedFieldsMonthlyJob` (`mfi_orc.xml` → `loanAccountDerivedFieldsMonthlyJobProcessor`; `LADerivedFieldsMonthlyBatchConfigService.JOB_NAME`)
  - What it does: runs only when `job_time` is the `firstDayOfMonth`, then checks `LADerivedFieldsRunHistoryService.findByMonthAndYear(...)` for previous month run history and `isDerivedFieldsMonthlyJobRun`.
  - It then runs `ParallelCommonBatchJob.runJob(...)` for partitions.
- `LADerivedFieldsIProcessor` and `LADerivedFieldsMonthlyIProcessor` (computation)
  - What it does (in code): computes derived values for `LoanAccountDerivedField*` by reading `loan_due_details` and using `due.getDueAmount() - due.getPaidAmount() - due.getWaivedAmount()` (see `calculateOutstandingAmount(...)` in `LADerivedFieldsIProcessor`).
  - It also builds GL-balance maps from `transaction_partition_details` by summing amounts based on `crDrIndicator`.
  - In these processors, no `postTransaction` call exists.

### Installment notifications jobs
- `LoanInstallmentDueNotificationJobProcessor`
  - What it does (in code): reads `loan.installment.due.notification.days`, builds a partition query for ACTIVE loans where `loan_installment_details.installment_date` equals `businessDate - notificationDay`, and runs `parallelCommonBatchJob.runJob(...)` with `upload_type = "LOAN_INSTALLMENT_DUE_NOTIFICATION"`.
- `LoanInstallmentBounceNotificationJobProcessor`
  - What it does (in code): reads `loan.installment.bounce.notification.days`, builds a partition query joining `presentation_bounce_charge_details` where `pbcd.mandate_missed_on_date = lid.installment_date` and `pbcd.is_settled = false`, and runs `parallelCommonBatchJob.runJob(...)`.

### Refund jobs (orchestration entrypoints)
- `ProactiveExcessAmountRefundJobProcessor`
  - What it does (in code): gets staging counts via `loanAccountDAOService.getStagingRefundRecords()`, partitions, and runs the job for the selected staging records (grid sizing comes from `LoanAccountAutoClosureBatchConfigService.GRID_SIZE`).
- `ProactiveReverseTransactionJobProcessor`
  - What it does (in code): gets `file_upload_id` from execution context, counts failed records via `ProactiveRefundFileStagingRepository.getAllFailedRecord()`, partitions, and runs `parallelCommonBatchJob.runJob(...)`.
- `RunInboundReverseExcessAmountRefundJobProcessor`
  - What it does (in code): sets `upload_type = "REVERSE_EXCESS_AMOUNT_REFUND"` and calls `ParallelBatchJobV2.runJob(jobName, operationType, overrideParams)`.
- `InboundReverseExcessAmountRefundJobProcessor`
  - What it does (in code): calls `ParallelBatchJobV2.runInboundFileUploadJob(...)` with `file_name` from `file_original_name` and `upload_type = "REVERSE_EXCESS_AMOUNT_REFUND"`, plus override params for `loan_account_number_flag`.

### eNACH jobs (representation + presentation)
- `BulkFileToSGEnachRepresentationJobProcessor`
  - What it does (in code): prepares a temp directory via `BulkUploadTempDirService.prepareJobDirectory(uploadType, fileUploadId)` and runs `parallelJob.runBulkFileUploadJob(...)`.
- `BulkSGToEnachRepresentationJobProcessor`
  - What it does (in code): counts file staging via `FileStagingEnachRepresentationDAOService.getCountOfFileStaging(fileUploadId)`, sets `business_date_long` and `employee_formatted_id`, then runs `parallelJob.runJob(...)`.
- `OutboundEnachRepresentationBatchProcessor` / `InboundEnachRepresentationBatchProcessor`
  - What it does (in code): both run `ParallelBatchJob.runJob(...)` with `job_time` and `op_code`.
- `OutboundEnachPresentationBatchProcessor` / `InboundEnachPresentationBatchProcessor`
  - What it does (in code): both run `ParallelBatchJob.runJob(...)` with `job_time` (inbound also adds batch execution context).

### Standing Instruction (SI) jobs
- ORC request → batch job/process mapping (service orchestration XML):
  - `generateSIPresentationFiles` → `outboundSIPresentationBatchProcessor` → `OutboundSIPresentationBatchProcessor`
  - `processingSIReverseFeedFiles` → `inboundSIPresentationBatchProcessor` → `InboundSIPresentationBatchProcessor`
  - `generateSIManualPresentationFiles` → `outboundSIManualPresentationBatchProcessor` → `OutboundSIManualPresentationBatchProcessor`
  - `processingSIManualPresentationReverseFeedFiles` → `inboundSIManualPresentationBatchProcessor` → `InboundSIManualPresentationBatchProcessor`
  - `generateSIAutoHoldRemovalPresentationFiles` → `outboundSIAutoHoldRemovalBatchProcessor` (outbound hold-unhold file)
  - `processingSIAutoHoldRemovalReverseFeedFiles` → `inboundSIAutoHoldRemovalBatchProcessor` (consume reverse feed)
  - `generateSIManualHoldMarkingPresentationFiles` / `processingSIManualHoldMarkingReverseFeedFiles` → manual hold marking batch processors
  - `generateSIManualHoldRemovalPresentationFiles` / `processingSIManualHoldRemovalReverseFeedFiles` → manual hold removal batch processors
  - `retrySIJob` → `RetrySIJobProcessor`
  - `updateSIPresentationDetails` → `checkDataForUpdateSIPresentationStatusProcessor` + `updateSIPresentationStatusProcessor` (synchronous status update)
  - `fetchFailedSIPresentationList` → `updateFailedSIPresentationListProcessor` + `fetchFailedSIPresentationListProcessor`
  
- SI synchronous orchestration walkthrough (mandate + presentation status; service orchestration XML):
  - `createRepaymentMandateDetails` (DEFAULT create)
    - validators:
      - `casa_account_number`, `mandate_category`, `loan_category`, `start_date`, `end_date` are mandatory
      - master-data validations for `repayment_frequency`, `mandate_type`, `mandate_category`, `mandate_status`
    - processors/APIs:
      - `accounting_getUseCaseDetails` (usecase `MANDATE-DTLS-UC001`) → `getUseCaseDetailsPostProcessor`
      - `validateMandateDetailsForCreateProcessor` → `createMandateDetailsProcessor`
      - notification message fetch (`getNotificationMessageByNotificationCode`, user_story_code `MANDATE-DTLS`) → `setUserStoryForResponseProcessor`
  - `fetchMandateDetails` (DEFAULT vs GROUP via `function_sub_code`)
    - DEFAULT: requires `loan_account_number` → `fetchMandateDetailsProcessor`
    - GROUP: requires `group_id` → `fetchMandateDetailsForGroupProcessor`
    - then populates bulk unique master-data extensions (`fetchBulkUniqueMasterDataExt`, reason `UPDT_MNDT`) and returns mandate details with notification payload (`MANDATE-DTLS`)
  - `fetchMandateDetailsHistory`
    - supports `function_sub_code` in `DEFAULT|GROUP|BY_LOAN_APPLICATION_NO`
    - routes to:
      - `fetchMandateDetailsHistoryProcessor` (DEFAULT, BY_LOAN_APPLICATION_NO)
      - `fetchMandateDetailsHistoryForGroupProcessor` (GROUP)
    - returns history with notification payload (`MANDATE-DTLS`)
  - `updateMandateDetailsTask` (maker-checker task lifecycle; `function_code` controls branch)
    - entry: `populateUserDetails`
    - `DIRDR` repayment_mode:
      - validates/normalizes document metadata (`validateDocumentDataForGenericDocumentProcessor`) and sets common attributes (`setCommonAttributesProcessor`)
    - core:
      - `validateMandateDetailsForUpdateProcessor`
      - `fetchBulkUniqueMasterDataExt` (reason `UPDT_MNDT`)
      - `constructRequestForApprovalUsingApprovalTemplate`
      - `constructRequestForTaskCreationProcessor` (task_type_code `UPDT_MANDATE_DTLS`)
    - maker path (`function_code=DEFAULT`, and when task creation is enabled by flow config):
      - creates document rows when `repayment_mode=DIRDR` (`createDocumentProcessor` + `createMandateDocumentDetailsProcessor`)
      - creates/updates approval task via `createOrUpdateTask` and sets task status to `PENDING` via `updateMandateDetailsTaskProcessor`
    - checker approval (`function_code=APPROVE`):
      - `fetchTaskIdForMandateDetailsIdProcessor` → `updateMandateDetailsTaskProcessor(status=APPROVED)`
      - persists approved mandate updates via `updateMandateDetailsProcessor` (DEFAULT) or `updateMandateDetailsForGroupProcessor` (GROUP)
      - deletes the task (`deleteTask`)
    - checker rejection (`function_code=REJECT`):
      - `fetchTaskIdForMandateDetailsIdProcessor` → `updateMandateDetailsTaskProcessor(status=REJECTED)`
  - `updateSIPresentationDetails` (presentation status update; synchronous)
    - `checkDataForUpdateSIPresentationStatusProcessor` → `updateSIPresentationStatusProcessor`
    - response wrapped with notification payload (`PRSN-DTLS`)
  - `fetchFailedSIPresentationList` (failed SI presentation remediation; synchronous)
    - `updateFailedSIPresentationListProcessor` → `fetchFailedSIPresentationListProcessor`
    - response wrapped with notification payload (`PRSN-DTLS`)
  - `updateMandateStatus` (simple orchestration wrapper)
    - `updateMandateStatusProcessor`
- `InboundSIPresentationBatchProcessor` (SI Presentation reverse feed)
  - What it does (in code): fetches `SIPresentationFileDetailsEntity` via `findAllUnconsumedFilesWithManualRepresentationFlag(false)`, calculates min/max `valueDate` from those files, partitions using DAO `countMinMaxIdsForSIReverseFeedJob(minDate, maxDate)`, populates office/external branch codes, and fetches reject-reason mappings via `getDatatypeMaster(datatype="RJCT_CODE_SI")`.
- `OutboundSIPresentationBatchProcessor`
  - What it does (in code): runs `ParallelBatchJob.runJob(...)` using `op_code` and `job_time`.
  - Batch writes (tasklets, code-verified):
    - `PopulateSIPresentationStepTasklet`
      - reads unsettled installment rows for `installment_date=valueDate` (`loanInstallmentDetailsDAOService.findUnsettledAmountsForInstallmentDate(valueDate)`)
      - fetches active SI mandates per loan account at `valueDate`
      - builds/updates:
        - `SIPresentationDetailsEntity` (status `INITIATED`, narration + mandate_reference_number)
        - `SIPresentationLoanAccountDetailsEntity` (valueDate, loanAccountId, repaymentMandateDetailsId, amount, status `INITIATED`)
      - parent/group handling:
        - parent mandates: creates child rows + sets `hasChildAccounts=true` on parent SIPresentationLoanAccountDetailsEntity
        - group mandates: aggregates amounts into a shared SIPresentationDetailsEntity per groupId
    - `CreateSIPresentationFileTasklet`
      - generates outbound text file(s) for the presentationDate and writes `SIPresentationDetailsEntity.presentationFileName`
      - splits into multiple files based on `si.max.records.in.file`
      - writes `SIPresentationFileDetailsEntity` with `manualPresentation=false`, `presentationFileName`, `totalRecords`, plus `presentationDate` + computed `valueDate`
- `OutboundSIManualPresentationBatchProcessor` / `InboundSIManualPresentationBatchProcessor`
  - What it does (in code): outbound runs `ParallelBatchJob.runJob(...)`; inbound also adds batch execution context before running.
  - Manual presentation outbound + reverse feed (tasklets, code-verified):
    - `CreateSIManualPresentationFileTasklet`
      - reads `SIManualPresentationDetailsEntity` non-presented rows
      - writes outbound text file (same delimiter/footer scheme as SI presentation)
      - updates `SIManualPresentationDetailsEntity.status="P"` and `presentationFileName`
      - creates/updates `SIPresentationFileDetailsEntity` with `manualPresentation=true`, `presentationFileName`, `totalRecords`, `presentationDate`
    - `ConsumeSIManualPresentationFileTasklet` (reverse feed)
      - reads unconsumed `SIPresentationFileDetailsEntity` for `manualPresentation=true`
      - parses reverse feed file rejected lines into `rejectedMandateReferenceNos` (reference_no → reject_reason_code)
      - for rejected records:
        - sets `SIManualPresentationDetailsEntity.status="F"` + rejectReason/rejectReasonCode + audit fields
      - for success records:
        - updates holds on `RepaymentAccountDetails` (holdAmount accumulation + save)
        - calls internal API `loanRepayment` with:
          - `repayment_amount = siManualPresentationDetailsEntity.amount`
          - `value_date = reverseFeedDate`
          - `repayment_mode="DIRDR"` and `function_sub_code="DEFAULT"`
          - for parent accounts: sets `child_loans` JSON payload and adjusts `client_reference_number`
        - marks `SIManualPresentationDetailsEntity.status="S"` and `internalApiStatus` accordingly
- `OutboundFinnoneSILienPresentationBatchProcessor`
  - What it does (in code): runs `ParallelBatchJob.runJob(...)` with `job_time`.
- `RetrySIJobProcessor`
  - What it does (in code): runs `ParallelBatchJob.runJob(...)` with `job_time`.
- `SIFileDownloadBatchJobProcessor`
  - What it does (in code): runs `ParallelBatchJob.runJob(...)` with `job_time`.
- SI Hold removal entrypoints (processors)
  - `OutboundSIManualHoldMarkingBatchProcessor`, `InboundSIAutoHoldRemovalBatchProcessor`, `OutboundSIManualHoldRemovalBatchProcessor`, `OutboundSIAutoHoldRemovalBatchProcessor`, `InboundSIManualHoldRemovalBatchProcessor`
  - What they do (in code): all run `ParallelBatchJob.runJob(...)` with `job_time` and validate non-empty `op_code`.
  - Auto hold removal tasklets (code-verified):
    - Outbound: `CreateSIAutoHoldRemovalFileTasklet`
      - fetches eligible files via `SIPresentationFileDetailsDAOService.findEligibleFilesForHoldPresentation()`
      - writes hold-unhold outbound file using failed `SIPresentationDetailsEntity` records
      - updates `SIPresentationFileDetailsEntity.holdPresentationDate`
      - creates `SIAutoHoldPresentationFileDetailsEntity` (presentationDate + totalRecords + presentationFileName)
    - Inbound: `ConsumeSIAutoHoldRemovalFileTasklet`
      - reads unconsumed `SIAutoHoldPresentationFileDetailsEntity`
      - if reverse feed exists, filters rejected mandate refs out of failed SIPresentationDetails and then:
        - subtracts holdAmount from `RepaymentAccountDetails` (holdAmount decremented and holdStatus set when it becomes <= 0)
      - updates hold presentation file details with reverse feed metadata + success/failure counts

### NPA secondary feed/status jobs
- **API / Spring job name** `runSecNpaBulkUploadJob` (`RunSecNpaJobBatchConfigService.JOB_NAME`) — processor `RunSecNpaBulkJobProcessor`
  - What it does (in code): validates non-empty `op_code`, sets `minId=1` and `maxId=1`, then runs `ParallelBatchJobV2.runJob(...)`.
- `BulkSGToSecNpaReverseFeedFileJobProcessor`
  - What it does (in code): sets `job_time` from `platformDateUtil.getBusinessDateInLong()`, counts file staging via `FileStagingSecNpaRevFeedFileDaoService.getCountOfFileStaging(fileUploadId)`, partitions, sets bulk end event via `BulkBatchUtil.setBulkUploadEndEvent(...)`, then runs `parallelJob.runJob(...)`.
- `BulkFileToSGSecNpaReverseFeedFileJobProcessor`
  - What it does (in code): prepares temp dir via `BulkUploadTempDirService.prepareJobDirectory(uploadType, fileUploadId)` and runs `parallelJob.runBulkFileUploadJob(...)`, including end-of-line tags (`end_of_line_key="MIS_DATE"`, `end_of_line_value="TRL"`) and `is_outbound_job_tagged=true`.
- **API / Spring job name** `bulkOutboundSecNpaReverseFeedFileJob` (`OutboundSecNpaStatusFileBatchConfigService.JOB_NAME`) — processor `OutboundSecNpaStatusFileJobProcessor`
  - What it does (in code): fetches `now` using `fileStagingSecNpaRevFeedFileDaoService.getMisDate(fileUploadId)`, and when not null sets `upload_type="SEC_NPA_NP_STATUS_FILE"` + `file_original_name="NOVOPAY_NPA_<ddMMyyyy>_STATUS.txt"`, sets min/max/batch_record_count, then calls `parallelJob.runBulkOutboundJob(...)`.

### SI GEFU file jobs (transfer + enquiry)
- `SIFileTransferBatchJobProcessor`
  - What it does (in code): validates non-empty `op_code`, sets `job_time`, adds batch execution context, then runs `ParallelBatchJob.runJob(...)`.
- `SIFileEnquiryBatchJobProcessor`
  - What it does (in code): validates non-empty `op_code`, sets `job_time`, adds batch execution context, then runs `ParallelBatchJob.runJob(...)`.

### Bulk file jobs (FileToSG / SGTo… processors)
- NOC
  - **API / Spring job name** `generateNocFileJob` (`GenerateNocFileBatchConfigService.JOB_NAME`)
  - `GenerateNocFileJobProcessor`
    - What it does (in code): sets `upload_type="GENERATE_NOC_FILE"`, counts via `loanAccountNocDetailsDAOService.getNocGenerationRecordCount()`, loads `MasterOutboundConfig` for delimiter/readSource/folder and then runs `parallelCommonBatchJob.runJob(...)`.
  - `BulkSGToDispatchDetailsJobProcessor`
    - What it does (in code): counts via `FileStagingDispatchDetailsDAOService.getCountOfFileStaging(fileUploadId)`, sets bulk end event, then runs `ParallelBatchJob.runJob(...)`.
  - `BulkFileToSGDispatchDetailsJobProcessor`
    - What it does (in code): validates `file_upload_id`/`op_code`, prepares temp dir via `BulkUploadTempDirService.prepareJobDirectory(upload_type, fileUploadId)`, populates audit fields (`office_id`, `employee_id`, `employee_name`, `employee_adid`), then calls `parallelJob.runBulkFileUploadJob(...)`.
  - `BulkSGToNocBlockUnblockJobProcessor`
    - What it does (in code): counts via `FileStagingNocBlockUnblockDAOService.getCountOfFileStaging(fileUploadId)`, sets bulk end event, then runs `ParallelBatchJob.runJob(...)`.
  - `BulkFileToSGNocBlockUnblockJobProcessor`
    - What it does (in code): validates `file_upload_id`/`op_code`, prepares temp dir via `BulkUploadTempDirService.prepareJobDirectory(upload_type, fileUploadId)`, populates audit fields, then calls `parallelJob.runBulkFileUploadJob(...)`.

- Manual hold (SI) bulk file processors
  - `BulkSGToManualHoldMarkingJobProcessor`
    - What it does (in code): counts staging rows via `FileStagingManualHoldMarkingDAOService.getCountOfFileStaging(fileUploadId)`, partitions, sets `function_sub_code="DEFAULT"` and override params including `business_date_long` and `employee_formatted_id`, then runs `parallelJob.runJob(...)`.
  - `BulkFileToSGManualHoldMarkingJobProcessor`
    - What it does (in code): validates `file_upload_id`/`op_code`, prepares temp dir via `BulkUploadTempDirService.prepareJobDirectory(upload_type, fileUploadId)`, sets `function_sub_code="DEFAULT"` + audit fields, then calls `parallelJob.runBulkFileUploadJob(...)`.
  - `BulkSGToManualHoldRemovalJobProcessor`
    - What it does (in code): counts staging rows via `FileStagingManualHoldRemovalDAOService.getCountOfFileStaging(fileUploadId)`, partitions, sets `function_sub_code="DEFAULT"` and override params including `business_date_long` and `employee_formatted_id`, then runs `parallelJob.runJob(...)`.
  - `BulkFileToSGManualHoldRemovalJobProcessor`
    - What it does (in code): validates `file_upload_id`/`op_code`, prepares temp dir via `BulkUploadTempDirService.prepareJobDirectory(upload_type, fileUploadId)`, sets `function_sub_code="DEFAULT"` + audit fields, then calls `parallelJob.runBulkFileUploadJob(...)`.
- Transaction reversal
  - `BulkSGToTransactionReversalJobProcessor`
    - What it does (in code): counts via `FileStagingTransactionReversalDAOService.getCountOfFileStaging(fileUploadId)`, injects `max_days_for_transaction_reversal`, sets batch context and runs `parallelJob.runJob(...)`.
  - `BulkFileToSGTransactionReversalJobProcessor`
    - What it does (in code): prepares temp dir using `BulkUploadTempDirService` and runs `parallelJob.runBulkFileUploadJob(...)`.
- Manual journal entries
  - **API / Spring job names** `bulkFileToSGManualJournalEntriesJob` and `bulkSGToManualJournalEntriesJob` (`FileToSGManualJournalEntriesBatchConfigService` / `SGToManualJournalEntriesBatchConfigService`)
  - `BulkFileToSGManualJournalEntriesJobProcessor`
    - What it does (in code): prepares temp dir and runs `parallelJob.runBulkFileUploadJob(...)`.
  - `BulkSGToManualJournalEntriesJobProcessor`
    - What it does (in code): counts from `file_staging_manual_journal_entries` (status not in `FAILED`), partitions, sets bulk end event, and runs `parallelJob.runJob(...)`.
    - Posting behavior (code-verified):
      - `SGToManualJournalEntriesIWriter` groups staging rows by journal (generates a single `manual_je_number` via internal job api `generateUniqueReferenceNumber`)
      - builds `manual_journal_entry_gl_details` JSON with `debit_gl_code` / `credit_gl_code` / `amount`
      - calls internal API `postManualJournalEntry` (v1) for each successful journal with:
        - `function_code=BULK`, `function_sub_code=TRANSACTION`
        - `manual_journal_entry_on=INTRA_BRNH`
        - `account_number=<loanAccountNumber from staging>`
        - `value_date=<business_date_long from batch params>`, `currency="INR"`, `remarks=<staging remarks>`
      - failed items are written back into file staging via `FileStagingManualJournalEntriesService.addFileStagingDetails(...)` and marked `status="FAILED"` with `reason`
- Asset criteria group update
  - `BulkSGToAssetCriteriaGroupUpdateJobProcessor` and `BulkFileToSGAssetCriteriaGroupUpdateJobProcessor`
    - What they do (in code): both count/partition file staging using the dedicated service + run `ParallelBatchJobV2` paths.
- Pre-foreclosure charge update
  - `BulkFileToSGForeclosureChargeUpdateJobProcessor`
    - What it does (in code): prepares temp dir and runs `runBulkFileUploadJob(...)`.
  - `BulkSGToForeclosureChargeUpdateJobProcessor`
    - What it does (in code): counts file staging and runs `parallelJob.runJob(...)`.
- Bulk repayment (Finsall)
  - **API / Spring job names** `bulkSGToFinsallRepaymentJob` and `bulkFileToSGFinsallRepaymentJob` (`SGToFinsallRepaymentBatchConfigService` / `FileToSGFinsallRepaymentBatchConfigService`)
  - `BulkSGToFinsallRepaymentJobProcessor` and `BulkFileToSGFinsallRepaymentJobProcessor`
    - What they do (in code): both partition on `file_upload_id` using their `FileStagingFinsallRepaymentDAOService` counts and run the appropriate `ParallelBatchJobV2` path (file upload vs SG->processing).

### Loan account servicing document events
- `LoanAccountServicingDocumentEventsJobProcessor`
  - What it does (in code): counts `PENDING` rows via `LoanAccountServicingDocumentEventsDAOService.getCountMinMaxForPendingStatus()`, then runs partitions via `ParallelCommonBatchJob.runJob(...)`.
- `LoanAccountServicingDocumentEventsItemProcessor`
  - What it does (in code):
    - retries up to `MAX_RETRIES=3`, then marks row `FAILED`
    - parses `documentFieldsJson` and calls `reportUtil.generateReportAndRetrieveDocumentId(...)`
    - creates `DocumentEntity` and `DocumentFileEntity`, and calls `LoanAccountServicingDocumentEventsI.updateDocumentId(...)` for each document event service
    - sets `status` to `SUCCESS`, or on exception updates `retryCount` + `status` back to `PENDING`/`FAILED` with `errorMessage`.

### Child loan event processing
- **API / Spring job name** `childLoanEventProcessingBatchJob` (`group_mfi_orc.xml`; `ProcessChildLoanEventsBatchConfigService.JOB_NAME`)
- `ChildLoanEventProcessingJobProcessor`
  - What it does (in code): selects ids from `loan_account_events_queue` where `event_status='P' AND is_deleted=false`, partitions, and runs `ParallelCommonBatchJob.runJob(...)`.
- `ChildLoanEventProcessingItemProcessor`
  - What it does (in code):
    - ignores some event types using `EVENT_TYPE_IGNORE_API_MAP`
    - `@BeforeStep`: builds `BatchExecutionContextHolder` key as `jobParameters['tenantCode'] + "-" + JOB_NAME`
    - parses queue `data` as JSON array
    - for each event, builds an ORC request using `OrchestrationXMLParser.getRequestFromOrcXML(...)` and executes the mapped processors via `ServiceOrchestrator.executeProcessors(...)`
    - sets queue `eventStatus` to `C` (completed) or records exception message in `filler1`
    - **CLB and CLMT (success path)**: saves the queue row, then `ParentGroupDisbursementStatusSyncService.syncParentAfterChildQueueProgress(parentAccountId)` so the parent loan’s `disbursement_status` matches CLMT/CLB queue state (closes the gap where all CLMT were already `C` but parent stayed `PARENT_SUCCESS` / `CHILD_SUCCESS` until CLB ran or a manual replay).
- `ParentGroupDisbursementStatusSyncService`
  - What it does (in code): if the parent has CLMT rows and all are `C`, and parent `disbursement_status` is `PARENT_SUCCESS` or `CHILD_SUCCESS`, sets parent to `CHILD_SUCCESS` when any CLB is still `P`, else `COMPLETED`. No-op otherwise. Also invoked from `PerformChildLoanBankDisbursementProcessor` after child bank calls (same rules as before; logic centralized here).

### Accounting bank service retry
- **API / Spring job name** `accountingBankServiceRetryJob` (`mfi_orc.xml`; `AccountingBankServiceRetryJobBatchConfigService.JOB_NAME`)
- `AccountingBankServiceRetryJobProcessor`
  - What it does (in code): selects failed client request/response logs with `retry=true` via `ClientRequestResponseLogDAOService.findAllFailedReuestAndRetryTrue()`, partitions, and runs `ParallelCommonBatchJob.runJob(...)`.

### Loan recurring payment batch API
- **API / Spring job name** `loanRecurringPaymentBatchApi` (`loans_orc.xml`; `LoanRecurringPaymentBatchConfigService.JOB_NAME`)
- `LoanRecurringPaymentItemProcessor`
  - What it does (in code): returns the input objects as pass-through (`return objects`), with comment that heavy processing is in the writer using bulk DB calls and pre-fetched data.

### Loan advance repayment (batch entrypoints)
- `LoanAdvanceRepaymentBatchProcessor`
  - What it does (in code): delegates to `LoanAdvanceRepaymentBatchService.process(executionContext)`.
- `LoanAdvanceRepaymentBatchService`
  - What it does (in code): reads `job_time` (optional) to set the business timestamp, gets batch partitions via `loanAccountDAOService.batchGetCountLoanAccountsCountForAdvanceRepayment(now)`, then sets `function_sub_code="DEFAULT"` and runs `ParallelCommonBatchJob.runJob(...)`.
  - The per-account processing (in `LoanAdvanceRepaymentService`) calls internal API `loanRepayment` using an `apiIdentifier` of `advance_repayment_<accountNumber>`, and on success it may trigger `reverseTransactionProcessor.execute(exec)` during failure paths when a reversal transaction reference is available.

### Standing instruction mandate expiry
- `ExpirePendingMandatesBatchProcessor`
  - What it does (in code):
    - requires non-empty `op_code` and non-blank `job_time`
    - computes `dueDateForMandateExpiry = businessDate + configured.days.for.pending.mandates.expiry`
    - selects `loan_account_ids` via `loanInstallmentDetailsDAOService.findLoanAccountIdsInstallmentDate(dueDateForMandateExpiry)`
    - counts pending registrations via `mandateDetailsDAOService.findCountsForRegistrationPendingMandates()`
    - partitions and runs `parallelJob.runJob(...)` with grid sizing from `SGToRefundMarkingBatchConfigService.GRID_SIZE`.

### CASA balance extraction (external cash for PC180/PC182)
- `ExtractCasaBalanceFor182ProductCodeBatchProcessor`
  - What it does (in code): validates non-empty `op_code`, sets `accts_under_pc_182_file_path` from config key `accts.under.pc.one.eight.two.file.path`, preloads `existing_repayment_accounts` and `existing_pc182_accounts`, then runs `parallelJob.runJob(...)`.
- `ExtractCasaBalanceFor180ProductCodeBatchProcessor`
  - What it does (in code): validates non-empty `op_code`, sets `accts_under_pc_180_file_path` from config key `accts.under.pc.one.eight.zero.file.path`, preloads `existing_repayment_accounts` and `existing_pc180_accounts`, then runs `parallelJob.runJob(...)`.

### Death foreclosure — billing sync cutoff & eligibility
- Death-foreclosure flows sync billing by invoking internal API `loanAccountBillingJob` with `job_time` and `account_number_list` before computing outstanding/waivers/closure posting.
- **Cutoff alignment (as of 2026-04-07)**: death-foreclosure billing sync uses **date of reporting** (`createdOn`) as `job_time` (fallback: `dateOfDeath` if reporting date is absent).
- **Eligibility alignment (as of 2026-04-07)**: when the billing job is invoked from death-foreclosure flows it is marked with `billing_sync_mode = DEATH_FORECLOSURE`, and the billing job includes loan accounts in statuses **`ACTIVE`** and **`DEATH_FORECLOSURE_FREEZE`** for the provided `account_number_list`. Bulk billing remains `ACTIVE` only.

### Bulk refund marking (view/download processing)
- `BulkSGToRefundMarkingJobProcessor`
  - What it does (in code): counts file staging rows via `FileStagingRefundMarkingDAOService.getCountOfFileStaging(fileUploadId)`, sets bulk end event via `BulkBatchUtil.setBulkUploadEndEvent(...)`, then runs `parallelJob.runJob(...)`.
- `BulkFileToSGRefundMarkingJobProcessor`
  - What it does (in code): prepares a temp directory via `BulkUploadTempDirService.prepareJobDirectory(uploadType, fileUploadId)` and runs `parallelJob.runBulkFileUploadJob(...)` after populating audit fields (`office_id`, `employee_id`, `employee_name`, `employee_adid`).

### Trial balance & zeroisation (tasklets)
- `PopulateTrialBalanceBatchTasklet`
  - What it does (in code): reads `calculation_start_date`, `tb_reporting_date`, `first_day_fy`, and `OFFICE_IDS_EXTERNAL_BRANCH_CODES`; builds/refreshes a `lastReportedDateMap` of GL+office balances; then for each business date it paginates `TransactionDetailsEntity` via `TransactionDetailsDAOService` and aggregates into `TrialBalanceEntity` (saved via `trialBalanceDAOService.saveAll(...)`).
- `GenerateGLReportBatchTasklet`
  - What it does (in code): for `reporting_date` builds `glReportName_<TB_REPORTING_DATE_FORMAT>`; fetches GL-level TB data via `trialBalanceDAOService.getGlLevelDataForDate(...)`; writes Excel via `GLReportWriter` and a text export via `TextFileWriter`.
- `GenerateOracleReportBatchTasklet`
  - What it does (in code): builds `oracleReportName_<TB_REPORTING_DATE_FORMAT>`; fetches Oracle-level TB data via `trialBalanceDAOService.getOracleLevelDataForDate(...)`; writes Oracle-level sheet via `BranchOrOracleReportWriter` and exports a text file.
- `GenerateOglReportBatchTasklet`
  - What it does (in code): generates an OGL `.dat` file using `DatFileWriter` by iterating Oracle-level data from `trialBalanceDAOService.getOracleLevelDataForDate(...)`; skips rows with zero closing balance; sets DR/CR amounts based on sign of `closing_balance`.
- `GenerateZeroisationReportBatchTasklet`
  - What it does (in code): builds a “Post Zeroisation TB Report” Excel + text file for the given `reporting_date`; it loads opening balances for `firstDayOfFY` via `openingBalanceDAOService.findByDate(...)` and derives GL balances using `openingBalanceAfterZeroisation` (with fallback/aggregation).
- `TriggerZeroisationGLEntriesTasklet`
  - What it does (in code): selects income/expense GL codes via `generalLedgerDAOService.findIncomeAndExpenseGLCodes()`; for each opening balance entry (where openingBalance != 0 and `checkIncomeAndExpenseGl(...)` returns true) it sets `function_code="DEFAULT"`, `function_sub_code="TRANSACTION"`, `currency="INR"`, sets `gl_transaction_reference_number`, then calls internal API `glBalanceZeroisation` (`novopayInternalAPIClient.callInternalAPI(..., "glBalanceZeroisation", "v1", "glBalanceZeroisation", ...)`).
- `PopulateOpeningBalanceAfterZeroisationBatchTasklet`
  - What it does (in code): after zeroisation, loads (a) zeroisation transaction details and (b) opening balance entities for the `firstDayOfFY`; then adjusts `openingBalanceAfterZeroisation` for the next FY based on `TransactionDetailsEntity.crDrIndicator` and saves via `openingBalanceDAOService.saveAll(...)`; sets `TrialBalanceRunHistoryEntity.isZeroisationDone=true`.
- `PopulateOpeningBalanceNextFYBatchTasklet`
  - What it does (in code): on last day of FY (`tb_reporting_date == last_day_fy`), ensures opening balance entities exist for `firstDayOfNextFY`; if missing, it creates them from `LAST_REPORTED_DATE_MAP` stored in execution context; updates/creates `TrialBalanceRunHistoryEntity` with `tbLastRunDate`.
- `GenerateBranchReportBatchTasklet`
  - What it does (in code): generates “Branch Code Level TB Report” Excel + text export by fetching branch-level TB data via `trialBalanceDAOService.getBranchLevelDataForDate(...)` and writing with `BranchOrOracleReportWriter` (sheet name) and `TextFileWriter`.

### CRR response-fidelity discipline (2026-04-14 brain sync)
- For WebClient callback/post-processor flows (`ServiceExecutorPostProcessor`), CRR `status` and CRR `response` must be sourced from the same callback payload (`apiResponse`) so incident evidence remains coherent.
- Infra dependency: `WebClientServiceExecutorDecorator` executes post-processors with `apiResponse=null` on transport errors (`execute(executionContext, null)`), which is expected fail-path behavior.
- **Known-safe in this class:** `PostNEFTChildLoanBankDisbursementProcessor` logs CRR response from callback `apiResponse` (or explicit null-envelope), not from shared `ExecutionContext.response`.
- **Resolved risk:** historical child-MFT CRR mismatch (`GAP-061`) is closed; `PostMFTChildLoanBankDisbursementProcessor` now logs response from callback `apiResponse` (or explicit null-envelope) with null-safe request capture.
- Scan focus after any disbursement callback change:
  - `PostNEFTChildLoanBankDisbursementProcessor`
  - `PostMFTChildLoanBankDisbursementProcessor`
  - `WebClientServiceExecutorDecorator`

### 2026-04-14 CLB child creation parity (vtc/employee)
- `ChildLoanBookingEventsQueueDataPopulator` includes `loan_details` fields `vtc_id`, `sourcing_emp_id`, and `servicing_emp_id` in CLB queue payload data with member-first precedence.
- `PopulateDataForChildLoanBookingProcessor` passes those keys into child `createOrUpdateLoanAccount`; `CreateLoanAccountProcessor` persists them on child `loan_account` (`filler_11`, sourcing/servicing fields), using member-level values when provided and parent fallback otherwise.

### 2026-04-13 Disbursement notes (reinit + child callback duplicate guard)
- Parent payment reinitiation bank leg now uses dedicated CRR transaction types with `*_REINIT` suffix (`_MFT_REINIT`, `_NEFT_REINIT`, `_NEFT_NEF_REINIT` / `_NEFT_NEI_REINIT`) inside `CallBankAPIForDisbursementProcessor`, so normal lane idempotency and reinit lane idempotency stay isolated.
- Reinit NEFT inquiry/dispatch derives stage from latest reinit transaction type instead of requiring loan status rollback from `COMPLETED`; loan `disbursement_status` is not regressed on successful reinit NEFT progression.
- `mfi_orc.xml` `REINITIATE_BANK` control now enforces `do_child_bank_transactions=false` (SHG parent-child flow excluded from payment reinitiation path).
- `DoGenericSyncSTPBankNeftCallBackProcessor` child failed-callback path keeps CLMT `disbursement_status=NEFT_STAGE_1_SUCCESS` for duplicate ST_NEF failures (`*0004`) to stop repeated ST_NEF retries from `childLoanEventProcessingBatchJob`.
- L1 extension: for child ST_NEI duplicate-like failed callbacks, queue status transitions are now evidence-gated (queue status/event + same-transaction-type CRR success). Without definitive stage-2 success evidence, status remains `NEFT_STAGE_2_PENDING`; `COMPLETED` and parent sync happen only when success is proven.


---

