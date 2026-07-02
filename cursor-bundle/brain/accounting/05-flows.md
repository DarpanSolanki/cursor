# 05 · Accounting — Key flows (inside-out)

The five money-state flows below are the ones every newcomer to accounting must internalise. Each section names the entry Request, the orchestration XML, the inner processors, the DB writes, the cross-service calls, and the failure modes.

---

## 1. Disbursement (LOS → accounting via Kafka)

**Entry:** `disburseLoan` (loans_orc.xml, `explicitTxnMgmt="true"`)
**Trigger:** Kafka message on `disburse_loan_api_*` consumed by `LmsMessageBrokerConsumer`. Sync HTTP entry from gateway also exists for manual operator paths.

```
LOS PrepareDisburseLoanAPIRequestService
   └─▶ DisburseLoanAPIUtil pushes  apiName|body|disburseLoan{productId}_{externalRefNumber}
            │                       └── topic: disburse_loan_api_<tenant>
            ▼
ACC LmsMessageBrokerConsumer.processConsumerRecord
   ├─▶ getDisburseSkipReason(externalRefNumber, productId, cacheKey, tenant)
   │      ├── ALREADY_ACTIVE   → publish SUCCESS, return
   │      ├── LOCK_LOAN_STATUS → silent return
   │      └── LOCK_CACHE_IN_PROGRESS → silent return
   ├─▶ novopayCacheClient.set("dl"+cacheKey, "true")     ← Redis ACCOUNTING db
   └─▶ executeServiceOrchestration → ServiceOrchestrator.executeProcessors(disburseLoan)
            ├── verifyDocuments (DMS)
            ├── disburseLoan_getLoanAccountDetails (self)
            ├── disburseLoan_submitApplication if maker_checker_enabled=1 (approval)
            ├── domain processors:
            │     • createOrUpdateLoanAccount (insert/update loan_account)
            │     • assign LAN (Loan Account Number)
            │     • generateRepaymentSchedule
            │     • outboundDisbursement<provider>InsuranceJob if applicable
            │     • bank NEFT call (or queue STP-bank retry)
            ├── postTransaction → GL hit (DR: bank, CR: loan_account)
            └── audit + notification
   finally:
      sendResultMessageToKafka(externRefNumber, isSuccess, exception)
            → topic: los_lms_disbursement_sync
      cleanupCacheKeys
```

**DB writes**
- `loan_account` (status=ACTIVE on success)
- `loan_installment_details`, `loan_due_details`, `interest_accrual_details`
- `account`, `account_balance`
- `general_ledger` / posting via `transaction` tables
- `audit_log`

**Failure modes & retries**
- Bank NEFT failure → row enters `bank_service_call_retry` table; `accountingBankServiceRetryJob` re-tries.
- Approval rejection → `disburseLoan` re-fires with `function_code=APPROVE` (success) or `RESUBMIT`.
- Kafka exception → `caughtException` → FAILED message back to LOS with `error_code` resolved via `notificationUtil.getResponseMessage`.
- Existing High-risk gap (per `_archive/changelog.md`): the in-flight `dl*` Redis key has no TTL — a crashed consumer can leave a permanent "in progress" key blocking retries. Mitigation: manual delete or a TTL-cleanup runbook.

---

## 2. Repayment

**Entry:** `loanRepayment` (mfi_orc.xml, `explicitTxnMgmt="true"`) — sync HTTP from webapp/payments.

```
loanRepayment
  ├── accounting_getUserDetails / getUserDetailsPostProcessor
  ├── loanRepayment_getLoanAccountDetails (self)
  ├── checkData…Repayment validators (allocation rules, write-off, foreclosure ineligible)
  ├── if maker_checker_enabled=1:
  │      └── loanRepayment_submitApplication (approval)
  ├── domain processors:
  │      • allocate amount: due interest → due principal → penal → fees → excess
  │      • update loan_due_details, loan_installment_details
  │      • postTransaction (DR: customer/bank, CR: GL revenue + principal-receivable)
  │      • write-off / NPA bucket re-evaluation hooks (deferred to EOD)
  └── audit + notification
```

Inquiry sibling `loanRepaymentInquiry` returns the proposed allocation without committing.

**Special variants**
- `loanAdvanceRepayment` — applies stored advance pool to next due (batch path).
- `loanAccountPartPrepayment` — partial principal prepayment with optional reschedule (`fetchPartPrepaymentRepaymentSchedule` shows preview, `loanAccountPartPrepayment` commits).
- `loanPrepayment` (full) → triggers `loanAccountClosure` chain.
- `childLoanRepayment` — for JLG/SHG group child accounts (group_mfi_orc.xml).

---

## 3. Interest accrual (EOD batch)

**Entries:** `interestAccrualCalculation` then `interestAccrualPosting` (loans_orc.xml). Fired by `runEODJobs` aggregator scheduled by batch service.

### Calculation (`batchnew/interest/interestaccrualcalculation`)

- `InterestAccrualCalculationItemReader` — pulls active loan accounts due for accrual today.
- `InterestAccrualCalculationItemProcessor` → `InterestAccrualCalService`:
  - looks up `interest_setup` slabs + base-interest-rate effective on accrual date
  - picks calculator: `LoanAmountInterestAmountCalculator` (flat) or `ReducingBalanceInterestAmountCalculator`
  - applies `InterestCalculationUtil` (day-count, compounding) and `RepaymentScheduleUtil`
  - subtracts part-prepayment effects (`LoanAccountPartPrepaymentDetailsEntity`)
- `InterestAccrualCalculationItemWriter` — UPSERT into `interest_accrual_details`.

### Posting / Booking (`batchnew/interest/interestaccrualbooking`)

- Reads accrued rows pending posting
- Calls `postTransaction` per row → GL hits (DR: interest receivable, CR: interest income)
- Marks row posted

**Idempotency:** rows are keyed on `(loan_account_id, accrual_date)`; re-running does not double-book because the writer upserts and the booker checks a `posted` flag.

---

## 4. EOD / BOD pipeline

**Entries:** `runBODJobs` then `runEODJobs` (mfi_orc.xml). Wrapped by batch service schedules.

```
runBODJobs (typically 04:00 IST)
  ├── server clock advance (clock package)
  ├── holiday roll-forward (holiday package)
  ├── eNACH presentation file generation (generateEnachPresentationFile)
  ├── expirePendingMandatesBatchJob
  └── reset day-level counters

runEODJobs (typically 21:00 IST)
  ├── loanAccountBillingJob               (generate today's due records)
  ├── interestAccrualCalculation          (compute today's accrual)
  ├── interestAccrualPosting              (post to GL)
  ├── penalInterestAccrualCalculation     (DPD × penal slabs)
  ├── penalInterestAccrualBooking
  ├── loanAccountDpdCalcJob               (refresh DPD)
  ├── loanAccountAssetCriteriaJob         (apply criteria slabs)
  ├── loanAccountAssetClassificationJob   (promote NPA buckets)
  ├── updateLoanAccountDerivedFieldsJob   (denormalised columns for reporting)
  ├── trialBalanceCalculation
  ├── trialBalanceZeroisationJob          (move closing balances to next day)
  ├── generateTBZeroisationReport
  ├── extractCasaBalanceFor180ProductCode + 182
  └── generatePostEODReports              (kicks reporting service)
```

Each step is a separate `BatchJob` so it can be re-run individually if it fails. The `runEODJobs` Request is itself an orchestration that dispatches these as ordered internal API calls; the batch scheduler triggers `runEODJobs`, which in turn calls the per-step Requests.

---

## 5. NPA / asset classification

**Daily** (inside `runEODJobs`):
1. `loanAccountDpdCalcJob` recomputes `dpd_count` per loan account.
2. `loanAccountAssetCriteriaJob` walks `asset_criteria_master` slabs (e.g., DPD 1–30 → SMA-0, 31–60 → SMA-1, 91+ → NPA-Substandard) and writes `asset_criteria_group`.
3. `loanAccountAssetClassificationJob` finalises `asset_classification` per loan and writes the dated record for reporting.

**Periodic / vendor-fed**
- `bulkSGToSecNpaReverseFeedFileJob` ingests RBI/SCB secondary-NPA reverse-feed files; `bulkOutboundSecNpaReverseFeedFileJob` produces the outbound submission.
- `bulkFileToSGAssetCriteriaGroupUpdateJob` allows ops to override classification via uploaded CSV.

NPA outcomes feed:
- Provisioning (`loanProvisioningPosting`)
- Penal interest computation (penal slabs differ by NPA bucket)
- Reporting (`generatePostEODReports`)

---

## Quick lookup: which file owns what?

| You need to find… | Look in |
|--------------------|---------|
| The Request → processor chain | `deploy/application/orchestration/<xml>` |
| The actual SQL the job runs | `batchnew/<domain>/*ItemReader.java` + `*Repository`/`*DAOService.java` |
| Why a value is what it is | `*Service.java` (e.g. `InterestAccrualCalService`) — pure business logic |
| Failure rows | `*FailureEntityMapper.java` → `batch_failure_audit` table |
| Why the consumer skipped a message | `LmsMessageBrokerConsumer.getDisburseSkipReason` |
| GL impact of any transaction | `accountingrules` master + `transactioncatalogue` + `placeholdermaster` |
| What master-data values are valid | `<Validator bean="masterDataValidator">` in the Request, or `masterdata-management` service |
| Approval flow data | the corresponding `…_submitApplication` `<API id>` and the `audit_log` for `entity_type=SEND_FOR_APPROVAL_*` |
