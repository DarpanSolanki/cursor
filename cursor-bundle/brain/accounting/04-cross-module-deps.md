# 04 · Accounting — Cross-module dependencies

Listing what accounting **calls outward** and what **calls into accounting**, by exact `<API id>` from the orchestration XMLs.

## What accounting calls outward (sync, via internal API client)

Distilled from a `grep` over all 9 orchestration XMLs (~340 Requests, ~70 unique outbound API ids — many are the same downstream API used in different Requests, so the table below groups by downstream service).

### → `novopay-platform-actor` (user / office / customer / role / use-case)

| `<API id>` (sample) | Downstream API |
|---------------------|----------------|
| `accounting_getUserDetails` | `getUserDetails` |
| `accounting_getOfficeDetails` | `getOfficeDetails` |
| `accounting_getCustomerDetails` | `getCustomerDetails` |
| `accounting_getUseCaseDetails` | `getUseCaseDetails` |
| `createOrUpdateLoanAccount_createActorAccountDetails` | `createActorAccountDetails` |
| `createOrUpdateLoanAccount_getOfficeDetails` | `getOfficeDetails` |
| `loanDisbursementCancellation_getOfficeDetails` | `getOfficeDetails` |
| `loanDisbursementCancellation_getRoleDetailsByUserId` | `getRoleDetailsByUserId` |
| `disburseLoan_getLoanAccountDetails` | `getLoanAccountDetails` (self/loan-side) |

Use-cases referenced as literals (a representative slice): `GENL-LEDG-UC001`, `GENL-LEDG-UC004`, plus IAD/TAX/INT/AIM/ACM/PRD/SCH/HOL use-case codes per master.

### → `novopay-platform-approval` (maker-checker)

| `<API id>` (per Request) | Downstream API |
|--------------------------|----------------|
| `accounting_submitApplication` | `submitApplication` |
| `createOrUpdateAccountingRules_submitApplication` | `submitApplication` |
| `createOrUpdateAssetClassificationMaster_submitApplication` | `submitApplication` |
| `createOrUpdateAssetCriteriaMaster_submitApplication` | `submitApplication` |
| `createOrUpdateHoliday_submitApplication` | `submitApplication` |
| `createOrUpdateInsuranceProduct_submitApplication` | `submitApplication` |
| `createOrUpdateInterestSetup_submitApplication` | `submitApplication` |
| `createOrUpdateLoanProduct_submitApplication` | `submitApplication` |
| `createOrUpdateOffice_submitApplication` | `submitApplication` |
| `createOrUpdatePlaceholderMaster_submitApplication` | `submitApplication` |
| `createOrUpdatePlaceholderMasterListForProductType_submitApplication` | `submitApplication` |
| `createOrUpdatePremiumCalculationMatrixDetails_submitApplication` | `submitApplication` |
| `createOrUpdatePriceMaster_submitApplication` | `submitApplication` |
| `createOrUpdatePriceSetup_submitApplication` | `submitApplication` |
| `createOrUpdateSavingsProduct_submitApplication` | `submitApplication` |
| `createOrUpdateStampDutyMaster_submitApplication` | `submitApplication` |
| `createOrUpdateTaxComponent_submitApplication` | `submitApplication` |
| `createOrUpdateTaxGroup_submitApplication` | `submitApplication` |
| `createOrUpdateTransactionCatalogue_submitApplication` | `submitApplication` |
| `disburseLoan_submitApplication` | `submitApplication` |
| `loanRepayment_submitApplication` | `submitApplication` |
| `loanWriteoff_submitApplication` | `submitApplication` |
| `deleteAccountingRules_submitApplication` | `submitApplication` |
| `deleteHoliday_submitApplication` | `submitApplication` |
| `deleteInterestSetup_submitApplication` | `submitApplication` |
| `deletePlaceholderMaster_submitApplication` | `submitApplication` |
| `deletePriceMaster_submitApplication` | `submitApplication` |
| `deletePriceSetup_submitApplication` | `submitApplication` |
| `deleteStampDutyMaster_submitApplication` | `submitApplication` |
| `deleteTransactionCatalogue_submitApplication` | `submitApplication` |

Pattern: every `createOrUpdate*` and `delete*` master, plus the financial actions `disburseLoan`, `loanRepayment`, `loanWriteoff`, has its own `<API id="…_submitApplication">` so the audit trail uniquely identifies which Request initiated the maker-checker draft.

### → `novopay-platform-task` (BPMN / human task)

| `<API id>` | Downstream API |
|------------|----------------|
| `loanForeclosure_deleteTask` | `deleteTask` |
| `loanPrepayment_deleteTask` | `deleteTask` |
| `loanWaiver_deleteTask` | `deleteTask` |
| `loanAccountReopening_createOrUpdateTask` / `…_deleteTask` | `createOrUpdateTask` / `deleteTask` |
| `LoanAccountRestructuring_deleteTask` | `deleteTask` |
| `loanAccountTransactionReversal_createOrUpdateTask` | `createOrUpdateTask` |
| `loanAccountPartPrepayment_createOrUpdateTask` / `…_deleteTask` | both |
| `loanAccountExcessAmountRefund_createOrUpdateTask` / `…_deleteTask` | both |
| `groupLoanAccountRebooking_createOrUpdateTask` / `…_deleteTask` | both |
| `individualLoanAccountRebooking_createOrUpdateTask` / `…_deleteTask` | both |

Pattern: any servicing flow that has a maker-checker step or operator approval registers (and later clears) a Task.

### → `novopay-platform-notifications`

| `<API id>` | Downstream API |
|------------|----------------|
| `accounting_getNotificationMessage` | `getNotificationMessageByNotificationCode` |

Used at the end of nearly every interactive Request to fetch the user-facing message tied to `user_story_code` (`GENL-LEDG`, `INTL-ACCT-DEFN`, `INT-SET`, `LON-PRD`, `LON-ACT`, `HOL`, etc.) and the response code.

### → `novopay-platform-dms`

| `<API id>` | Downstream API |
|------------|----------------|
| `employee_verifyDocuments` | `verifyDocuments` |

Used during loan-account creation / disbursement to confirm the supporting documents have been verified (KYC, agreement, NACH mandate).

### → `novopay-platform-masterdata-management`

Not via `<API id>` — accessed declaratively through the `<Validator bean="masterDataValidator">` in every CRUD. Master types observed:

`CURRENCY/ISO_CODES`, `GL_CATEGORY/DEFAULT`, `BAL_TYPE/DEFAULT`, `ALLOWED_TXN_TYPE/DEFAULT`, `GL_STATUS/DEFAULT`, plus the rest of the per-master codes (interest type, asset criteria type, etc.).

The validator goes through the master-data service when it isn't already cached locally.

### → `novopay-platform-audit` (implicit, framework-level)

Every domain `*Processor` declares `<AuditData key="entity_type" value="…"/>` and `<AuditData key="new_data" value="${new_data}"/>`. The framework writes to `audit_log` automatically; accounting does not call audit explicitly via `<API>`.

### → External: bank / NEFT / insurance providers / Finsall

| Channel | Trigger |
|---------|---------|
| Bank NEFT (NEFT bank service) | `disburseLoan` outbound + `accountingBankServiceRetryJob` retries; `doGenericSyncSTPBankNEFNeftCallBack` / `…NEINeftCallBack` for callbacks |
| Insurance HDFC Life / HDFC Ergo / Bajaj Ergo | `outboundDisbursement…InsuranceJob` family, `outboundDeathForeclosureInsuranceJob` |
| Finsall (repayment vendor) | `bulkFileToSGFinsallRepaymentJob` / `bulkSGToFinsallRepaymentJob` |

## What calls into accounting

### ← `novopay-mfi-los` (Kafka)

Topic: `disburse_loan_api_*` (per-tenant). Payload format `disburseLoan|<json body>|disburseLoan{productId}_{externalRefNumber}`.

Consumer: `LmsMessageBrokerConsumer` → orchestration Request `disburseLoan` (in `loans_orc.xml`).

Reply topic: `los_lms_disbursement_sync` — payload `{external_ref_number, status, error_code?, error_message?, tenant_code, timestamp}`. LOS subscribes via its own `ProcessDisbursementCallBackService` (described in the existing `disbursement-end-to-end-flow.md` reference under aitdp-docs).

### ← `novopay-platform-batch`

Sync HTTP via `NovopayInternalAPIClient.callInternalAPI(ctx, jobName, …)` from `DirectJobExecutor` / `DirectGroupJobExecutor`. See `03-batch-dependency.md` for the full job inventory.

### ← `novopay-platform-webapp` / `novopay-sli-andriod` (gateway)

All interactive `createOrUpdate*` / `get*` / `delete*` Requests, plus servicing actions (`loanRepayment`, `loanPrepayment`, `loanForeclosure`, `loanAccountPartPrepayment`, `loanAccountReopening`, etc.).

### ← `novopay-platform-payments` (LCS)

Likely posts to accounting for repayment booking on collection events (the existing Payments docs show the inbound side). Inbound API: `loanRepayment`, `loanRepaymentInquiry`, `postTransaction`. Not enumerated here in detail because it lives outside accounting orchestration.

### ← `novopay-platform-bpmn` (Camunda)

BPMN workflows trigger `loanForeclosure`, `loanWriteoff`, `loanAccountTransactionReversal`, `loanAccountPartPrepayment`, etc. through service tasks that hit the gateway. The accounting side closes the loop by calling `…_deleteTask` on the task service when the workflow completes.

## Dependency diagram

```
                           ┌────────────────────────┐
                           │ master-data-management │
                           └──────────┬─────────────┘
                                      │ masterDataValidator
                                      ▼
       ┌────────┐    ┌────────┐    ┌─────────────────────┐    ┌──────────┐
       │ webapp │───▶│gateway │───▶│ accounting-v2       │◀───│  batch   │
       │ android│    └────────┘    │  • orchestration    │HTTP│ scheduler│
       └────────┘                  │  • batchnew jobs    │    └──────────┘
                                   │  • Kafka consumer   │
                                   └──┬───┬──┬──┬────┬───┘
                                      │   │  │  │    │
                  submitApplication   │   │  │  │    │  Kafka publish
                                      │   │  │  │    └──▶ los_lms_disbursement_sync
                                      ▼   │  │  │           ▲
                              ┌──────────┐│  │  │           │
                              │ approval ││  │  │           │
                              └──────────┘│  │  │           │
                                          ▼  │  │           │
                                   ┌──────────┐ │           │
                                   │   task   │ │           │
                                   └──────────┘ │           │
                                                ▼           │  Kafka publish
                                       ┌────────────┐       │  disburse_loan_api_*
                                       │notifications│      │           ▲
                                       └────────────┘       │           │
                                                            │      ┌─────────┐
                                                            └──────│ LOS     │
                                                                   │ (mfi-los)│
                                                                   └─────────┘
                                                  ┌──────────┐
                                                  │   dms    │
                                                  └──────────┘
                                                  ┌──────────┐
                                                  │  audit   │  (framework auto-write)
                                                  └──────────┘
```

## What accounting does **not** depend on

- `novopay-platform-bre` — not referenced in any accounting orchestration. NPA / asset criteria use the in-service `assetcriteriamaster` slabs, not BRE rules.
- `novopay-platform-consents` — no `<API id>` references.
- `novopay-platform-reporting` — accounting calls it indirectly via `generatePostEODReports` which is itself an accounting Request that pushes a job; the actual rendering lives in `trustt-platform-reporting`.
- `novopay-platform-batch` — there is no inbound dependency; the relationship is `batch → accounting` only.
