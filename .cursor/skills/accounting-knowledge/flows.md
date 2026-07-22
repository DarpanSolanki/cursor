<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.mdc only routes here. -->

## Whole-module orchestration walkthroughs (code-verified)

### Tax Component & Tax Group APIs (Service Orchestration XML)
These requests are configuration/master-data APIs. They don’t directly perform GL posting legs themselves; instead they persist tax component/tax group definitions (including slabs) that downstream charge/tax calculation + transaction partitioning rely on.

### `createOrUpdateTaxComponent`
- Makers/checker behavior is controlled by `maker_checker_enabled`:
  - `maker_checker_enabled=1` builds an approval payload (`constructRequestDataForApproval`) and submits via `accounting_submitApplication`.
  - `maker_checker_enabled=0` runs the create/update processors directly.
- CREATE path (function_code=`DEFAULT`, function_sub_code=`CREATE`):
  - `createTaxComponentProcessor`: persists `TaxComponentEntity` (requires `InternalAccountDefinitionEntity`)
  - if `computation_type != TAX_COM_EXT`: `validateTaxComponentSlabProcessor` + `parseDataForStartDateAndEndDateProcessor` + `createTaxComponentSlabProcessor` (persists `TaxComponentSlabEntity`)
- UPDATE path (function_sub_code=`UPDATE`):
  - `updateTaxComponentProcessor`: updates `TaxComponentEntity`
  - if `computation_type != TAX_COM_EXT`: `updateTaxComponentSlabProcessor` (updates slabs; can logical-delete old slabs depending on inputs)
- Delete and logical delete:
  - `deleteTaxComponent` (DEFAULT/APPROVE) uses `logicalDeleteTaxComponentProcessor` which sets `TaxComponentEntity.is_deleted=true`
  - if `computation_type != TAX_COM_EXT`, slab deletion is handled by `logicalDeleteTaxComponentSlabProcessor`

### `getTaxComponentList` / `getTaxComponentDetails`
- List/details are read-only:
  - `getTaxComponentListProcessor`: populates `tax_component_list` (paged)
  - `getTaxComponentDetailsProcessor`: populates component fields and `tax_component_slab_details` (unless `computation_type == TAX_COM_EXT`)

### `createOrUpdateTaxGroup` / `getTaxGroupList` / `getTaxGroupDetails` / `deleteTaxGroup`
- Tax group is a container that maps to a set of tax components.
- Create/update writers:
  - `createTaxGroupProcessor` / `updateTaxGroupProcessor`: persists `TaxGroupEntity` (requires `InternalAccountDefinitionEntity`)
  - `createTaxGroupTaxComponentMappingProcessor` / `updateTaxGroupTaxComponentMappingProcessor`:
    - persists `TaxGroupTaxComponentMappingEntity` linking tax_group_id ↔ tax_component_id
- Delete:
  - `deleteTaxGroup` uses logical delete via `logicalDeleteTaxGroupProcessor` which sets `TaxGroupEntity.is_deleted=true`
  - mapping deletion is handled by `logicalDeleteTaxGroupTaxComponentMapping` in the orchestration

### `createOrUpdateLoanAccount` (ORC entrypoint) -> initial loan account setup (CREATE) / mutate account attributes (UPDATE)
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="createOrUpdateLoanAccount"`).

#### CREATE path (function_sub_code=`CREATE`, run_mode=`REAL`)
This path creates the core loan account and its supporting “mode/interest” rows:
- `populateCurrentDateProcessor`
- `getOfficeDetails` + `getCustomerDetails` (internal APIs)
- validations/builders: `validateLoanAccountDetailsProcessor`, `validateDisbursementRepaymentAccountDetailsProcessor`, `populateRepaymentDetailsProcessor`, `getEffectiveInterestRateForInterestSetupCodeProcessor`, `populateInterestDetailsForAccountProcessor`, `populateDisbursementAmountProcessor`, `fetchBulkUniqueMasterData`
- `populatePerformedDateProcessor`
- `generateSequenceNumberProcessor` (sets `account_number`)
- `createLoanAccountProcessor`
  - Persists: `LoanAccountEntity` (via `LoanAccountDAOService.save(...)`)
  - Notable: sets `loan_account.disbursement_status = "LAN_CREATED"` and copies `external_ref_number` from context.
- `createAccountBalanceProcessor`
  - Persists: `AccountBalanceEntity` (initialized to `0` balances; via `AccountBalanceDAOService.save(...)`)
- `createActorAccountDetails` (internal API; creates actor-account mapping, not an accounting table here)
- `createDisbursementModeDetailsProcessor`
  - Persists: `LoanDisbursementModeDetailsEntity` (via `LoanDisbursementModeDetailsDAOService.saveLoanDisbursementDetails(...)`)
- `createRepaymentModeDetailsProcessor`
  - Persists: `LoanRepaymentModeDetailsEntity` (via `LoanRepaymentModeDetailsDAOService.saveLoanRepaymentDetails(...)`)
- `createAccountInterestDetailsProcessor`
  - Persists: `AccountInterestDetailsEntity` (via `AccountInterestDetailsDAOService.save(...)`)

#### UPDATE path (function_sub_code=`UPDATE`, run_mode=`REAL`)
This path mutates the existing loan rows and supporting mode/interest records:
- `validateUpdateLoanAccountDetailsProcessor`
- `populatePerformedDateProcessor`
- `updateLoanAccountProcessor`
  - Persists: `LoanAccountEntity` (loads by `account_number`, updates fields like `loan_status` / `disbursed_amount`, then `LoanAccountDAOService.save(...)`)
- `updateDisbursementModeDetailsProcessor`
  - Persists: `LoanDisbursementModeDetailsEntity` (loads by `loan_account_id`, updates mode/account routing/bank details, then `saveLoanDisbursementDetails(...)`)
- `updateRepaymentModeDetailsProcessor`
  - Persists: `LoanRepaymentModeDetailsEntity` (loads by `loan_account_id`, updates mode/account/routing/bank details, then `saveLoanRepaymentDetails(...)`)
- `updateAccountInterestDetailsProcessor`
  - Persists: `AccountInterestDetailsEntity` (loads by `account_id`, updates spread/setup/effective/penal rates and upfront-interest fields, then `AccountInterestDetailsDAOService.save(...)`)

### `postManualJournalEntry` (ORC entrypoint) -> persist manual JE + create GL posting partitions (transaction engine)
Source: `trustt-platform-accounting/deploy/application/orchestration/product_transaction_orc.xml` (Request `name="postManualJournalEntry"`).

This request creates a *Manual Journal Entry* header + GL-lines, then (optionally via maker-checker) posts the accounting legs using the transaction engine.

Key wiring:
- Dummy transaction classification:
  - dummyProcessor sets `transaction_type="MANUAL_JOURNAL_POSTING"` and `transaction_sub_type="GL"`
- Manual JE persistence:
  - `createManualJournalEntryDetailsProcessor`
    - Persists `ManualJournalEntryDetailsEntity` (via `ManualJournalEntryDetailsDAOService.saveOne(...)`)
    - Persists `ManualJournalEntryGlDetailsEntity` rows (via `ManualJournalEntryGlDetailsDAOService.saveOne(...)`)
    - Stores the generated header row in EC under `manual_journal_entry_details_entity`
  - `createDocumentProcessor` + `createManualJournalEntryDocumentDetailsProcessor`
    - Persists `ManualJournalEntryDetailsDocumentEntity` rows (links `dbDocumentIdList` → manual JE header)
- Posting (real-mode posting path for maker-checker disabled or after approval):
  - `validateAndPopulateDataForManualPostingProcessor`
  - `getTransactionCatalogueIdProcessor` + `generateTransactionReferenceNumberProcessor`
  - `createTransactionMasterProcessor` + `createTransactionMetadataProcessor`
  - `createPartitionDetailsForManualJournalPostingProcessor`
    - Uses `ExecuteTransactionRulesProcessor.createPartitionDetails(...)` to build `TransactionPartitionDetailsEntity` list
    - Sets TransactionRuleDTO:
      - `entityType="LOANS"`
      - `referenceCode="MNL_JRNL_ENTRY"`
      - `officeId`: `loanAccountEntity.officeId` when `manual_journal_entry_on=INTRA_BRNH`, otherwise uses config `loan.internal.account.default.office.id`
  - `createTransactionDetailsProcessor` and `updateManualJournalEntryDetailsProcessor`
    - `updateManualJournalEntryDetailsProcessor` sets:
      - `manual_je_status`
      - `transaction_reference_number`
      - approval/audit fields

Makers/checker behavior:
- `maker_checker_enabled=1`: creates JE in `manual_je_status=PENDING`, sends for approval via `constructRequestForApprovalUsingApprovalTemplate` + `accounting_submitApplication`; approval branch posts and updates status through `updateManualJournalEntryDetailsProcessor` (approval sets performed/approved fields).
- `maker_checker_enabled=0`: runs the posting path directly and updates `manual_je_status=APPROVED`.

### `reverseManualJournalEntry` (ORC entrypoint) -> reverse posted manual JE + mark reversed (reverseTransaction engine)
Source: `trustt-platform-accounting/deploy/application/orchestration/product_transaction_orc.xml` (Request `name="reverseManualJournalEntry"`).

This request reverses an already-posted manual journal entry by:
- populating reverse payload (processor in ORC wiring)
- calling the `reverseTransactionProcessor` inside the ledger engine
- updating both original + reverse manual JE rows

Verified entity updates:
- `updateReverseManualJournalEntryDetailsProcessor` (code-verified)
  - Loads original `ManualJournalEntryDetailsEntity` by `transaction_reference_number`
  - Loads reverse `ManualJournalEntryDetailsEntity` by `manual_je_number` in `PENDING`
  - Sets reverse entity fields:
    - `reverseTransactionReferenceNumber`
    - `manual_je_status`
    - approval/audit fields
  - Sets original entity:
    - `reversed=true`
  - Persists both via `ManualJournalEntryDetailsDAOService.saveOne(...)`

### `getManualJournalEntryList` (ORC entrypoint) -> paged listing of manual JE headers
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="getManualJournalEntryList"`).

Processors (code-verified):
- `GetManualJournalEntryListProcessor`
  - reads `page_size` + `offset` from EC (defaults `limit=10`, `offset=0`)
  - calls:
    - `ManualJournalEntryDetailsDAOService.getManualJournalEntryList(executionContext)`
    - `ManualJournalEntryDetailsDAOService.getManualJournalEntryListTotalCount(executionContext)`
  - populates EC:
    - `manual_journal_entry_details_list` (paged list)
    - `number_of_records`, and normalizes `page_size` / `offset`

### `getManualJournalEntryDetails` (ORC entrypoint) -> manual JE header + GL lines + documents (+ reversal fields)
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="getManualJournalEntryDetails"`).

Processors (code-verified):
- `GetManualJournalEntryDetailsProcessor`
  - input: `id` (long)
  - loads:
    - `ManualJournalEntryDetailsEntity` by id
    - `ManualJournalEntryGlDetailsEntity` list by manual JE header id
    - document mapping rows `ManualJournalEntryDetailsDocumentEntity` → resolves to `DocumentEntity` + `DocumentFileEntity`
  - populates EC fields used by the API response:
    - `manual_je_number`, `manual_journal_entry_on`
    - `currency`, `value_date`, `transaction_date`, `transaction_amount`, `remarks`, `manual_je_status`
    - reversal-related fields:
      - `reversal` / `reversed`
      - `transaction_reference_number` for original vs reverse based on `reversal` flag
      - `reversal_notes`, `reversal_reason` (+ master-data mapped `reversal_reason_value` when present)
    - `manual_journal_entry_gl_details` (array of debit/credit GL + amount)
    - `document_details` (array of document metadata + files)

### `executeLMSPortfolioTransfer` (ORC entrypoint) -> create portfolio transfer detail rows + internal GL transfer
Source: `trustt-platform-accounting/deploy/application/orchestration/product_transaction_orc.xml` (Request `name="executeLMSPortfolioTransfer"`).

This is a *two-step* flow:
1) `executeLMSPortfolioTransferProcessor` builds `PortfolioTransferDetailsEntity` rows (status `PENDING`) from existing loan GL balances.
2) if `auto_process=true` (or when retrying pending), it triggers internal API `doGLTransfer` to create transaction postings and complete transfer rows.

`executeLMSPortfolioTransferProcessor` (code-verified):
- Inputs read from EC:
  - `account_numbers` (JSONArray)
  - `source_office_id/code`, `destination_office_id/code`, `destination_emp_id`
  - `external_reference_code`, `auto_process`, `do_gl_transfer`, `do_employee_transfer`
- Idempotency:
  - queries existing `PortfolioTransferDetailsEntity` by `external_reference_code`
  - if existing rows contain any `status="PENDING"`:
    - skips creation
    - if `auto_process` triggers `doGLTransfer` retry for the provided accounts
  - if existing rows are non-pending:
    - returns existing records as `portfolio_transfer_details_list`
- GL category selection:
  - loads master data `ALLOWED_GL_CATEGORY_FOR_PORTFOLIO_TRANSFER` (`datatype="ALLOWED_GL_CATEGORY_FOR_PORTFOLIO_TRANSFER"`, `subType="DEFAULT"`)
  - fetches `GeneralLedgerEntity` rows and extracts GL codes + categories
- Detail creation:
  - for each loan account id:
    - reads GL movement/partition details via `transactionPartitionDetailsDAOService.findTransactionDetailsByEntityIdOfficeIdEntityTypeAndGlCodes(accountId, sourceOfficeId, "LOANS", glCodes)`
    - aggregates `creditBalance` and `debitBalance` based on `crDrIndicator` (`"C"` vs `"D"`)
    - creates one `PortfolioTransferDetailsEntity` per GL code:
      - `gl_credit_balance`, `gl_debit_balance`, `gl_net_balance`
      - `status="PENDING"`, `completionDate=null`, audit fields
- Completion trigger:
  - saves list and stores JSON in EC under `portfolio_transfer_details_list`
  - if `auto_process && !list.isEmpty()` calls internal API `doGLTransfer` with:
    - `transaction_type="PORTFOLIO_GL_TRANSFER"`
    - `transaction_sub_type="DEFAULT"`
    - `external_reference_code`, `destination_office_id/code`, `account_id_list`, `user_id`

`doGLTransfer` / `DoGLTransferProcessor` (code-verified):
- Fetches all `PortfolioTransferDetailsEntity` by `external_reference_code`
- For each record with non-zero `gl_net_balance`:
  - chooses debit/credit GL legs based on sign of net balance
  - creates source and destination transactions:
    - `TransactionMasterEntity`
    - `TransactionDetailsEntity` (debit + credit)
    - `TransactionPartitionDetailsEntity` with `referenceCode="GL_TRANSFER"` and `entityType="OFFICE"`
  - On master + details: `business_date` and `value_date` are both set from `PlatformDateUtil.getBusinessDateInLong()`; `transaction_date` (and related audit timestamps) use system time.
- Marks every transfer detail row:
  - `status="COMPLETED"`
  - `completionDate` and `updatedOn` set to platform business date (aligned with txn `business_date` / `value_date`)
- Updates loan/account office:
  - `loanAccountDAOService.updateAccountOfficeAndAuditByAccountIds(...)`
  - `loanAccountDAOService.updateLoanAccountOfficeAndAuditByAccountIds(...)`

### `doGLTransfer` (ORC entrypoint) -> inter-branch GL transfer for portfolio transfer details
Source: `trustt-platform-accounting/deploy/application/orchestration/product_transaction_orc.xml` (Request `name="doGLTransfer"`).

ORC wiring:
- Validators:
  - `external_reference_code` mandatory
  - `transaction_type` + `transaction_sub_type` mandatory
  - `function_code=function_sub_code=DEFAULT`
- Processors:
  - `setCommonAttributesProcessor`
  - `getTransactionCatalogueIdProcessor`
  - `doGLTransferProcessor`

`DoGLTransferProcessor` (code-verified summary):
- Fetches `PortfolioTransferDetailsEntity` by `external_reference_code`
- For each row with non-zero `glNetBalance`:
  - creates `TransactionMasterEntity`, `TransactionDetailsEntity` (debit + credit), and `TransactionPartitionDetailsEntity` legs with:
    - `referenceCode="GL_TRANSFER"`
    - `entityType="OFFICE"`
  - debit/credit leg selection is based on sign of `glNetBalance`
- Marks portfolio transfer details as:
  - `status="COMPLETED"`
  - sets `completionDate` + `updatedOn` to platform business date
- Updates office mapping for impacted accounts via:
  - `loanAccountDAOService.updateAccountOfficeAndAuditByAccountIds(...)`
  - `loanAccountDAOService.updateLoanAccountOfficeAndAuditByAccountIds(...)`
- EC outputs:
  - `created_transaction_master_ids`
  - `total_transactions_created`
  - `loan_accounts_updated`

### `disburseLoan` (ORC entrypoint) -> loan setup + disbursement GL legs + schedule/due creation
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="disburseLoan"`).

High-level flow:
- `populateUserDetails` → `validateLoanDisbursementDetailsProcessor` → `getLoanAccountDetails` (loads `loan_amount`, `expected_disbursement_date`, `disbursement_mode`, `upfront_interest_amount`, `upfront_interest_applicable`, etc.)
- maker-checker gating:
  - `maker_checker_enabled=1`: builds approval payload (`constructRequestForApprovalUsingApprovalTemplate`) and submits via `disburseLoan_submitApplication` (then deletes draft).
  - ledger posting + loan state mutation happen when `call_post_transaction_required=true` (DEFAULT with `maker_checker_enabled=0`, APPROVE, RESUBMIT, or TRIAL).

GL posting leg (`postTransaction`, nested API; code-verified):
- transaction type/sub-type selection by `disbursement_mode`:
  - `CASH` → `transaction_type=LOAN_DISBURSEMENT`, `transaction_sub_type=CASH`
  - `ACCTWB|OTHACWB` → `transaction_type=LOAN_DISBURSEMENT`, `transaction_sub_type=CASA`
    - also runs `populateDisbursementAccountProcessor`
    - then `populateTransactionAccountDetailsProcessor` with `placeholder=CASA_ACCOUNT` and narration `Loan Disbursement Credit`
  - `OTHBACCT` → `transaction_type=LOAN_DISBURSEMENT`, `transaction_sub_type=ACCOUNT_TRANSFER_NEFT`
- account details + additional amount:
  - `populateTransactionAccountDetailsProcessor` with `placeholder=LOAN_ACCOUNT` and narration `Loan Disbursement`
  - `populateAdditionalAmountDetailsProcessor` adds upfront interest as `additional_amount_details`:
    - `reference_code=INT_AMT`, `amount=upfront_interest_amount`
- nested `postTransaction` maps:
  - `logged_user_office_id` → `originating_office_id`
  - `currency_code` → `currency`
  - `loan_amount` → `amount`
  - `expected_disbursement_date` → `value_date`
  - captures `transaction_reference_number`, `account_level_transaction_details`, `overall_transaction_details`
- net extraction after GL posting:
  - `extractOverallTransactionDetailsAndNetAmountForAccountProcessor(extract_account_number=account_number)`

Loan/account + repayment schedule mutation (REAL, non-maker-checker path; code-verified):
- `validateGenerateRepaymentScheduleProcessor`
- `generateRepaymentScheduleProcessor`:
  - `expected_disbursement_date→schedule_effective_date`
  - `first_repayment_date→schedule_start_date`
  - `effective_interest_rate→interest_rate`
  - `loan_amount→principal_outstanding`
- `createRepaymentScheduleDetailsProcessor(schedule_number=1)`
- `createInstallmentAndDueDetailsProcessor(schedule_number=1)`
- `updateLoanAccountProcessor`:
  - `loan_amount→disbursed_amount`
  - `loan_status=ACTIVE`
  - `updated_by→performed_by`, `updated_on→performed_on`
- if `upfront_interest_applicable=true`:
  - `populatePaymentDetailsForDisbursementProcessor`
  - `updateLoanDueDetailsProcessor`
  - `updateLoanInstallmentDetailsProcessor(expected_disbursement_date→value_date)`

### `loanAccountReopening` (ORC entrypoint) -> closure reversal + status reset + post-reversal recomputation
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="loanAccountReopening"`).

This request is a maker-checker task flow:
- Validation + task creation (DEFAULT/create_task):
  - `validateDataForLoanAccountReopeningProcessor` (on non-REJECT paths)
  - `setCommonAttributesProcessor`
  - `createLoanAccountReopeningDetailsProcessor`
  - `create_task=true` branch: builds approval request + creates `LOAN_REOPEN_CHECKER` task
  - document creation:
    - `createDocumentProcessor`
    - `createLoanAccountReopeningDocumentProcessor`
  - then deletes draft (`deleteDraftProcessor`)
- Approval (APPROVE/do_reopen=true):
  - `initiateClosureReversalProcessor`
  - `getLoanAccountReopeningDetailsProcessor`
  - `reverseTransactionProcessor` with:
    - `value_date=${valueDateLongInStr}`
    - `created_by=${reversal_created_by}`
    - `created_on=${reversal_created_on}`
  - `updateLoanAccountClosureDetailsProcessor`
  - `updateLoanAccountReopeningTaskDetailsProcessor(status=APPROVED)`
  - `updateLoanAccountStatusProcessor`:
    - `loan_status=ACTIVE`, `account_status=ACTIVE`, `is_reopening_process=true`
- Post-reversal jobs:
  - `populateCurrentDateProcessor`
  - `populateEODJobDataAfterReversalProcessor(transaction_reversal_date=${valueDateLongInStr})`
  - `checkLoanAccountInterestAndPenalAccrualProcessor`
  - `checkLoanAccountInterestAccrualBookingProcessor` (function DEFAULT/DEFAULT, office_id/originating_office_id from request context, `is_forceful_booking=false`)
  - `loanAccountDpdCalcProcessor`
  - `loanAccountAssetCriteriaProcessor`:
    - forward movement: `REGULAR_TO_NPA` / `INT_INCOME`
    - reverse movement: `NPA_TO_REGULAR` / `INT_INCOME`
    - reference codes: `reference_code_int_amt=INT_AMT`, `reference_code_int_suspense_air_amt=INT_SUSPENSE_AIR_AMT`
  - `loanAccountAssetClassificationProcessor`
  - `bookingNonPostedPenalProcessor(job_time=${current_date_str})`
  - `initiateClosureTaxReversalProcessor`
  - `loanAccountPaymentsDetailsReversalProcessor`
  - `childLoanReopeningEventGenerationProcessor`
  - task deletion at end (`deleteTask`)

### `loanAccountTransactionReversal` (ORC entrypoint) -> transaction reversal task flow + ledger inversion + NPA bookkeeping
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="loanAccountTransactionReversal"`).

Task flow:
- Validation + optional task flags (run_mode REAL):
  - `validatePendingTxnReversalTaskProcessor`
  - `validateTransactionForLoanAccountProcessor(current_transaction_name=TXN_REVERSAL)`
  - `validateTransactionExcessAmountProcessor`
- Create task (function_code DEFAULT|APPROVE, create_task=true):
  - `validateTransactionReversalDataProcessor` + `validateTransactionReversalBusinessCaseProcessor`
  - `createTransactionReversalDetailsProcessor`
  - `fetchBulkUniqueMasterData(reason=TRNS_REVL)`
  - constructs approval payload and then creates `TRANSACTION_REVERSAL_CHECKER` task (documents + task status PENDING)
- Approve task (approve_task=true):
  - `validateTransactionReversalDataProcessor`
  - `getTransactionReversalTaskDetailsProcessor(task_status=PENDING)`
  - `executeTransactionReversalProcessor` (prepares reversal engine input + reversal artifacts in EC)
  - `populateEODJobDataAfterReversalProcessor`
  - `populateLoanAccountPaymentDetailsDataProcessor`
  - `reverseTransactionProcessor`:
    - `transaction_reference_number=${transaction_ref_no}`
    - `created_by=${reversal_created_by}`
    - `created_on=${reversal_created_on}`
    - `value_date=${valueDateLongInStr}`
    - captures `reversal_reference_number` + `reversal_client_reference_number`
  - `convertTransactionValueDateProcessor`
  - `createLoanAccountPaymentsDetailsProcessor` with transaction refs from reversal outputs
  - recomputation:
    - `loanAccountDpdCalcProcessor`
    - `loanAccountAssetCriteriaProcessor` (forward REGULAR_TO_NPA / reverse NPA_TO_REGULAR, reference codes INT_AMT + INT_SUSPENSE_AIR_AMT)
    - `loanAccountAssetClassificationProcessor`
  - task update + delete (`updateTransactionReversalTaskDetailsProcessor(task_status=APPROVED)` + `deleteTask`)

### `childLoanTransactionReversal` (ORC entrypoint) -> child txn reversal + reverseTransaction + recomputation
Source: `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml` (Request `name="childLoanTransactionReversal"`).

Chain (code-verified):
- `executeTransactionReversalProcessor`
  - seeds `transaction_reference_number` from `transaction_reference_no` in EC
- `populateEODJobDataAfterReversalProcessor`
- `populateLoanAccountPaymentDetailsDataProcessor`
- `reverseTransactionProcessor`:
  - passes `created_by=${reversal_created_by}` and `created_on=${reversal_created_on}`
  - outputs `reversal_reference_number` and `reversal_client_reference_number`
- `convertTransactionValueDateProcessor` (converts EC `value_date` Date -> String millis)
- `createLoanAccountPaymentsDetailsProcessor`:
  - uses `transaction_reference_number=${reversal_reference_number}`
  - uses `client_reference_number=${reversal_client_reference_number}`
- recomputation:
  - `loanAccountDpdCalcProcessor`
  - `loanAccountAssetCriteriaProcessor` sets:
    - forward movement: `REGULAR_TO_NPA` / `INT_INCOME`
    - reverse movement: `NPA_TO_REGULAR` / `INT_INCOME`
    - reference codes: `reference_code_int_amt=INT_AMT`, `reference_code_int_suspense_air_amt=INT_SUSPENSE_AIR_AMT`
  - `loanAccountAssetClassificationProcessor`

### `childLoanReopening` (ORC entrypoint) -> closure reversal + set ACTIVE + post-reversal jobs
Source: `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml` (Request `name="childLoanReopening"`).

Chain (code-verified):
- setup:
  - `setCommonAttributesProcessor`
  - `populateChildLoanReopeningAccountDataProcessor`:
    - loads `loan_account_entity` and stores `str_office_id`
  - `initiateClosureReversalProcessor`
- ledger reversal:
  - `reverseTransactionProcessor` with `value_date=${valueDateLongInStr}` (ORC still passes millis for compatibility; **reversal ledger rows use configured business date for TM/TD `business_date` / `value_date`** — see `ReverseTransactionProcessor` notes above)
- closure + status:
  - `updateLoanAccountClosureDetailsProcessor`
  - `updateLoanAccountStatusProcessor`:
    - `loan_status=ACTIVE`, `account_status=ACTIVE`
- post-reversal recomputation and triggers:
  - `populateCurrentDateProcessor`
  - `populateEODJobDataAfterReversalProcessor(transaction_reversal_date=${valueDateLongInStr})`
  - `checkLoanAccountInterestAndPenalAccrualProcessor`
  - `checkLoanAccountInterestAccrualBookingProcessor` (DEFAULT/DEFAULT, office_id/originating_office_id from `str_office_id`, `is_forceful_booking=false`)
  - `loanAccountDpdCalcProcessor`
  - `loanAccountAssetCriteriaProcessor` (forward REGULAR_TO_NPA + reverse NPA_TO_REGULAR, reference codes INT_AMT + INT_SUSPENSE_AIR_AMT)
  - `loanAccountAssetClassificationProcessor`
  - `bookingNonPostedPenalProcessor(job_time=${current_date_str})`

### `childLoanBooking` (ORC entrypoint) -> child events processing (booking)
Source: `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml` (Request `name="childLoanBooking"`).

- For `function_code=DEFAULT`: runs `childLoanEventsProcessingProcessor`.

### `childLoanDisbursement` (ORC entrypoint) -> book child loan (disbursement booking)
Source: `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml` (Request `name="childLoanDisbursement"`).

Chain (code-verified):
- `populateDataForChildLoanBookingProcessor` — before `createOrUpdateLoanAccount`, if a non-deleted child already exists for `parent_loan_account_id` + member `external_ref_number` (oldest by `created_on`), reuses that `account_id` / LAN instead of creating another row (CLB replay idempotency). DB: **unique** partial index `uidx_accounting_la_child_parent_extref_active` on `mfi_accounting.loan_account` `(parent_loan_account_id, external_ref_number, loan_product_id)` where `parent_loan_account_id IS NOT NULL` — **created/maintained manually** (not shipped via accounting flyway in this workspace).
  - **Lookup query perf** (`LoanAccountRepository.findFirstActiveChildByParentAndExternalRef`): `WHERE parent_loan_account_id = ? AND external_ref_number = ? AND is_deleted = false` + `ORDER BY created_on LIMIT 1`. Uses **leading** index columns (`parent_loan_account_id`, `external_ref_number`) on `uidx_accounting_la_child_parent_extref_active` → expect **index access** (not seq scan on `loan_account`). Returned columns (`la_account_number`, `created_on`) are not in that index → **heap fetch** on matching row(s). `is_deleted` is **not** in the index partial predicate → **Filter** after index read. **Timing** is environment-specific — not measured in repo CI; run `EXPLAIN (ANALYZE, BUFFERS)` on `mfi_accounting` with real `parent_loan_account_id` / `external_ref_number`. Ballpark for a single lookup on a warm DB: **~1–5 ms** (order of magnitude only; verify locally).
- `bookChildLoanProcessor`

### `childLoanRepayment` (ORC entrypoint) -> child due settlement + GL posting + optional NPA reverse movement
Source: `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml` (Request `name="childLoanRepayment"`).

Core chain (code-verified):
- load child context: `populateChildLoanAccountDataProcessor`
- sets transaction type/sub-type by `repayment_mode`:
  - `CASH` / `DIRDR` → `LOAN_REPAYMENT/CASH`
  - `ACH` → `LOAN_REPAYMENT/CASH`
  - `UPI` → `LOAN_REPAYMENT/UPI`
  - `NET_BANKING` → `LOAN_REPAYMENT/NET_BANKING`
  - `EXCESS_AMT` → `LOAN_REPAYMENT/EXCESS_AMT`
- `getOfficeIdFromAccountNumberProcessor`
- appropriation eligibility gate: `checkEligibleForRepaymentAppropriationProcessor`
- if `do_repayment_appropriation=true`:
  - `repaymentApproppriationProcessor` (component allocation using liquidation order & precedence)
- excess-mode component prep:
  - `populateAmountForExcessRepaymentModeProcessor`
- builds `additional_amount_details` and component amounts used by due + GL:
  - `PRIN_AMT` (`principal_amount`)
  - `INT_AMT` (`interest_amount`)
  - `PENALTY_AMT` (`penalty_amount`)
  - `EXCESS_AMT` (`excess_amount`)
  - `SUSP_AMT` (`suspense_amount`)
  - `FEE_AMT` (`fee_amount`)
- transaction account + due/inst updates:
  - `populateTransactionAccountDetailsProcessor(placeholder=LOAN_ACCOUNT, narration="Loan Repayment", account_number)`
  - `updateLoanDueDetailsProcessor`
  - `updateLoanInstallmentDetailsProcessor`
  - `updateLoanAccountForExcessAmountProcessor`
- main GL posting via nested `postTransaction`:
  - `transaction_type=${transaction_type}`, `transaction_sub_type=${transaction_sub_type}`
  - `currency=INR`
  - `amount=${repayment_amount}`
  - captures `transaction_reference_number`
- persists payment-linking + NPA logic:
  - `createLoanAccountPaymentsDetailsProcessor`
  - `checkNPAReverseMovementRequiredProcessor`
- if `do_npa_reverse_movement=true`:
  - adds `INT_SUS_AMT` (`interest_amount`)
  - posts an additional `postTransaction` leg with `transaction_sub_type=NPA` and `amount=${interest_amount}` (client ref from `npa_client_reference_number`)
- auto-closure recomputation (only when `is_eligible_for_auto_closure=true`):
  - `populateLoanAutoClosureReqProcessor`
  - `loanAccountDpdCalcProcessor`
  - `loanAccountAssetCriteriaProcessor` forward REGULAR_TO_NPA + reverse NPA_TO_REGULAR (INT_INCOME) with reference codes INT_AMT + INT_SUSPENSE_AIR_AMT
  - `loanAccountAutoClosureProcessor(DEFAULT/AUTO)`
  - if `loan_account_status=CLOSED`: creates closure details via `createLoanAccountClosureDetailsProcessor`

### `loanRepayment` (ORC entrypoint) -> due + installment settlement mutation
ORC wiring (validated in `deploy/application/orchestration/loans_orc.xml`):
- Appropriation + due/installation updates happen in the `trial_mode_post_transaction` / `real_mode_post_transaction` blocks before the nested `API id="postTransaction"`.

Code-verified mutation path (repayment):
- `repaymentApproppriationProcessor` → `in.novopay.accounting.loan.repayment.processor.RepaymentApproppriationProcessor`
  - Allocation setup:
    - reads `repayment_amount` from `executionContext["repayment_amount"]`
    - loads:
      - `loan_account_entity` and `loan_product_entity`
      - `loan_due_details_list` (`LoanDueDetailsEntity` rows)
    - loads asset criteria slab via `LoanProductAssetCriteriaDAOService.getAssetCriteriaSlabDetailsByProductAndAssetCriteriaSlabId(productId, assetCriteriaSlabsId)`
      - extracts `liquidationOrder` from returned index `[4]`
      - builds component precedence via indices `[0..3]` into `approppriationSequenceMap` (maps to PRIN/INT/PENALTY/FEE via `APPROPPRIATION_COMPONENT_TYPE_MAP`)
  - Due-line ordering (liquidation strategy):
    - `LIQ_INSTL`: sort by `dueDate` ascending; tie-break by component precedence
    - `LIQ_COMP`: sort by component precedence; tie-break by `dueDate` ascending
    - `LIQ_INSTL_CHRG_COMP`: split due lines into
      - installments (`PRIN`/`INT`) + charges (`PINT`/`FEE`)
      - sort each group separately using the relevant comparator, then concatenate installments first, charges second
  - For each `LoanDueDetailsEntity` (doAppropriation):
    - computes `settledAmount = paidAmount + waivedAmount`
    - computes `pendingAmount = dueAmount - settledAmount`
    - sets `currentPaidAmount = min(repaymentAmount, pendingAmount)` (caps by pending)
    - sets transient `loanDueDetailsEntity.currentPaidAmount = currentPaidAmount`
    - increments totals:
      - `principal_amount` for componentType=`PRIN`
      - `interest_amount` for componentType=`INT`
      - `penalty_amount` for componentType=`PENALTY`
      - `fee_amount` for componentType=`FEE`
    - reduces remaining repayment:
      - `repaymentAmount = repaymentAmount - currentPaidAmount`
      - stops early when remaining becomes `0`
  - Sets execution-context outputs:
    - `principal_amount`, `interest_amount`, `penalty_amount`, `fee_amount`
    - `excess_amount` = rounded remainder (CurrencyUtil.roundAmount with `ROUND_OFF_TYPE_CCY`)
    - `total_settled_amount` = principal + interest + penalty + fee
    - `suspense_amount`:
      - if `loanAccountEntity.npaAgeingStartDate != null`, suspense_amount = `interest_amount`
      - else suspense_amount = `0`
- `updateLoanDueDetailsProcessor` → `in.novopay.accounting.loan.repayment.processor.UpdateLoanDueDetailsProcessor`
  - persists repayment at due-row level:
    - `loanDueDetailsEntity.paidAmount = paidAmount + currentPaidAmount`
    - `loanDueDetailsEntity.updatedBy/updatedOn`
    - calls `loanDueDetailsDAOService.saveEntityList(modifiedLoanDueDetailsList)`
  - builds `loan_due_details_payment_dto_map`:
    - if DTO not present: initializes DTO with `paidAmount = loanDueDetailsEntity.paidAmount` and `waivedAmount = 0`
    - writes DTO map back to `executionContext` under `loan_due_details_payment_dto_map`
- `updateLoanInstallmentDetailsProcessor` → `in.novopay.accounting.loan.repayment.processor.UpdateLoanInstallmentDetailsProcessor`
  - updates installment settlement and settlement flags:
    - `loanInstallmentDetailsEntity.settledAmount = settledAmount + currentPaidAmount(sum)`
    - sets `lastPaidDate`, `updatedOn`, `updatedBy`
    - sets `settled=true` if `mode == "prepayment"` OR `settledAmount >= dueAmount(PRIN+INT)`
    - calls `loanInstallmentDetailsDAOService.saveEntityList(...)`
- `createLoanDueDetailsLoanAccountPaymentsDetailsProcessor` → `in.novopay.accounting.loan.common.processor.CreateLoanDueDetailsLoanAccountPaymentsDetailsProcessor`
  - persists link table rows:
    - constructs `LoanDueDetailsLoanAccountPaymentsDetailsEntity` for each due DTO key:
      - copies `paidAmount`, `waivedAmount` (from `LoanDueDetailsPaymentDTO`)
      - copies `waiverDetailsId` if present
    - calls `lddLoanAccountPaymentsDetailsDAOService.saveEntityList(...)`

### `loanPrepayment` / foreclosure (ORC entrypoint) -> waiver/loss-bucket + BPI due-mutation
ORC wiring (validated in `deploy/application/orchestration/loans_orc.xml`):
- In the `do_prepayment` real block:
  - `updateDueDetailsForPrepaymentProcessor` runs before the nested `API id="postTransaction"`.
  - later the flow updates due/installment/loan status via `updateLoanDueDetailsProcessor`, `updateLoanInstallmentDetailsProcessor(mode=prepayment)`, and calls `updateExcessAmountForPrepaymentProcessor`.

Code-verified mutation path (prepayment):
- `updateDueDetailsForPrepaymentProcessor` → `in.novopay.accounting.loan.prepayment.processor.UpdateDueDetailsForPrepaymentProcessor`
  - computes and persists waiver/loss impacts by setting due-row `waivedAmount`:
    - calls `loanDueDetailsSuperListUtil.getDueDetailsByComponent(...)`
    - filters rows where `dueAmount > paidAmount + waivedAmount`
    - for each component bucket (INT/PRIN/BPI, plus current_lpp, foreclosure_fee, cbc_fee):
      - sets `LoanDueDetailsEntity.waivedAmount` to either remaining amount or bucket dueAmount
      - creates `WaiverDetailsEntity` with:
        - `waiverAmount`
        - `waiverStatus="APPROVED"`
        - `fullyWaived` flag
      - persists `WaiverLoanDueDetailsEntity`:
        - `identifierType="FORECLOSURE"`
        - `identifierValue=<prepaymentDetailsId>`
        - `waivedAmount`
  - BPI (gap interest) handling:
    - logically deletes future gap interest rows:
      - `logicalDeleteByLoanAccountIdAndComponentTypeAndDueDate(..., componentType="INT", dueDate=gapDueDate, foreclosureDate)`
    - creates a new due row as a copy:
      - sets `dueAmount = prepaymentDetailsEntity.bpiAmount`
      - sets/accumulates `waivedAmount` by adding `prepaymentDetailsEntity.bpiWaivedAmount`
    - persists waiver details and DTO map entries for the new BPI due row

- `prepaymentApproppriationProcessor` (component allocation) → `in.novopay.accounting.loan.prepayment.processor.PrepaymentApproppriationProcessor`
  - Allocation setup:
    - reads `total_foreclosure_amount` and per-component amounts from EC:
      - `principal_amount`, `interest_amount`, `penal_amount`, `fee_amount`
    - reads `foreclosure_date` as millis (`FORECLOSURE_DATE`) and converts to `repaymentValueDate`
    - loads `loan_due_details_list` via `LoanDueDetailsSuperListUtil.getDueDetails(loanAccountId, executionContext)`
    - loads asset criteria slab details (same `[0..4]` extraction) to build:
      - `liquidationOrder`
      - component precedence map (`approppriationSequenceMap`)
  - Due-line ordering:
    - `LIQ_INSTL`: by dueDate then component precedence
    - `LIQ_COMP`: by component precedence then dueDate
    - `LIQ_INSTL_CHRG_COMP`: split installment (`PRIN`/`INT`) + charge (`PINT`/`FEE`), sort each, then concatenate
  - For each due line (doApproppriation):
    - computes `settledAmount = paidAmount + waivedAmount`
    - computes `pendingAmount = dueAmount - settledAmount`
    - principal (`PRINCIPAL`):
      - allocates when componentType=`PRIN` with no dueDate gate:
        - `currentPaidAmount = min(pendingAmount, remainingPrincipalAmount)`
        - subtracts from `principalAmount` remaining
    - interest (`INTEREST`):
      - allocates when:
        - `dueDate <= repaymentValueDate`, OR
        - `isGapInterestApplicable(repaymentValueDate, loanAccountId, executionContext)` is true
      - `isGapInterestApplicable(...)` checks previous/next due dates around `repaymentValueDate`:
        - if `prevDueDate` is null, it falls back to `loanAccountEntity.expectedDisbursementDate`
        - returns true when `repaymentValueDate` lies within `[prevDueDate, nextDueDate]`
    - penalty (`PENALTY`):
      - allocates only when `dueDate <= repaymentValueDate`
    - fee (`FEE`):
      - allocates regardless of dueDate (it uses `currentPaidAmount = min(pendingAmount, remainingFeeAmount)`)
    - else:
      - sets `currentPaidAmount=0`
  - Sets EC outputs:
    - `principal_amount`, `interest_amount`, `penalty_amount`, `fee_amount` (updated remaining-allocated totals)
    - `excess_amount = 0`
    - replaces `loan_due_details_list` with modified due rows

### `loanAccountPartPrepayment` -> part prepayment appropriation (PAP: gate + reuse repayment allocation) 
Code-verified appropriation path (part prepayment transaction):
- `PopulateAdditionalAmountForPartPrepaymentProcessor` → `in.novopay.accounting.loan.partprepayment.processor.PopulateAdditionalAmountForPartPrepaymentProcessor`
  - Sets up transaction context:
    - sets `transaction_type` (PART_PREPAYMENT) and `transaction_sub_type` (instrumentType)
    - builds EC “repayment style” inputs so it can reuse repayment appropriation:
      - `repayment_amount = overDueAmount + overDueFeeCharges + dueAmount`
      - `repayment_time = rescheduling_effective_date`
      - `account_number` + `loan_account_entity`
      - sets `is_part_prepayment_call=true`
  - Eligibility gate:
    - calls `CheckEligibleForRepaymentAppropriationProcessor`
      - if due details list is empty OR (loan status inactive AND NOT part-prepayment call):
        - sets `principal_amount/interest_amount/penalty_amount/fee_amount = 0`
        - sets `excess_amount = repayment_amount`
        - clears `loan_due_details_list`
        - sets `do_repayment_appropriation=false`
      - else:
        - sets `do_repayment_appropriation=true` and seeds:
          - `loan_due_details_list`
          - `loan_product_entity`
  - Allocation execution (when gate allows):
    - if `do_repayment_appropriation=true`, it executes `repaymentApproppriationProcessor` (same liquidation-order logic as `loanRepayment`)
  - Excess/advance propagation into GL additional amounts:
    - `processExcessAmount(...)` pushes advance-sourced additional amount details:
      - `ADV_OVER_DUE_PRIN_AMT`, `ADV_OVER_DUE_INT_AMT`, `ADV_OVER_DUE_PENALTY_AMT`, `ADV_OVER_DUE_FEE_AMT`
      - plus `ADV_SUSP_AMT`, `ADV_PRIN_AMT`, `ADV_INT_AMT`, `ADV_PART_PREPAYMENT`
  - Overdue additional amounts when totalDues > 0:
    - populates `OVER_DUE_PRIN_AMT`, `OVER_DUE_INT_AMT`, `OVER_DUE_PENALTY_AMT`, `OVER_DUE_FEE_AMT`, `SUSP_AMT`
  - Part-prepayment specific additional amount details:
    - `additional_amount_details` includes:
      - `PRIN_AMT` (net part prepay amount)
      - `INT_AMT` (only when bpiAmount > 0)
      - `PART_PREPAYMENT` charges (only when charges > 0)
  - Tax reference setup:
    - `populateTaxAdditionalInfo(...)` resolves product scheme transaction charge config:
      - derives `price_setup_code` and its `tax_group_id`
      - calls `TaxAmountUtiltyService.populateTaxExternalReference(...)` to create deterministic external tax reference ids

### `loanAccountRebooking` (ORC entrypoint) -> regenerate repayment schedule with new ROI (+ optional interest adjustment posting)
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="loanAccountRebooking"`).

Validators (ORC):
- `function_code=function_sub_code=DEFAULT` (`patternFieldValidator`)
- `account_number`, `existing_roi`, `new_roi`, `rebooking_effective_date`
- ROI format validation + numeric range for `rebooking_effective_date`

Processor chain (code-verified wiring):
- `populateUserDetails`
- `setCommonAttributesProcessor`
- API `loanAccountRebooking_getLoanAccountDetails` (`getLoanAccountDetails` v1; maps `id` → `account_id`)
- `executeLoanAccountRebookingProcessor`

Post Transaction (code-verified from ORC + processor EC flags):
- If `${excess_int_amt_txn}=true`:
  - populates additional amounts for `EXCESS_PAID`, `EXCESS_BILLED`, `NPA_EXCESS_BILLED`
  - posts `postTransaction` with:
    - `transaction_type=LOAN_REBOOKING`
    - `transaction_sub_type=INTEREST_ADJUSTMENT`
    - `amount=${excess_interest_amount}`
- If `${less_int_amt_txn}=true`:
  - populates additional amount `LESS_INT_AMT` with `amount=${less_interest_amount}`
  - posts `postTransaction` with:
    - `transaction_type=LOAN_REBOOKING`
    - `transaction_sub_type=INTEREST_ADJUSTMENT`
    - `amount=${less_interest_amount}`
- On `${post_txn=true}`:
  - `populateTransactionAccountDetailsProcessor` (placeholder `LOAN_ACCOUNT`, narration `Loan Rebooking`)
  - `postTransaction` with `originating_office_id=${logged_user_office_id}`, `office_id=${office_id}`, `function_code/function_sub_code=DEFAULT`, `currency=INR`
  - `createLoanAccountPaymentsDetailsProcessor` with:
    - `value_date=${rebooking_effective_date}`
    - `repayment_amount=${txn_amount}`
    - `repayment_mode=REBKG`

`ExecuteLoanAccountRebookingProcessor` (code-verified core):
- Regenerates repayment schedule with new ROI and computes interest diff vs existing schedule
- Sets EC flags:
  - `${excess_int_amt_txn}` for negative interest diff (EXCESS case)
  - `${less_int_amt_txn}` for positive interest diff (LESS case)
- Deletes and recreates due/installment/schedule details from the current schedule number onward
- Updates `AccountInterestDetailsEntity.effectiveRate` to `newROI`
- Writes EC amounts:
  - `principal_amount`, `interest_amount`, `penalty_amount`, `fee_amount`
  - `excess_amount="0.000000"`
  - `client_reference_number="LR"+accountId+<timestamp>`

### `childWaiveLoanAccountCharges` (ORC entrypoint) -> child due waivedAmount + waiver identifier linkage rows
Source: `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml` (Request `name="childWaiveLoanAccountCharges"`).

Processor chain (code-verified wiring):
- `populateChildLoanWaiverDataProcessor`
- `updateLoanDueDetailsForWaiverProcessor`
- `updateWaiverLoanDueDetailsProcessor`

EC behavior:
- Builds `waiver_details_entity_list` from `waiver_details_list`
- Updates `LoanDueDetailsEntity.waivedAmount` (additive) and creates per-installment waived mapping
- Persists `WaiverLoanDueDetailsEntity` rows:
  - `identifier_type` (defaults to `WAIVER`)
  - `identifier_value` = waiver entity id
  - `loan_due_details_id` + `waived_amount`

Idempotency/dedupe:
- No explicit dedupe guard in this request chain; repeated invocations can re-apply waived amounts.

### `cancelLoanForeclosure` (ORC entrypoint) -> mark foreclosure/prepayment task rejected + reactivate loan
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="cancelLoanForeclosure"`).

Validators (ORC):
- `account_number` mandatory
- `function_code=function_sub_code=DEFAULT`

Processor chain:
- `cancelLoanForeclosureProcessor`
- If `${task_status}` is NOT `APPROVED|REJECTED`, calls API `loanForeclosure_deleteTask` to delete task details for `task_id`

`CancelLoanForeclosureProcessor` (code-verified):
- Reads `account_number`, `reject_reason`, `notes`
- Resolves `prepaymentDetailsId` and `loanAccountId`
- Marks:
  - `PrepaymentDetailsEntity.deleted=true`
  - `PrepaymentDetailsEntity.task_status=REJECTED`
  - sets `rejectReason` + `notes`
  - marks ALL related `PrepaymentChargeDetailsEntity.deleted=true`
- Sets `LoanAccountEntity.loanStatus=ACTIVE` and updates `loanAccountUpdatedBy/On`
- Writes EC:
  - `task_id`
  - `task_status`

### Waiver persistence primitives (charged-off / foreclosure waivers)
Code-verified waiver persistence:
- `updateLoanDueDetailsForWaiverProcessor` → `in.novopay.accounting.loan.waiver.processor.UpdateLoanDueDetailsForWaiverProcessor`
  - for each `WaiverDetailsEntity` in `executionContext["waiver_details_entity_list"]`:
    - loads `LoanDueDetailsEntity` by `loanDueDetailsId`
    - accumulates `loanDueDetailsEntity.waivedAmount = waivedAmount + entity.waiverAmount`
    - saves due-row via `loanDueDetailsDAOService.saveOne(...)`
    - accumulates a per-installment map in `executionContext` under `waiver_installment_id_map`
- `updateWaiverLoanDueDetailsProcessor` → `in.novopay.accounting.loan.waiver.processor.UpdateWaiverLoanDueDetailsProcessor`
  - persists `WaiverLoanDueDetailsEntity` rows by copying:
    - `identifierType` (defaults to `"WAIVER"` unless `waiver_identifier_type` execution key is present)
    - `identifierValue = waiverDetailsEntity.id`
    - `loanDueDetailsId` and `waivedAmount`

### Billing state selection + posting trigger (ACTIVE-only)
Code-verified billing selection and post trigger:
- `loanAccountBilling` (batch) uses an ACTIVE-only partition query:
  - `PARTITION_DATA_QUERY = SELECT la.account_id FROM loan_account la WHERE (la.loan_status = 'ACTIVE')`
- `LoanAccountBillingBatchService.processLoanAccountBilling(...)` sets and posts:
  - `transaction_type="BILLING"`, `transaction_sub_type="NORMAL_BILLING"`
  - sets:
    - `account_details=[{placeholder:"LOAN_ACCOUNT", account_number:<accountNumber>, narration:""}]`
    - `principal_amount` and `interest_amount` as execution locals and into `additional_amount_details`
    - `amount = principal + interest`
    - `value_date`, `currency`, `originating_office_id`
  - calls internal API: `postTransaction` with identifier `billing_postTransaction`

### Excess refund state mutation (derived from due paid/waived buckets)
Code-verified computation + state update:
- `ProactiveExcessAmountRefundItemWriter.executeExcessAmountRefund(...)`
  - uses due table state to compute due outstanding:
    - for each `LoanDueDetailsEntity` in `loanDueDetailsDAOService.getDueDetails(loanAccountId, new Date())`:
      - `totalDueAmount += dueAmount - paidAmount - waivedAmount`
  - computes `total_refund_amount` as:
    - `loanAccount.excessAmount - totalDueAmount`
  - sets execution-context totals:
    - `total_refund_amount`, `repayment_amount`
  - updates `loanAccount.excessAmount` based on diff logic:
    - if computed diff is negative: sets excessAmount = null
    - else: sets excessAmount = diff
- it then updates loan account again in `updateLoanAccountDetails(...)` on success:
  - `loanAccountEntity.setExcessAmount(proactiveRefundDTO.getExcessAmount())`
  - sets `loanAccountUpdatedBy="SYSTEM"`, `loanAccountUpdatedOn=<now>`

### Auto-closure state mutation (closure orchestration before GL)
Code-verified closure state updates and processor invocation:
- `LoanAccountClosureService.processIndividualAccount(...)`
  - sets `loanAccountEntity.loanStatus = CLOSED`
  - sets `loanAccountEntity.status = AccountStatus.CLOSED` and closing dates
  - saves via `loanAccountDAOService.save(loanAccountEntity)`
- `LoanAccountClosureService.doClosureRelatedTransactions(...)` (when auto closure tolerance path triggers):
  - calls in order:
    - `createLoanAccountPaymentsDetailsProcessor.execute(...)`
    - `populateWaiverDetailsForUnpaidPenal(...)` and stores `waiver_details_entity_list` in execution-context
    - `updateLoanDueDetailsForWaiverProcessor.execute(...)`
    - `updateLoanInstallmentDetailsForWaiverProcessor.execute(...)`
    - `updateWaiverLoanDueDetailsProcessor.execute(...)` (with `WAIVER_IDENTIFIER_TYPE = AUTO_CLOSURE`)
    - `populateLoanDueDetailsPaymentDTO(executionContext)`
    - `createLoanDueDetailsLoanAccountPaymentsDetailsProcessor.execute(executionContext)`
    - `populateEODJobDataProcessor.execute(...)`
    - `loanAccountDpdCalcProcessor.execute(...)`
    - NPA movement criteria processors + `loanAccountAssetClassificationProcessor.execute(...)`

### `waiveLoanAccountCharges` (charge/fee waiver) -> due waived bucket + waiver detail rows
Code-verified mutation path:
- `createWaiverDetailsProcessor` → `in.novopay.accounting.loan.waiver.processor.CreateWaiverDetailsProcessor`
  - inserts `WaiverDetailsEntity` rows with `waiverStatus=PENDING`:
    - sets `loanAccountId`, `loanDueDetailsId`, `fullyWaived`, `waiverPercentage` (optional), `waiverAmount` (optional), `extRefNumber` (optional), `notes` (optional)
- `getWaiverDetailsProcessor` → `in.novopay.accounting.loan.waiver.processor.GetWaiverDetailsProcessor`
  - reads `waiver_details_list` (objects with `loan_account_number` + `loan_due_details_id`)
  - fetches pending waiver entities and stores:
    - `waiver_details_entity_list` (List of `WaiverDetailsEntity`)
    - `task_id`
- `updateLoanDueDetailsForWaiverProcessor` → `in.novopay.accounting.loan.waiver.processor.UpdateLoanDueDetailsForWaiverProcessor`
  - increments `loan_due_details.waived_amount`:
    - `updatedWaivedAmount = waiverAmount + current loanDueDetails.waivedAmount`
    - persists via `loanDueDetailsDAOService.saveOne(...)`
  - builds `waiver_installment_id_map` in execution-context (sum waived per `loan_installment_details_id`)
- `updateWaiverLoanDueDetailsProcessor` → `in.novopay.accounting.loan.waiver.processor.UpdateWaiverLoanDueDetailsProcessor`
  - inserts `WaiverLoanDueDetailsEntity` rows (one per `WaiverDetailsEntity`):
    - `identifierType = executionContext.waiver_identifier_type` if present, else `"WAIVER"`
    - `identifierValue = waiverDetailsEntity.id`
    - `loanDueDetailsId = waiverDetailsEntity.loanDueDetailsId`
    - `waivedAmount = waiverDetailsEntity.waiverAmount`

### `loanWriteoff` -> loan status WRITEOFF + due paid movement + installment settlement
Code-verified mutation path:
- `validateLoanWriteOffDataProcessor` → `in.novopay.accounting.loan.writeoff.processor.ValidateLoanWriteOffDataProcessor`
  - validates:
    - `value_date` equals today (midnight not applied; uses LocalDate.now)
    - `loan_status == ACTIVE`
  - computes execution-context amount seeds:
    - `principal_amount` from `loanDueDetailsDAOService.getPrincipalOutStandingAmount(loanAccountId)`
    - `interest_amount` from `loanDueDetailsDAOService.getInterestDueAmountByDueDate(loanAccountId, now)`
    - `penalty_amount` from `loanDueDetailsDAOService.getPenalDueAmountByDueDate(loanAccountId, now)`
  - enforces `writeoff_amount == principal + interest + penalty`
- `prepaymentApproppriationProcessor` → `in.novopay.accounting.loan.prepayment.processor.PrepaymentApproppriationProcessor`
  - allocates the writeoff amount across `loan_due_details` and sets `LoanDueDetailsEntity.currentPaidAmount`
  - allocation rules (from code):
    - `pendingAmount = dueAmount - (paidAmount + waivedAmount)`
    - `PRINCIPAL`: always allocates against `principalAmount`
    - `INTEREST`: allocates only when `dueDate <= repaymentValueDate` OR gap-interest eligibility is true
    - `PENALTY`: allocates only when `dueDate <= repaymentValueDate`
    - `FEE`: allocates against `feeAmount`
  - stores:
    - `loan_due_details_list` (modified due rows)
    - `principal_amount`, `interest_amount`, `penalty_amount`, `fee_amount`
    - `excess_amount = 0`
  - code-verified inconsistency note:
    - in `loans_orc.xml`, `loanWriteoff` invokes `prepaymentApproppriationProcessor` with `prepayment_amount=<writeoff_amount>`
    - but `PrepaymentApproppriationProcessor` reads `executionContext["total_foreclosure_amount"]` (not `prepayment_amount`) for `repaymentAmount`
    - `ValidateLoanWriteOffDataProcessor` does not set `total_foreclosure_amount`, so `total_foreclosure_amount` must already exist in `ExecutionContext` before entering `PrepaymentApproppriationProcessor` (e.g., seeded from request payload or another earlier processor).
- `updateLoanWriteOffStatusProcessor` → `in.novopay.accounting.loan.writeoff.processor.UpdateLoanWriteOffStatusProcessor`
  - sets `loan_account.loan_status = WRITOFF`
- `updateLoanDueDetailsProcessor` → `in.novopay.accounting.loan.repayment.processor.UpdateLoanDueDetailsProcessor`
  - persists due paid movement:
    - `loan_due_details.paid_amount = paidAmount + currentPaidAmount`
    - updates audit `updatedBy/updatedOn`
  - builds `settled_amount_map` (key=`loan_installment_details_id`, value=`sum currentPaidAmount per installment`)
  - initializes `loan_due_details_payment_dto_map` with `waivedAmount=0` for entries not already in the DTO map
- `updateLoanInstallmentDetailsProcessor` → `in.novopay.accounting.loan.repayment.processor.UpdateLoanInstallmentDetailsProcessor`
  - persists installment settlement:
    - `loan_installment_details.settled_amount = settled_amount_map[installment_id]`
    - sets `lastPaidDate`, `updatedOn/updatedBy`
    - sets `settled=true` if `mode == "prepayment"` OR settledAmount >= (principal+interest due amount)
- `createLoanAccountPaymentsDetailsProcessor` → `in.novopay.accounting.loan.common.processor.CreateLoanAccountPaymentsDetailsProcessor`
  - inserts `LoanAccountPaymentsDetailsEntity` (transaction/payment audit + component amounts + `mode`)

### `loanDisbursementCancellation` -> INT gap & FEE due mutation + waiver detail rows + logical deletions
Code-verified mutation path:
- `updateDueDetailsForDisbursementCancellationProcessor` → `in.novopay.accounting.account.loans.processor.UpdateDueDetailsForDisbursementCancellationProcessor`
  - input keys used:
    - `loan_account_entity`
    - `loan_disbursement_cancellation_details`
    - `loan_disbursement_cancellation_charge_details_list`
  - BPI / gap interest handling:
    - finds gap interest due row via `loanDueDetailsDAOService.findDueDetailForGapInterest(...)`
    - updates:
      - `gapDue.waivedAmount += bpiWaivedAmount`
      - `gapDue.paidAmount += bpiAmountToBePaid`
    - persists gap due row
    - if `bpi waivedAmount > 0`:
      - creates `WaiverDetailsEntity` with:
        - `identifierType`/identifier fields are stored via `WaiverLoanDueDetailsEntity` below
        - `waiverStatus="APPROVED"`, `fullyWaived` from cancellation details, and audit fields
      - creates `WaiverLoanDueDetailsEntity`:
        - `identifierType="DISB_CNCL"`
        - `identifierValue=<loanDisbursementDetailsEntity.id>`
        - `waivedAmount=<bpiWaivedAmount>`
  - cancellation fee handling:
    - creates new `LoanDueDetailsEntity` rows with:
      - `componentType="FEE"`, `chargeCode/chargeRate/chargeFixedAmount`, `baseAmount`
      - `dueDate=overdueDate=cancellationDate`
      - `dueAmount=chargeAmount`, `paidAmount=amountToBePaid`, `waivedAmount=waivedAmount`
    - persists and creates corresponding `WaiverDetailsEntity` + `WaiverLoanDueDetailsEntity` with `identifierType="DISB_CNCL"`
  - logical deletions after cancellation:
    - `logicalDeleteByLoanAccountIdAndComponentTypeAndDueDate(...)` for `componentType in ["INT"]` using:
      - `dueDate = gapInterestDueDetailsEntity.getDueDate()`
      - `now = cancellationDate`
    - `loanInstallmentDetailsDAOService.logicalDeletionOfFutureInstallmentsByLoanAccountIdAndDueDate(...)` (future installments from `now`)
- `updateExcessAmountForDisbursementCancellationProcessor` → `in.novopay.accounting.loan.cancellation.processor.UpdateExcessAmountForDisbursementCancellationProcessor`
  - sets `loan_account.excessAmount = newExcessAmount - oldExcessAmount`

### `childLoanDisbursementCancellation` (ORC entrypoint) -> child-disbursement cancel txn + due/BPI/status mutation
Source: `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml` (Request `name="childLoanDisbursementCancellation"`).

Processor chain (code-verified wiring):
- `setCommonAttributesProcessor`
- `populateChildLoanDisbursementCancellationDataProcessor`
- `checkLoanAccountInterestAccrualCalculationProcessor` with `value_date=${cancellation_date}`
- `checkLoanAccountInterestAccrualBookingProcessor` with `function_code/function_sub_code=DEFAULT` and `office_id=${logged_user_office_id}`
- Dummy sets:
  - `transaction_type=LOAN_DISB_CNCL`
  - `transaction_sub_type=CASH`
- `populateAdditionalAmountAndAccountDetailsForCancellationProcessor`
- `populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails`
- Nested `postTransaction` with:
  - `run_mode=REAL`
  - `originating_office_id=${logged_user_office_id}`
  - `transaction_type=${transaction_type}`, `transaction_sub_type=${transaction_sub_type}`
  - `client_reference_number=${client_reference_number}`
  - `value_date=${cancellation_date}`
  - `currency=INR`
  - `amount=${total_cancellation_amount}`
  - captures `transaction_reference_number`
- `createLoanAccountPaymentsDetailsProcessor`:
  - principal: `net_principle_outstanding_amount`
  - interest: `bpi_amount_to_be_paid`
  - fee: `cancellation_fee_amount_to_be_paid`
  - penalty=0, excess_amount=0
  - `transaction_reference_number` + `client_reference_number` wiring
- Mutations after GL posting:
  - `updateLoanDueDetailsDataProcessor` with `set_int_deleted=true`, `set_prin_paid=true`
  - `updateLoanBPIDataProcessor`
  - `updateLoanInstallmentDataProcessor`
  - `updateLoanAccountStatusProcessor`:
    - `loan_status=DISB_CNCL`
    - `account_status=CANCELLED`
    - `set_excess_amount=true`

### `loanAccountExcessAmountRefund` -> validate refund amount + reduce loan_account.excess_amount + record payment details
Code-verified mutation path:
- `validateDataForLoanAccountExcessAmountRefundProcessor` → `in.novopay.accounting.loan.excessamountrefund.processor.ValidateDataForLoanAccountExcessAmountRefundProcessor`
  - validates:
    - parent/SHG child excess consistency
    - lock-in period using existing `loan_account_payments_details` and `refundLockInPeriod`
  - validates monetary correctness:
    - `totalDueAmount = sum(dueAmount - paidAmount - waivedAmount)` across due details (as of `refundEffectiveDate`)
    - enforces `totalRefundAmount == loanAccount.excessAmount - totalDueAmount`
  - seeds `LOAN_ACCOUNT_ENTITY` and `customer_id` into execution-context
- `executeExcessAmountRefundProcessor` → `in.novopay.accounting.loan.excessamountrefund.processor.ExecuteExcessAmountRefundProcessor`
  - adjusts `loan_account.excessAmount`:
    - `diff = excessAmt - totalRefundAmount`
    - if diff < 0: sets `loanAccount.excessAmount = null`
    - else: sets `loanAccount.excessAmount = diff`
    - persists with updatedBy/updatedOn
  - sets execution-context:
    - component amounts to `"0.000000"`
    - `client_reference_number = "EAR" + loanAccountId + <timestamp>`
- In approve path, `createLoanAccountPaymentsDetailsProcessor` inserts `LoanAccountPaymentsDetailsEntity` with:
  - `repayment_amount = total_refund_amount`
  - `excess_amount = total_refund_amount`
  - `mode = payment_mode`

### `fetchLoanAccountChargeDetails` (ORC entrypoint) -> configured charge/tax breakdown + placeholder fallback
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="fetchLoanAccountChargeDetails"`).

Validators (ORC):
- `function_code=DEFAULT`
- `function_sub_code=DEFAULT|BY_PRICE_SETUP_CODE`

Processor:
- `fetchLoanAccountChargeDetailsProcessor` (DEFAULT flow)
- `fetchChargeDetailsProcessor` (BY_PRICE_SETUP_CODE flow)

`FetchLoanAccountChargeDetailsProcessor` (code-verified core outputs):
- writes `product_scheme_id`
- writes `charges_details` (JSONArray)
- writes `charges_configured`:
  - `"true"` when non-placeholder charges exist
  - `"false"` when it falls back to a placeholder
- placeholder fallback (code-verified):
  - includes `charge_identifier="PROC_FEE"` with `charge_value=0` when no configuration exists

### `calculateAnnualPercentageRate` (ORC entrypoint) -> APR (annual percentage rate)
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="calculateAnnualPercentageRate"`).

Processor:
- `calculateAnnualPercentageRateProcessor`

EC inputs:
- `nper`, `nper_type`, `pmt`, `pv`

EC outputs:
- `annual_percentage_rate`

### `calculateStampDutyCharges` (ORC entrypoint) -> stamp duty + surcharge + POA
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="calculateStampDutyCharges"`).

Processor:
- `calculateStampDutyChargesProcessor`

EC inputs:
- `state_code`, `product_code`, `loan_amount`

EC outputs (key shape):
- `charge_identifier="STAMP_DUTY"`
- `stamp_duty_charges`, `poa`
- surcharge outputs:
  - `is_surcharge_applicable`, `surcharge_type`, `surcharge_amount`, `surcharge_percentage_value`

### `fetchPartPrepaymentRepaymentSchedule` (ORC entrypoint) -> part prepayment repayment schedule preview (generate_repayment_schedule=false)
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="fetchPartPrepaymentRepaymentSchedule"`).

Processor chain (code-verified wiring):
- `dummyProcessor` (sets `function_code=DEFAULT`)
- `populateUserDetails`
- `setCommonAttributesProcessor`
- `validateLoanAccountPartPrepaymentProcessor`
- `generateLoanAccountPartPrepaymentRepaymentScheduleProcessor` with `generate_repayment_schedule=false`

Preview mode:
- computes schedule keys into EC (no persistence).

### `fetchRestructuringRepaymentSchedule` (ORC entrypoint) -> restructuring repayment schedule preview (generate_repayment_schedule=false)
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="fetchRestructuringRepaymentSchedule"`).

Processor chain (code-verified wiring):
- `populateUserDetails`
- `setCommonAttributesProcessor`
- `validateLoanRestructuringBusinessCaseProcessor`
- `populateRegisterLoanAccountRescheduleDataPreProcessor`
- `registerLoanAccountRescheduleEventProcessor` (identifier_type `EMIORTENOR`, generate_repayment_schedule=false)
- `generateLoanAccountRestructuringRepaymentScheduleProcessor`

Preview mode:
- computes schedule keys into EC (no persistence).

### `fetchLoanForeclosureSimulationDetails` (ORC entrypoint) -> foreclosure simulation amounts + charges (including fees and CBC components)
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="fetchLoanForeclosureSimulationDetails"`).

Processor chain (high-level wiring):
- validates/prepares foreclosure inputs and super-data
- computes prin/int for foreclosure
- calls `fetchLoanForeclosureSimulationDetailsProcessor`
- (optional) channel-based DDP borrower/loan details enrichment

Key EC outputs:
- `billed_principal`, `billed_interest`
- `future_principal`, `balance_principal`
- `bpi_amount`, `current_lpp`, `excess_amount`
- `charges_details` (JSONArray)

### `fetchDisbursementCancellationSimulationDetails` (ORC entrypoint) -> disbursement cancellation simulation amounts + fee/taxes
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="fetchDisbursementCancellationSimulationDetails"`).

Processor chain (high-level wiring):
- prepares cancellation inputs
- calls `fetchDisbursementCancellationSimulationDetailsProcessor` (TRIAL)

Key EC outputs:
- `charges_details` (JSONArray)
- `bpi_amount`, `principal_outstanding_amount`
- `excess_amount`, `cross_sell_amount`
- `cancellation_fee`
- `deducted_charges_details` (JSONArray)

### `generatePreEMIRepaymentSchedule` (ORC entrypoint) -> pre-EMI schedule generation (combined `installment_list`)
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="generatePreEMIRepaymentSchedule"`).

Processor:
- `generatePreEMIRepaymentScheduleProcessor`

EC outputs:
- `installment_list` (combined across tranches)

### `generateOnDemandDocument` (ORC entrypoint) -> generate PDF documents via report microservice
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request `name="generateOnDemandDocument"`).

Branching by `function_code/function_sub_code` selects which report template to generate, then uses `GenerateReportProcessor`.

EC outputs (key shape):
- `document_details` (JSONArray; each contains `document_code`, `version`, and `file_names[]`)

### `extractCasaBalanceFor180ProductCode` (ORC entrypoint) -> CASA balance extraction batch trigger for product code 180
Source: `trustt-platform-accounting/deploy/application/orchestration/mfi_orc.xml` (Request `name="extractCasaBalanceFor180ProductCode"`).

Processor:
- `extractCasaBalanceFor180ProductCodeBatchProcessor`

EC/side-effects:
- validates `op_code`
- uses `job_time` and sets `accts_under_pc_180_file_path`
- adds batch execution context via `BatchExecutionContextHolder`

### `extractCasaBalanceFor182ProductCode` (ORC entrypoint) -> CASA balance extraction batch trigger for product code 182
Source: `trustt-platform-accounting/deploy/application/orchestration/mfi_orc.xml` (Request `name="extractCasaBalanceFor182ProductCode"`).

Processor:
- `extractCasaBalanceFor182ProductCodeBatchProcessor`

EC/side-effects:
- validates `op_code`
- uses `job_time` and sets `accts_under_pc_182_file_path`
- adds batch execution context via `BatchExecutionContextHolder`

### `fetchLoanAccountsForCustomer` (ORC entrypoint) -> fetch active loans by customer IDs (status + product filters)
Source: `trustt-platform-accounting/deploy/application/orchestration/mfi_orc.xml` (Request `name="fetchLoanAccountsForCustomer"`).

Processor chain:
- `fetchCustomerAccountNumberProcessor`

Key EC outputs:
- `status` (`SUCCESS` on success)
- if none:
  - `customer_present="FALSE"`
  - `number_of_records=0`
  - `loan_account_list=[]`

### `bulkFileToSGManualJournalEntriesJob` (ORC entrypoint) -> bulk upload staging + trigger SG->Manual Journal posting
Source: `trustt-platform-accounting/deploy/application/orchestration/mfi_orc.xml` (Request `name="bulkFileToSGManualJournalEntriesJob"`).

Processors executed (ordered):
- `populateUserDetails`
- `bulkFileToSGManualJournalEntriesJobProcessor` -> `ParallelBatchJobV2.runBulkFileUploadJob(jobName, op_code, overrideParams)`

Spring Batch chain (file upload -> staging):
- Batch config: `FileToSGManualJournalEntriesBatchConfigService` -> `FileToStagingBatchConfigService`
- Worker step: `BulkFileToStagingIProcessor` (validates rows; sets staging row `status`) -> `FileToStagingIWriter` (writes temp partition CSVs)
- Tasklet step: `FileToStagingTasklet`
  - `COPY` temp CSVs into staging table: `file_staging_<upload_type.toLowerCase()>`
  - `duplicateCheck()` -> `batchDBHandlerService.updateForDuplicateBulk(...)` for `DUPLICATE_CHECK`
  - Updates overall file type status (maker-checker vs non-maker-checker) and triggers next `bulkSGTo*Job` via bulk upload internal APIs

Key EC inputs/outputs:
- Inputs used by `bulkFileToSGManualJournalEntriesJobProcessor`: `op_code`, `header_rows`, `file_upload_id`, `upload_type`, `job_time`, `user_id` (from `populateUserDetails`)
- Outputs written:
  - `function_sub_code = DEFAULT`
  - overrideParams: `temp_file_path`, `user_id`, `file_upload_id`, `upload_type`, `header_rows`, `job_time`
  - `BatchExecutionContext` stored via `BatchExecutionContextHolder.addBatchExecutionContext(...)`

File staging/table names:
- Staging load pattern: `file_staging_<upload_type.toLowerCase()>`
- Downstream SGTo reader for this flow expects: `file_staging_manual_journal_entries`

Nested accounting API calls:
- None in this stage (only bulk upload internal APIs to update file upload/file type status and start SGTo job).

Persistence/status update flow:
- Per-row validation status written into staging by batch worker (`PENDING`/`FAILED`).
- After `COPY`:
  - duplicates are marked `FAILED`
  - overall file type status is updated:
    - maker-checker: `PENDING_APPROVAL` + application submission
    - else: `FAILED` if `totalCount==0` or `successCount==0`, otherwise `PROCESS_READY` and SGTo job is started.

Dedupe/idempotency guards:
- Staging duplicate guard: `duplicateCheck()` using `DUPLICATE_CHECK` field validations.
- Ledger/posting idempotency is handled in the later SGTo job via `bulkSGToManualJournalEntriesJob`.

### `bulkSGToManualJournalEntriesJob` (ORC entrypoint) -> staged manual journal postings (postManualJournalEntry, per-row status)
Source: `trustt-platform-accounting/deploy/application/orchestration/mfi_orc.xml` (Request `name="bulkSGToManualJournalEntriesJob"`).

Processors executed (ordered):
- `populateUserDetails`
- `bulkSGToManualJournalEntriesJobProcessor` -> `ParallelBatchJobV2.runJob(jobName, op_code, overrideParams)`

Spring Batch chain (staging -> manual journal posting):
- Batch config: `SGToManualJournalEntriesBatchConfigService`
  - Step 1 (partitioned chunk):
    - Partitioning: `CustomBatchIdListPartitioner` using `dataQuery` over `file_staging_manual_journal_entries` (`sl_no` where `status NOT IN ('FAILED')`)
    - Reader: `SGToManualJournalEntriesIReader`
      - Reads from: `file_staging_manual_journal_entries`
      - Filters: `status NOT IN ('FAILED')` and `sl_no` between partition min/max
    - Processor: `SGToManualJournalEntriesIProcessor`
      - Pre-loads staging rows for `file_upload_id` and validates each:
        - enforces single LAN + SL_NO constraints
        - rejects invalid or child LANs
        - rejects manual journal for past date (based on `createdOn` vs current date)
        - validates GL debit/credit codes and office mapping
        - validates debit amount vs available GL balance derived from `TransactionPartitionDetailsEntity`
      - sets staging `status`/`reason` (`FAILED` on validation errors)
    - Writer: `SGToManualJournalEntriesIWriter`
      - For each successful staging record:
        - generates `manual_je_number` by calling `generateUniqueReferenceNumber` (sequence-based)
        - builds `manual_journal_entry_gl_details`
        - calls internal accounting API `postManualJournalEntry`
        - sets staging `status = SUCCESS` or `FAILED` + `reason`
  - Step 2 (tasklet): `SGToManualJournalEntriesTasklet`
    - counts staging failures and updates overall file type status to `SUCCESS` or `FAILED`

Key EC inputs/outputs:
- Inputs used by `bulkSGToManualJournalEntriesJobProcessor`:
  - `file_upload_id`, `op_code`, `user_id`, `LOGGED_USER_EMPLOYEE_FORMATTED_ID`
- Batch override params prepared by the ORC processor:
  - `user_id`, `file_upload_id`
  - `business_date_long` (from `PlatformDateUtil.getValueDateInLong()`)
  - `employee_formatted_id`
  - `dataQuery` for partitioning by `sl_no`

File staging/table names:
- `file_staging_manual_journal_entries`

Nested accounting API calls:
- `postManualJournalEntry`
- Ledger-level dedupe guard inside posting: `clientReferenceNumberDedupProcessor` using `client_reference_number = manual_je_number`

Persistence/status update flow:
- Per-row:
  - validation marks staging as `FAILED` with `reason`
  - successful rows are posted and then marked `SUCCESS` (or `FAILED` if posting fails)
- Overall:
  - `SGToManualJournalEntriesTasklet` sets overall to `SUCCESS` when `failedCount==0`, else `FAILED` with business validation message.

Idempotency/dedupe guards:
- Staging duplicate guard happens in the earlier file->staging stage.
- Ledger dedupe guard happens during `postManualJournalEntry`.

### `bulkFileToSGRefundMarkingJob` (ORC entrypoint) -> bulk upload staging + trigger SG->Refund marking
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request `name="bulkFileToSGRefundMarkingJob"`).

Processors executed (ordered):
- `populateUserDetails`
- `bulkFileToSGRefundMarkingJobProcessor` -> `ParallelBatchJobV2.runBulkFileUploadJob(jobName, op_code, overrideParams)`

Spring Batch chain (file upload -> staging):
- Batch config: `FileToSGRefundMarkingBatchConfigService` -> generic `FileToStagingBatchConfigService`
- Worker: `BulkFileToStagingIProcessor` -> `FileToStagingIWriter`
- Tasklet: `FileToStagingTasklet`
  - loads into `file_staging_<upload_type.toLowerCase()>`
  - `duplicateCheck()` + duplicate bulk update for `DUPLICATE_CHECK`
  - sets file type status and triggers SGTo via `startSGToFileTypeJob`

Key EC inputs/outputs:
- Inputs: `op_code`, `header_rows`, `file_upload_id`, `upload_type`, `job_time`, `user_id`
- Output: `function_sub_code=DEFAULT` and override params for the batch job

File staging/table names:
- staging load pattern: `file_staging_<upload_type.toLowerCase()>`
- downstream SGTo reader expects: `file_staging_refund_marking`

Dedupe/idempotency guards:
- `duplicateCheck()` at staging load stage.

### `bulkSGToRefundMarkingJob` (ORC entrypoint) -> evaluate refund eligibility and update loan flags
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request `name="bulkSGToRefundMarkingJob"`).

Processor:
- `bulkSGToRefundMarkingJobProcessor`

Spring Batch chain (staging -> refund eligibility updates):
- Batch config: `SGToRefundMarkingBatchConfigService`
  - Step 1 (chunk):
    - Reader: `SGToRefundMarkingItemReader`
      - reads from `file_staging_refund_marking`
      - filters `status NOT IN ('FAILED')` and partitions by id range
    - Processor: `SGToRefundMarkingItemProcessor`
      - calls `SGToRefundMarkingService.executeRefundMarking(...)`
      - sets staging:
        - `SUCCESS` if:
          - loan is not missing
          - loan is not a child LAN
          - and (`excessAmountRefundAllowed == true` OR `refundAllowed == "no"`)
        - else `FAILED` + reason (`Refund Not allowed for this Loan Product`)
    - Writer: `SGToRefundMarkingItemWriter`
      - persists staging rows
      - for `SUCCESS` updates `LoanAccountEntity.refundAllowed` + `refundRemarks`
      - propagates to child accounts too
  - Step 2 (tasklet): `SGToTypeTasklet`
    - updates overall file type status and sets final approval status.

Key EC inputs/outputs:
- Inputs used by ORC processor: `file_upload_id`, `user_id`, `op_code`
- Outputs: `function_sub_code=DEFAULT` + batch override params

Dedupe/idempotency guards:
- No explicit idempotency key; re-runs overwrite eligibility flags deterministically based on staging input and loan product config.

### `bulkFileToSGNocBlockUnblockJob` (ORC entrypoint) -> bulk upload staging + trigger SG->NOC block/unblock
Source: `trustt-platform-accounting/deploy/application/orchestration/mfi_orc.xml` (Request `name="bulkFileToSGNocBlockUnblockJob"`).

Processors executed (ordered):
- `populateUserDetails`
- `bulkFileToSGNocBlockUnblockJobProcessor` -> `ParallelBatchJobV2.runBulkFileUploadJob(...)`

Spring Batch chain (file upload -> staging):
- Batch config: `FileToSGNocBlockUnblockBatchConfigService` -> `FileToStagingBatchConfigService`
- Worker step: `BulkFileToStagingIProcessor` -> `FileToStagingIWriter`
- Tasklet step: `FileToStagingTasklet`
  - loads into `file_staging_<upload_type.toLowerCase()>`
  - runs duplicate validations via `duplicateCheck()`
  - triggers SGTo job using `startSGToFileTypeJob`

File staging/table names:
- staging load pattern: `file_staging_<upload_type.toLowerCase()>`
- downstream SGTo reader expects: `file_staging_noc_block_unblock`

### `bulkSGToNocBlockUnblockJob` (ORC entrypoint) -> validate/update NOC details and block/unblock statuses
Source: `trustt-platform-accounting/deploy/application/orchestration/mfi_orc.xml` (Request `name="bulkSGToNocBlockUnblockJob"`).

Processor:
- `bulkSGToNocBlockUnblockJobProcessor`

Spring Batch chain:
- Batch config: `SGToNocBlockUnblockBatchConfigService`
  - chunk step:
    - Reader: `SGToNocBlockUnblockIReader` from `file_staging_noc_block_unblock` where `STATUS NOT IN ('FAILED')`
    - Processor: `SGToNocBlockUnblockIProcessor`
      - validates:
        - loan exists and is not child LAN
        - loan status is `CLOSED`
        - NOC not already dispatched and `nocDocumentId == null`
        - requested new NOC action changes state (block/unblock cannot map to same existing)
      - updates/creates `LoanAccountNocDetailsEntity` and reason rows
      - mirrors update into child NOC details when `hasChildAccounts`
      - marks staging as `SUCCESS` or `FAILED` with `reason`
    - Writer: `SGToNocBlockUnblockIWriter` persists staging + NOC entities/reason rows (including child)
  - tasklet step: `SGToTypeTasklet` finalizes overall file type to `APPROVED` and sets staging statuses.

Idempotency/dedupe guards:
- Rejects no-op transitions (same action vs existing NOC state) to avoid duplicate state transitions on re-runs.
- Also avoids updates when NOC is already dispatched or document already exists.

### `bulkSGToSecNpaReverseFeedFileJob` (ORC entrypoint) -> SEC NPA reverse feed + asset criteria movements
Source: `trustt-platform-accounting/deploy/application/orchestration/mfi_orc.xml` (Request `name="bulkSGToSecNpaReverseFeedFileJob"`).

Processor:
- `bulkSGToSecNpaReverseFeedFileJobProcessor`

Spring Batch chain:
- Batch config: `SGToSecNpaReverseFeedFileBatchConfigService`
  - Reader: `SGToSecNpaReverseFeedFileIReader` from `file_staging_sec_npa_reverse_feed_file` (filters `status NOT IN ('FAILED')`)
  - Processor: `SGToSecNpaReverseFeedFileIProcessor`
    - validates loan account exists (else staging `FAILED`)
    - updates SEC NPA fields only when:
      - `secNpaReportingDate == null` OR `misDate > secNpaReportingDate`
  - Writer: `SGToSecNpaReverseFeedFileIWriter`
    - saves feed rows
    - sets movement-related EC keys and invokes `loanAccountAssetCriteriaProcessor.execute(...)`
      - may trigger GL movements via asset criteria processor paths
  - Tasklet: `SGToTypeTasklet` finalizes overall file type status

Persistence/status update flow:
- Staging feed rows saved; invalid feed rows marked `FAILED`.
- Overall file type marked `APPROVED` and staging statuses finalized.

Idempotency/dedupe guards:
- Loan SEC NPA fields update is guarded by the `secNpaReportingDate/misDate` condition.

### `bulkSGToTransactionReversalJob` (ORC entrypoint) -> batch reversal posting for staged transactions
Source: `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` (Request `name="bulkSGToTransactionReversalJob"`).

Processors:
- `bulkSGToTransactionReversalJobProcessor`

Spring Batch chain:
- Reader: `SGToTransactionReversalIReader` from `file_staging_transaction_reversal` (filters `STATUS NOT IN ('FAILED')`)
- Processor: `SGToTransactionReversalIProcessor`
  - calls `ValidateBulkTransactionReversalBusinessCasesService.validate(...)`
  - marks staging `FAILED` on business invalidations
- Writer: `SGToTransactionReversalIWriter`
  - seeds EC and calls:
    - `ExecuteTransactionReversalProcessor`
    - `populateEODJobDataAfterReversalProcessor`
    - `populateLoanAccountPaymentDetailsDataProcessor`
    - `reverseTransactionProcessor.execute(...)` (fatal if original transaction already reversed)
    - `convertTransactionValueDateProcessor`
    - `createLoanAccountPaymentsDetailsProcessor`
    - `createTransactionReversalDetailsProcessor` + save `TransactionReversalDetailsEntity` as `APPROVED`
    - `loanAccountDpdCalcProcessor` + `loanAccountAssetCriteriaProcessor` + `loanAccountAssetClassificationProcessor`
    - enqueues child reversal events if needed
  - on exception sets staging `FAILED` + `reason`
- Tasklet: `SGToTypeTasklet` finalizes overall file type based on success counts.

Idempotency/dedupe guards:
- Business validation blocks duplicates/in-progress rows.
- Ledger-level guard: `ReverseTransactionProcessor` (fatal if already reversed).

### `bulkSGToManualHoldMarkingJob` (ORC entrypoint) -> SI manual hold marking + hold presentation rows
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request `name="bulkSGToManualHoldMarkingJob"`).

Processors:
- `populateUserDetails`
- `bulkSGToManualHoldMarkingJobProcessor` -> `ParallelBatchJobV2.runJob(...)`

Spring Batch chain:
- Tasklet: `PopulateSIManualHoldMarkingTasklet`
  - Reads success staging rows from `file_staging_manual_hold_marking`
  - Validates:
    - loan account exists and is not CLOSED
    - parent-only LAN constraint
    - active SI mandate exists for the business date
    - CASA account exists and matches
  - Aggregates hold amounts per CASA account
  - Creates `SIManualHoldMarkingPresentationDetailsEntity`:
    - `manualHoldMarkingReferenceNumber = "NP"+yyyyMMdd+sequence(...)`
    - status `I` + audit fields
  - Saves FAILED staging rows with `reason`
- Tasklet: `SGToTypeTasklet` finalizes overall file type.

Dedupe/idempotency guards:
- Presentation reference numbers are generated from sequences; re-runs can duplicate rows unless upstream re-execution is prevented.

### `bulkSGToManualHoldRemovalJob` (ORC entrypoint) -> SI manual hold removal + hold-unhold presentation rows
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request `name="bulkSGToManualHoldRemovalJob"`).

Processors:
- `populateUserDetails`
- `bulkSGToManualHoldRemovalJobProcessor` -> `ParallelBatchJobV2.runJob(...)`

Spring Batch chain:
- Tasklet: `PopulateSIManualHoldRemovalTasklet`
  - Reads success staging rows from `file_staging_manual_hold_removal`
  - Validates:
    - loan account exists and is not CLOSED
    - parent-only LAN constraint
    - active SI mandate exists for the business date
    - CASA account exists and matches
    - `holdAmount > 0`
  - Aggregates removal amounts per CASA account
  - Creates `SIManualHoldRemovalPresentationDetailsEntity`:
    - `manualHoldRemovalReferenceNumber = "NP"+yyyyMMdd+sequence(...)`
    - status `I` + audit fields
  - Saves FAILED staging rows with `reason`
- Tasklet: `SGToTypeTasklet` finalizes overall file type as `APPROVED`.

### `bulkSGToEnachRepresentationJob` (ORC entrypoint) -> create ENACH representation work rows (mandate + presentation linkage)
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request name=`bulkSGToEnachRepresentationJob`)

Processor/tasklet chain:
- `populateUserDetails` (populates `user_id` / `logged_user_employee_formatted_id`)
- `bulkSGToEnachRepresentationJobProcessor` (`BulkSGToEnachRepresentationJobProcessor`)
- Batch wiring for `SGENACHREP` (`SGToEnachRepresentationBatchConfigService`)
  - `PopulateEnachRepresentationStepTasklet`
  - `SGToTypeTasklet`

Key inputs:
- `op_code` (mandatory)
- business date via `current.business.date` -> passed as `business_date_long`
- `upload_type` must exist in execution context for `SGToTypeTasklet`

Persistence/creation:
- Creates `EnachRepresentationDetailsEntity` and `EnachRepresentationLoanAccountDetailsEntity` with status `I`
- Idempotency guard (code-verified): if `enachRepresentationDetailsDAOService.findAllByPresentationDate(presentationDate)` is non-empty, it returns early

How it generates mandates/presentation:
- Validates loan exists and is not CLOSED
- Validates active ENACH mandate exists for the business date and `mandateCategory=="ENACH"`
- Finds failed ENACH presentation loan-account record for the mandate and `emiBounceDate`
- Computes due amount capped by `mandateDetails.maxAmount` and creates representation rows

Success/failure handling:
- Staging rows marked `FAILED` for business validation failures
- Representation entities created as `status="I"` for successes.

### `generateEnachPresentationFile` (ORC entrypoint) -> generate ENACH ACH presentation request file + ACH control file
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request name=`generateEnachPresentationFile`)

Processor/tasklet chain:
- `outboundEnachPresentationBatchProcessor` -> runs batch using job_time and op_code
- Batch wiring for `ENACH-P-O`
  - `PopulateEnachPresentationStepTasklet`
  - `CreateEnachPresentationFileTasklet`
  - `CreateAchPresentationControlFileTasklet` (calls `GenerateAchPresentationFileService.generateACHControlFile`)

Key inputs:
- `job_time` (drives `presentationDate/valueDate`)
- `op_code` (required)

Idempotency:
- `PopulateEnachPresentationStepTasklet`: skips if existing `enachPresentationLADetails` exist for `valueDate`
- `CreateEnachPresentationFileTasklet`: skips if presentation file details already exist for that `valueDate` with fileCategory `PRESENTATION`
- Control file stage: only generates when `!isControlFileGenerated()`

Outputs:
- ENACH request `.txt` file in configured path
- `EnachPresentationFileDetailsEntity` (presentation file and control generation flag)

### `processingEnachPresentationResponseFiles` (ORC entrypoint) -> consume ENACH presentation reverse feed and trigger loanRepayment
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request name=`processingEnachPresentationResponseFiles`)

Processor/tasklet chain:
- `inboundEnachPresentationBatchProcessor`
- Batch wiring: `ConsumeEnachPresentationFileTasklet`

Idempotency (critical):
- processes a mandate reference only when `EnachPresentationDetailsEntity.status == "I"`
- if status != `"I"` it skips (prevents duplicate `loanRepayment` calls)

Success path:
- sets presentation details and loan-account detail statuses to `"S"`
- resets `loanAccount.enachBounceCount` to 0 (when >0)
- calls internal `loanRepayment` API with `repayment_mode="ACH"` and `client_reference_number = mandateReferenceNumber + loanAccountId`

Rejected path:
- sets presentation details/status to `"F"`
- resolves reject reason and applies bounce charges:
  - creates `PresentationBounceChargeDetailsEntity` and `LoanDueDetailsEntity` (fee component)
- increments bounce count via loan update logic

### `generateEnachRepresentationFile` (ORC entrypoint) -> generate ENACH representation request + ACH control file
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request name=`generateEnachRepresentationFile`)

Processor/tasklet chain:
- `outboundEnachRepresentationBatchProcessor` -> runs batch with job_time/op_code
- Batch wiring:
  - `CreateEnachRepresentationFileTasklet`
  - `CreateAchRepresentationControlFileTasklet`

Idempotency:
- skips if representation file details already exist for `presentationDate` with fileCategory `REPRESENTATION`
- control file only generated when `!isControlFileGenerated()`

Outputs:
- representation request `.txt` file
- `EnachPresentationFileDetailsEntity` with fileCategory `REPRESENTATION`

### `processingEnachRepresentationResponseFiles` (ORC entrypoint) -> consume ENACH representation reverse feed and trigger loanRepayment
Source: `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml` (Request name=`processingEnachRepresentationResponseFiles`)

Processor/tasklet chain:
- `inboundEnachRepresentationBatchProcessor`
- Batch wiring: `ConsumeEnachRepresentationFileTasklet`

Idempotency (critical):
- processes only when `EnachRepresentationDetailsEntity.status == "I"`

Success path:
- sets statuses to `"S"`
- resets bounce count (`loanAccount.enachBounceCount = 0`)
- triggers `loanRepayment` internal API (ACH) with `client_reference_number = mandateReferenceNumber + loanAccountId`

Rejected path:
- sets statuses to `"F"` and applies bounce charges by creating bounce fee due entries
- prevents duplicate posting by the `"I"` status gate.

