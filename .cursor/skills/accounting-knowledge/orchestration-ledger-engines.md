<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.md only routes here. -->

## Orchestration-ledger engines (code-verified)

### `postTransaction` (ORC Request) - processor chain + persistence points
Source: `trustt-platform-accounting/deploy/application/orchestration/product_transaction_orc.xml` (Request `name="postTransaction"`).

Processors executed (ordered):
- `validateTransactionDataProcessor` → `in.novopay.accounting.transaction.processor.ValidateTransactionDataProcessor`
  - Validates `run_mode` in `{TRIAL, REAL}`, `function_code == DEFAULT`, `function_sub_code == DEFAULT`, optional `receipt_number` regex, and `amount` parses to non-negative INR-rounded value.
- `populateAdditionalInformationProcessor` → `in.novopay.accounting.transaction.processor.PopulateAdditionalInformationProcessor`
  - Expects `additional_information_details` (array of `{placeholder, value}`); removes it and populates execution-context keys by `placeholder` and `value`.
- `populateAndValidateAccountDetailsProcessor` → `in.novopay.accounting.transaction.processor.PopulateAndValidateAccountDetailsProcessor`
  - Expects `account_details` (array of `{placeholder, account_number, narration}`).
  - Resolves actor accounts via `AccountDAOService.findAccountSummaryForTransaction(accountNumber)` and validates status in `{ACTIVE, CLOSED, APPROVED}`.
  - Resolves internal accounts via `InternalAccountDAOService.getInternalAccountDetailsByCode(accountNumber)`.
  - Writes execution-context keys:
    - `is_child_account` (if not already set and actor account resolution returns it)
    - `<account_placeholder_code>` → account number
    - actor account DTO keyed by account number (execution-context key = `account_number`)
    - internal account entity keyed by internal-account code (execution-context key = `internalAccountEntity.code`).
- `populateAdditionalAmountProcessor` → `in.novopay.accounting.transaction.processor.PopulateAdditionalAmountProcessor`
  - Expects `additional_amount_details` array; removes it and populates `executionContext[reference_code] = amount`.
- `clientReferenceNumberDedupProcessor` → `in.novopay.accounting.transaction.processor.ClientReferenceNumberDedupProcessor`
  - Dedup guard: `TransactionMasterDAOService.findOneByClientCodeAndClientReferenceNumber(client_code, client_reference_number)`; fatal on duplicates.
- `getTransactionCatalogueIdProcessor` → `in.novopay.accounting.transaction.processor.GetTransactionCatalogueIdProcessor`
  - Looks up catalogue by `transaction_type` + `transaction_sub_type`, writes:
    - `transaction_catalogue_id`
    - normalized `transaction_type` and `transaction_sub_type`
    - `transaction_category_list`
- `getTransactionRuleListProcessor` → `in.novopay.accounting.transaction.processor.GetTransactionRuleListProcessor`
  - Loads `transaction_rule_list` by `transaction_catalogue_id`.
- `executeTransactionRulesProcessor` → `in.novopay.accounting.transaction.processor.ExecuteTransactionRulesProcessor`
  - Builds accounting map and transaction partitions using:
    - `PlaceholderMasterDAOService`
    - `ProductTransactionCatalogueDAOService`
    - `InternalAccountDAOService`
    - `InternalAccountDefinitionDAOService`
    - compute engines (`<entryType>Engine`) via `applicationContext.getBean(StringUtils.lowerCase(entryType) + "Engine")`
  - Writes execution-context:
    - `accounting_map` (Map of account -> `AccountingSummaryDTO`)
    - `transaction_partition_details_list` (List of `TransactionPartitionDetailsEntity`)
- `populateLimitRequestProcessor` → `in.novopay.accounting.transaction.processor.PopulateLimitRequestProcessor` (TRIAL branch)
  - Builds `limits_to_validate` from `accounting_map` + `transaction_category_list`.
- `validateActorAccountBalanceProcessor` → `in.novopay.accounting.transaction.processor.ValidateActorAccountBalanceProcessor` (TRIAL branch)
  - Validates limits and updates `AccountBalanceDAOService` rows for actor accounts.
- `createTransactionResponseProcessor` → `in.novopay.accounting.transaction.processor.CreateTransactionResponseProcessor` (TRIAL + REAL)
  - Builds `account_level_transaction_details` and `overall_transaction_details` from `transaction_partition_details_list`, `actor_account_list`, `accounting_map`, and `transaction_rule_dto_list`.
- `validateLimitProcessor` → `in.novopay.accounting.transaction.processor.ValidateLimitProcessor` (TRIAL branch)
  - Calls internal API `validateLimits` using `NovopayInternalAPIClient`.

REAL branch additional persistence processors:
- `generateTransactionReferenceNumberProcessor` → `in.novopay.accounting.transaction.processor.GenerateTransactionReferenceNumberProcessor`
  - Writes `transaction_reference_number = <JulianDay><UUID-no-dashes>`.
- `createTransactionMasterProcessor` → `in.novopay.accounting.transaction.processor.CreateTransactionMasterProcessor`
  - Persists `TransactionMasterEntity` via `TransactionMasterDAOService.save(...)`.
  - Writes execution-context: `transaction_date`, `business_date`, `transaction_master_id`.
- `createTransactionMetadataProcessor` → `in.novopay.accounting.transaction.processor.CreateTransactionMetadataProcessor`
  - Persists `TransactionMetadataEntity` list if `metadata` is present in execution-context.
- `createTransactionPartitionDetailsProcessor` → `in.novopay.accounting.transaction.processor.CreateTransactionPartitionDetailsProcessor`
  - Persists `TransactionPartitionDetailsEntity` list via `TransactionPartitionDetailsDAOService.save(...)`.
  - Writes execution-context: `account_gl_map` (account_number -> glCode).
- `createTransactionDetailsProcessor` → `in.novopay.accounting.transaction.processor.CreateTransactionDetailsProcessor`
  - For each entry in `accounting_map`:
    - if `netAmount > 0` => `cr_dr_indicator = CrDrIndicator.C` and persist `netAmount = abs(netAmount)`
    - if `netAmount < 0` => `cr_dr_indicator = CrDrIndicator.D` and persist `netAmount = abs(netAmount)`
    - if `netAmount == 0` => skip creating a row for that account
  - Sets `glCode` from `account_gl_map` (account_number -> glCode) and sets `child_gl_code` from `is_child_account`.
  - Persists via `TransactionDetailsDAOService.save(...)`.

### `reverseTransaction` (ORC Request) - ledger inversion engine
Source: `trustt-platform-accounting/deploy/application/orchestration/product_transaction_orc.xml` (Request `name="reverseTransaction"`).

Processors:
- `reverseTransactionProcessor` → `in.novopay.accounting.transaction.reverse.processor.ReverseTransactionProcessor`

What `ReverseTransactionProcessor` does (code-verified):
- Reads from execution-context:
  - `transaction_reference_number` OR `client_reference_number` (fatal if neither present).
  - `created_by`, `created_on`, `user_id`, plus master attributes: `operation_mode`, `client_code`, `channel_code`, `end_channel_code`, `stan`, `remarks`.
  - **Posting dates (reversal TM + TD):** `transaction_master.business_date`, `transaction_master.transaction_value_date`, `transaction_details.business_date`, and `transaction_details.value_date` are all set from **`PlatformDateUtil.getBusinessDateInLong()`** (`current.business.date` config). Execution-context `value_date` (string millis) is **not** used for those columns (avoids system-timestamp drift vs trial balance / date-keyed jobs).
- Loads original master:
  - `TransactionMasterDAOService.findOneByTransactionReferenceNumber(...)` or `findOneByClientReferenceNumber(...)`.
  - Fatal if original not found or already reversed (`originalTransactionMasterEntity.getReversed() == true`).
- MFT bank-leg reversal (code-verified):
  - Attempts to locate the original `client_request_response_log` row by matching the original `TransactionMasterEntity` `clientReferenceNumber` (first) or `referenceNumber` (fallback), and searching partner=`Hdfc` first then `HDFC`.
  - If a matching log is found and its stored `request` JSON contains the `miscFundTransfer` structure, constructs a `reversalMiscFundTransfer` bank request:
  - `orgReferenceNo` = original `miscFundTransfer.sessionContext.externalReferenceNo`
  - `sessionContext.externalReferenceNo` = deterministic new reversal ref using prefix `05` (based on `loanAccountNumber` + reversal transaction type + counter), so it is stable across retries
    - Swaps `fromAccount*`/`toAccount*` to reverse the leg direction.
    - Uses original `customerId`, `flagForceDebit`, `txnId`, `transactionAmount`, and original `creditNarrative`/`debitNarrative` for `revCreditNarrative`/`revDebitNarrative`.
  - Calls `CustomerServicePartnerDiscoveryService.reversalMiscFundTransfer(...)` (HDFC OBP integration).
  - Saves the bank attempt into `client_request_response_log` with `transactionType = "REVERSAL_MISC_FUND_TRANSFER"`.
  - If bank response `errorCode` != `"0"`, throws `NovopayFatalException("MFI-40001", ...)` to fail the whole `reverseTransaction` request (GL reversal rolls back).
  - If the original `miscFundTransfer` bank log is missing (or the request JSON is not `miscFundTransfer`), throws the same fatal (`MFI-40001`) so GL reversal does not happen.
- Creates a new `TransactionMasterEntity` via `createTransactionMasterEntry(...)`:
  - Sets `businessDate` and `valueDate` on the new master to the same configured business date (see above).
  - New reference numbers prefixed with `R_`:
    - `referenceNumber = "R_" + original.referenceNumber`
    - `clientReferenceNumber = "R_" + original.clientReferenceNumber`
  - Flags:
    - new master: `reversed=false`, `reversal=true`
    - original master: `reversed=true`, `reversalReferenceNumber=<new.referenceNumber>`
- Ledger lines reversal:
  - Fetches original `TransactionPartitionDetailsEntity` by original `transactionId` and reverses debit/credit:
    - swaps `CrDrIndicator` (`C` <-> `D`)
    - preserves the rest of partition fields (GL codes, entity references, narration, reference codes).
  - Fetches original `TransactionDetailsEntity` by original `transactionId` and reverses debit/credit similarly.
  - Persists via:
    - `transactionMasterDAOService.save(...)`
    - `transactionPartitionDetailsDAOService.save(...)`
    - `transactionDetailsDAOService.save(...)`
- Writes execution-context:
  - `reversal_reference_number`
  - `reversal_client_reference_number`
  - `reference_number` (original reference number)

### Ledger-impacting ORC call-sites: `postTransaction` (13 requests)
These 13 ORC requests include a nested `API id="postTransaction"` call in `deploy/application/orchestration/*.xml` (accounting-v2). FieldNames below are the explicit `IParam` keys passed in the nested API call blocks (not an exhaustive list of all execution-context keys required by the `postTransaction` request itself):

| ORC Request name | postTransaction API explicit `IParam` fieldNames |
|---|---|
| `childLoanAccountExcessAmountRefund` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `office_id`, `transaction_type`, `transaction_sub_type`, `amount`, `currency` |
| `childLoanDisbursementCancellation` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `transaction_type`, `transaction_sub_type`, `value_date`, `client_reference_number`, `amount`, `currency` |
| `childLoanDisbursementCancellationParentRescheduling` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `transaction_type`, `transaction_sub_type`, `value_date`, `client_reference_number`, `amount`, `currency` |
| `childLoanRebookingAdjustmentTransaction` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `office_id`, `transaction_type`, `transaction_sub_type`, `amount`, `currency`, `client_reference_number` |
| `childLoanRepayment` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `office_id`, `transaction_type`, `transaction_sub_type`, `value_date`, `client_reference_number`, `amount`, `currency` |
| `disburseLoan` | `logged_user_office_id`, `function_code`, `function_sub_code`, `expected_disbursement_date`, `loan_amount`, `currency_code` (code-verified: `originating_office_id`, `currency`, `amount`, and `value_date` are mapped directly in the nested `postTransaction` call; `transaction_type`/`transaction_sub_type` are set earlier based on `disbursement_mode`). |
| `individualChildLoanForeclosure` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `transaction_type`, `transaction_sub_type`, `value_date`, `client_reference_number`, `amount`, `currency`, `created_by`, `approved_on`, `approved_by` |
| `loanAccountExcessAmountRefund` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `office_id`, `transaction_type`, `transaction_sub_type`, `amount`, `currency` |
| `loanAccountRebooking` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `office_id`, `transaction_type`, `transaction_sub_type`, `amount`, `currency` |
| `loanDisbursementCancellation` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `transaction_type`, `transaction_sub_type`, `value_date`, `client_reference_number`, `amount`, `currency` |
| `loanPrepayment` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `transaction_type`, `transaction_sub_type`, `value_date`, `client_reference_number`, `amount`, `currency`, `created_by`, `approved_on`, `approved_by` |
| `loanRepayment` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `office_id`, `transaction_type`, `transaction_sub_type`, `value_date`, `client_reference_number`, `amount`, `currency` |
| `loanWriteoff` | `run_mode`, `function_code`, `function_sub_code`, `originating_office_id`, `transaction_type`, `transaction_sub_type`, `amount`, `client_reference_number`, `currency` |

### Ledger-impacting ORC call-sites: `reverseTransactionProcessor` (6 requests)
These 6 ORC requests include an explicit processor node `Processor bean="reverseTransactionProcessor"` in `deploy/application/orchestration/*.xml` (accounting-v2). FieldNames below are explicit `IParam`/`OParam` keys on that processor node.

| ORC Request name | reverseTransactionProcessor explicit IParam | reverseTransactionProcessor explicit OParam |
|---|---|---|
| `reverseTransaction` | (none in ORC; execution-context inputs must come from API/ExecutionContext population) | (none) |
| `reverseManualJournalEntry` | `created_by` (only in `function_code=APPROVE` branch) | (none) |
| `loanAccountTransactionReversal` | `transaction_reference_number`, `created_by`, `created_on`, `value_date` | `reversal_reference_number`, `reversal_client_reference_number` |
| `childLoanTransactionReversal` | `created_by`, `created_on` | `reversal_reference_number`, `reversal_client_reference_number` (code-verified: `value_date` may be prepared earlier by `ConvertTransactionValueDateProcessor` for other steps; **`ReverseTransactionProcessor` persists TM/TD business_date and value_date from `current.business.date`, not from EC `value_date`**). |
| `loanAccountReopening` | `value_date`, `created_by`, `created_on` | (none) |
| `childLoanReopening` | `value_date` | (none) (code-verified: `created_by` and `created_on` are not passed on this node; `ReverseTransactionProcessor` falls back to `user_id` (for `created_by`) and system current date (for `created_on`) when those EC keys are absent). |

### Kafka entrypoint: `LmsMessageBrokerConsumer` → ORC request name
Source: `trustt-platform-accounting/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`.

Code-verified mapping:
- Kafka message `consumerRec.value()` format comment: `apiName|requestBody|cacheKey`.
- Extracts:
  - `api` = substring before first `|`
  - `requestBody` = substring between first `|` and last `|`
- Sets tenant in thread-local context: `ThreadLocalContext.setTenant(tenant)` (done before processing records).
- Populates `requestMap` with `tenant_code = tenant.getTenantCode()`, then populates `ExecutionContext` via `DefaultExecutionContextPopulator.populateExecutionContext(api, "v1", requestMap, requestBody)`.
- Resolves ORC request definition via `OrchestrationXMLParser.getRequestFromOrcXML(tenant_code, api)`:
  - ORC request map key is `tenantCode + "_" + requestName`
  - If tenant-specific request is missing, it falls back by `novopay.orchestration.precedence.order` and retries lookup with other tenant prefixes.
    - Iterates `orchestrationTenantsInOrderOfPrecedence` (config property `novopay.orchestration.precedence.order`, default `product`) and tries `${fallbackTenant}_${requestName}` until found.
    - Throws `NovopayFatalException("13014")` if no ORC request is found.
- Pre-orchestration skip (`getDisburseSkipReason`): if loan is `ACTIVE` and `disbursement_status=COMPLETED`, normally skips to avoid double disbursement. **Exception:** processing continues when the Kafka `requestBody` JSON has `headers.function_sub_code=REINITIATE_BANK` **and** `request.payment_reinitiation_update` truthy (`true`, case-insensitive). LOS must send that flag on the Kafka payload; JTF maps `payment_reinitiation_update` via `disburseLoan_requestTemplate.json` (mfi + product) for HTTP parity.

