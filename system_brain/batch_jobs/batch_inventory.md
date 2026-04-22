# Batch Jobs Inventory (code-verified)

This inventory focuses on the **money-relevant** EOD/BOD/batch jobs we re-validated with direct code reads:
- accounting-v2 ledger-affecting batches (posting/accrual/billing/closure/repayment/trial balance)
- masterdata `updateBusinessDate`
- portfolio transfer scheduled job (actor orchestration)

For each job below:
- **Schedule** = job config `group_code` + `cron_expression` (where found)
- **Mutations** = which accounting tables/entities are written
- **Posting calls** = where the job calls internal `postTransaction` / `loanRepayment`
- **Idempotency** = the actual code guard (reader WHERE clauses, posting-date guards, run-history flags, or “already exists” app logic)

## LMS-EOD-BOD group (daily)

All following jobs are under `group_code = LMS-EOD-BOD` with `cron_expression = 0 0 18 * * ?` (18:00 daily), as read from their config services.

### 1. `updateBusinessDate`
- Config: `novopay-platform-masterdata-management/.../BusinessDateBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed): `configuration` via `ConfigurationEntity` (current.business.date)
- Idempotency / rerun behavior (confirmed):
  - No explicit dedupe guard in job code; reruns re-increment.

### 2. `loanAccountDpdCalcJob`
- Config: `in.novopay.accounting.batchnew.npa.primary.loanaccountdpdcalcjob.LoanAccountDpdCalcBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed): `loan_account` fields like `past_due_days`, `delinq_string`
- Posting calls (confirmed): none (calculation + entity updates only)
- Idempotency / rerun behavior:
  - No explicit dedupe guard found; it deterministically recalculates and overwrites.

### 3. `loanAccountAssetCriteriaJob`
- Config: `in.novopay.accounting.batchnew.npa.primary.loanaccountassetcriteriajob.LoanAccountAssetCriteriaBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Reader selection guard (confirmed):
  - Loans where `loan_status IN ('ACTIVE','FORECLOSURE_FREEZE')`
  - Includes asset-criteria conditions on NPA tagging / past_due_days
  - Skips previously processed business-date windows using `batch_failure_audit bfa ... AND bfa.context_value IS NULL`
- Processor dedupe-by-change (confirmed):
  - If computed `slabId.equals(accountAssetCriteriaSlabId)` -> `return null` (no persistence)
- Writer mutations (confirmed):
  - Saves `loan_account` updates via `loanAccountDAOService.save(...)`
- Posting calls (confirmed):
  - In `LoanAccountAssetCriteriaBatchProcessor#postAccrualEntries(...)`:
    - internal calls: `interestAccrualCalculation` -> `accounting_interestAccrualCalculation`
    - internal calls: `interestAccrualPosting` -> `accounting_interestAccrualPosting`
  - In writer loop: calls internal `postTransaction` via processor `postTransaction(...)` when applicable
- Idempotency / rerun behavior:
  - Change-based skip (slabId equality) prevents duplicate loan_account field mutations.
  - Posting safety is expected to rely on `interestAccrualPosting` + `postTransaction` guards, not on a job-level dedupe.

### 4. `loanAccountAssetClassificationJob`
- Config: `in.novopay.accounting.batchnew.npa.primary.loanaccountassetclassificationjob.LoanAccountAssetClassificationBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed): `loan_account` fields `assetClassificationSlabsId`, `npaAgeingDays`
- Posting calls (confirmed): none in classification path
- Processor dedupe-by-change (confirmed):
  - If computed slab/day values don’t differ from existing -> returns `null` -> writer won’t save

### 5. `interestAccrualCalculation`
- Config: `in.novopay.accounting.batchnew.interest.interestaccrualcalculation.InterestAccrualCalculationBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed): `interest_accrual_details` via `InterestAccrualDetailsDaoService.save(...)`
- Reader idempotency guard (confirmed):
  - Reader SQL uses `batch_failure_audit` join and requires `bfa.context_value IS NULL` for the relevant business_date window
  - (So “previous failure contexts” suppress reprocessing)
- Service range guards (confirmed):
  - skip if `isStopAccraul`
  - skip if `accrualStartDateCal >= now`
  - in-loop skip when `accrualStartDateCal >= accrualEndDate`
- Idempotency / rerun behavior:
  - Effectively create-or-update: updates existing accrual segments rather than blindly inserting.

### 6. `interestAccrualPosting`
- Config: `in.novopay.accounting.batchnew.interest.interestaccrualbooking.InterestAccrualBookingBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed): `interest_accrual_details` (writer persists updated posted totals and posting dates)
- Reader idempotency guard (confirmed):
  - Reader SQL again uses `batch_failure_audit` + `bfa.context_value IS NULL`
  - restricts loans to `ACTIVE` or `FORECLOSURE_FREEZE`
- Posting idempotency guards (confirmed):
  - skip if `totalAccruedAmount == totalAccrualPostedAmount`
  - only post on posting-eligible dates:
    - last day of month OR there exists a due for the due_date boundary
  - booking delta guard: skip if computed `bookingAmount <= 0` (and also skips negative/invalid deltas)
- Posting call-site (confirmed):
  - calls internal `postTransaction` from `InterestAccrualBookingBatchService#doInterestBooking(...)`
  - also may call NPA posting via an additional internal posting call inside same service
- `client_reference_number` generation (confirmed):
  - it uses `accountId + "" + new Date().getTime()` (not deterministic)

### 7. `penalInterestAccrualCalculation`
- Config: `in.novopay.accounting.batchnew.penal.penalaccrualcalculation.PenalInterestAccrualCalculationBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed):
  - saves penal accrual details
  - updates installment detail data as part of calculation
- Idempotency / rerun behavior (confirmed):
  - decides create-new vs update-last entity via `isCreateNewPenalInterestAccrualDetails(...)`
  - updates last entity endDate/amount when it’s not a create-new boundary

### 8. `penalInterestAccrualBooking`
- Config: `in.novopay.accounting.batchnew.penal.penalaccrualbooking.PenalInterestAccrualBookingBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed):
  - creates `loan_due_details` entries
  - sets `penal_interest_accrual_details.accrualPostingDate` (booking marker)
  - books child loans via `ChildLoanPenalInterestBookingService#bookChildLoans(...)` (updates child installment + due details)
- Strong booking idempotency (confirmed):
  - Reader selects rows where `accrual_posting_date is null`
  - writer sets `accrualPostingDate` so reruns naturally skip

### 9. `loanAccountBillingJob`
- Config: `in.novopay.accounting.batchnew.loanaccountbilling.LoanAccountBillingBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed): `loan_account_billing_details`
- Posting call-site (confirmed):
  - writer/service calls internal billing posting via:
    - `apiClient.callInternalAPI(exec, "postTransaction", "v1", "billing_postTransaction", ...)`
- Application-level dedupe (confirmed):
  - `createBillingEntry(...)` checks `loanAccountBillingDetailsDaoService.findByLoanInstallmentDetailsId(...)`
  - if already exists -> returns `null` -> no duplicate billing row + no duplicate billing posting
- Framework-level reruns:
  - Spring Batch uses `RunIdIncrementer` so each start is a new job instance; correctness relies on the app-level “already exists” checks.

### 10. `loanAdvanceRepayment`
- Config: `in.novopay.accounting.batchnew.loanadvancerepayment.LoanAdvanceRepaymentBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed via reversal path):
  - repayment posting + reversal writes in:
    - `transaction_master`, `transaction_details`, `transaction_partition_details`
    - and reversal bookkeeping in `transaction_reversal_details`
- Posting call-site (confirmed):
  - writer calls internal `loanRepayment` API
  - on fatal exception it may call reversal (`ReverseTransactionProcessor`)
- Idempotency / rerun guard (confirmed):
  - skip processing when there is a pending reversal in `transaction_reversal_details` (`status=PENDING`)
  - reversal processor further prevents double reversal using original transaction’s `reversed` flag.

### 11. `loanAccountClosure`
- Config: `in.novopay.accounting.batchnew.loanaccountclosure.LoanAccountAutoClosureBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed):
  - `loan_account` transitions to `LoanStatus.CLOSED` and `AccountStatus.CLOSED`
  - `loan_account_closure_details` persisted by writer
- Eligibility / idempotency guards (confirmed):
  - batch reader selects `la.loan_status='ACTIVE'` and uses `batch_failure_audit` window suppression
  - service checks interest accrual + booking up-to-date consistency:
    - interest accrual exists
    - `endDate`/`lastAccrualPostedDate` not null
    - accrued == booked exactly
  - additional tolerance + maturity guards based on product tolerance settings
- Posting calls (confirmed for tolerance path):
  - tolerance path triggers internal accounting posting via internal `postTransaction` calls and/or NPA movement posting.

### 12. `trialBalanceCalculation`
- Config: `in.novopay.accounting.batchnew.trialbalance.config.TrialBalanceBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed):
  - `trial_balance` via `PopulateTrialBalanceBatchTasklet`
  - `trial_balance_run_history` and conditional `opening_balance` via `PopulateOpeningBalanceNextFYBatchTasklet`
- Idempotency / replay-safety (confirmed):
  - processor sets `job_run_flag=false` when:
    - previous FY zeroisation not done
    - TB already calculated beyond/for the target reporting date
  - tasklets early return if `job_run_flag == false`
  - relies on run-history to avoid overlapping ranges.

### 13. `generatePostEODReports`
- Config: `in.novopay.accounting.batchnew.trialbalance.config.GeneratePostEODReportsBatchConfigService`
- Schedule: `LMS-EOD-BOD`, cron `0 0 18 * * ?`
- Mutations (confirmed):
  - no DB mutations in tasklets (file generation)
- Idempotency (confirmed):
  - processor/tasklets guard via `job_run_flag == false` based on TB last calculated date

## Portfolio Transfer scheduled job (Actor)

### `executePortfolioTransfer`
- Source schedule (confirmed from Flyway): `V9000098__create_portfolio_transfer_scheduler.sql`
  - inserts batch schedule cron `0 0 17 * * ?` (daily 17:00)
- Runtime mapping (confirmed):
  - the scheduled batch group executes an Actor orchestration request:
    - `novopay-platform-actor` request `<Request name="executePortfolioTransfer">` with `executePortfolioTransferProcessor`
- Selection criteria (confirmed):
  - request_status in `('APPROVED','INITIATED')`
  - transfer_status in `('YET_TO_START','TRFR_IN_PRGRS','TRFR_FAILED')`
  - also buckets and expires non-eligible approvals before executing eligible ones
- Execution + rollback idempotency (confirmed):
  - uses `portfolio_transfer_execution_history` and `is_rollbacked` marker
  - step history is committed with `REQUIRES_NEW` (`commitExecutionHistoryImmediately`)
  - rollback reads only `is_rollbacked=false` and marks rows rollbacked after each successful rollback step

---

## Other accounting-v2 batch groups (code-verified + clearly marked UNVERIFIED)

### `generateNocFileJob`
- Config class: `in.novopay.accounting.batchnew.bulknoc.dispatch.generatenocfilejob.GenerateNocFileBatchConfigService`
- Schedule (confirmed in config): `group_code = LMS-GEN-NOC`, `cron_expression = 0 0 18 * * ?`
- Mutations / writes (confirmed by writer):
  - `loan_account` fields updated via `loanAccountDAOService.saveAll(...)`
  - NOC details via `loanAccountNocDetailsDAOService.saveList(...)`
  - Processor triggers document generation by calling internal APIs (document download/generation) from:
    - `GenerateNocFileItemProcessor` (calls internal API `downloadDocument`)
- Posting calls: not found in writer paths (no direct `postTransaction` confirmed).

### `accountingBankServiceRetryJob`
- Config class: `in.novopay.accounting.batchnew.bankservicecallretry.AccountingBankServiceRetryJobBatchConfigService`
- Schedule (confirmed): `group_code = BANK-RETRY-MECH`, `cron_expression = 0 20 * * * ?`
- Mutations (confirmed by writer):
  - updates `client_request_response_log` via `clientRequestResponseLogDAOService.saveAll(...)`
- Posting calls: UNVERIFIED (depends on what endpoint the retry job pulls from DB).

### Insurance-related disbursement cancellation / policy updates

#### `bulkSGToDisbursementCancellationJob`
- Config class: `in.novopay.accounting.batch.disbursmentcancellation.config.SGToDisbursementCancellationBatchConfigService`
- Schedule (confirmed): `group_code = INSURANCE_DISB_CNCL`, `cron_expression = 0 0 18 * * ?`
- Writer (confirmed):
  - `SGToDisbursementCancellationIWriter.write(...)` persists:
    - `disbursement_cancellation` insurance staging details
    - loan disbursement cancellation details
    - updates insurance status in `loan_account_insurance_details`
  - `SGToDisbursementCancellationIWriter.doDisbursementCancellation(...)` includes posting:
    - internal `postTransaction` call (`postTransaction`)
    - `createLoanAccountPaymentsDetailsProcessor.execute(...)`
    - updates statuses via `updateLoanAccountStatusProcessor.execute(...)`
    - tax reversal + child-flow rescheduling via:
      - `initiateCancellationTaxReversalProcessor.execute(...)`
      - `callInternalOrchestrationWithoutJsonProcessor.execute(...)`

#### `bulkSGToPostDisbursementInsuranceUpdateJob`
- Config class: `in.novopay.accounting.batch.disbursement.config.SGToPostDisbursementInsuranceUpdateBatchConfigService`
- Schedule (confirmed): `group_code = INSURANCE_POST_DISB`, `cron_expression = 0 0 18 * * ?`
- Mutations (confirmed):
  - saves staging rows via `fileStagingPostDisbursementInsuranceDAOService.saveAll(...)`
  - updates insurance details via `loanAccountInsuranceDetailsDAOService.saveList(...)`
  - creates output files via `PostDisbursementFileCreationTasklet.execute(...)`
- Posting calls: not confirmed as `postTransaction` in the discovered writer/tasklet path.

### Death foreclosure insurance jobs

#### `deathForeclosureInsuranceJob`
- Config class (confirmed): `DeathForeclosureInsuranceConfigService`
- Schedule (confirmed): `cron_expression = 0 0 6 * * ?` (6:00 daily)
- Writer (confirmed): `DeathForeclosureInsuranceWriter`
- Posting calls + accounting mutations (confirmed within writer):
  - `DeathForeclosureInsuranceWriter.calculateAmountsForTransaction(...)`
    - calls internal `postTransaction`
    - updates due records via `loanDueDetailsDAOService.saveOne(...)`
    - persists death foreclosure details/staging:
      - `deathForeclosureDetailsDAOService.saveOne(...)`
      - `deathForeclosureInsuranceStagingDetailsDAOService.saveOne(...)`
    - creates closure record via `loanAccountClosureDetailsDAOService.saveEntity(...)`
    - updates loan insurance details via `loanAccountInsuranceDetailsDAOService.save(...)`
    - calls `deathForeclosureGLCBSIntegrationProcessor.execute(executionContext)`
  - `DeathForeclosureInsuranceWriter.doParentPartPrePayment(...)`
    - calls internal `postTransaction`
    - uses part-prepayment processors to persist payment detail allocations and update loan entities
- Note: orchestration entrypoint linkage was partially UNVERIFIED from XML mapping in the earlier pass, but writer-level posting is confirmed.

#### `outboundDeathForeclosureInsuranceJob`
- Config class: `OutboundDeathForeclosureInsuranceBatchConfigService`
- Schedule (confirmed): `group_code = INSURANCE_DETH_FRCLS`, `cron_expression = 0 0 6 * * ?`
- Writer: `OutBoundDeathForeclosureDocumentWriter`
- Mutations: primarily document merging/downloading + file upload.
- Posting calls / accounting mutations: UNVERIFIED.

#### `runInboundDeathForeclosureInsuranceJob` and `inboundDeathForeclosureInsuranceJob`
- Config classes exist and are scheduled/triggered as part of `loans_insurance_orc.xml`, but:
  - posting/table-writing behavior: UNVERIFIED in this pass.

### Proactive excess amount refunds (scheduled)

#### `ProactiveExcessAmountRefundStagingJob`
- Config class: `ProactiveExcessAmountRefundStagingConfigService`
- Schedule (confirmed): `group_code = LMS-PRRF`, `cron_expression = 0 0 9 * * ?`
- Mutations (confirmed): staging via `file_staging_proactive_refund` (no direct `postTransaction` confirmed here).
- Idempotency (confirmed):
  - staging reader excludes accounts already present in `file_staging_proactive_refund`
  - reader excludes rows already marked for refund in failure/success by where-clause constraints.

#### `ProactiveExcessAmountRefundJob`
- Config class: `ProactiveExcessAmountRefundConfigService`
- Schedule (confirmed): `group_code = LMS-PRRF`, `cron_expression = 0 0 9 * * ?`
- Posting call (confirmed):
  - writer calls internal `postTransaction` with:
    - `transaction_type = EXCESS_AMT_REFUND`
    - `transaction_sub_type = LOAN_ACCOUNT`
    - `apiIdentifier = accounting_postTransaction`
  - `client_reference_number` is generated as: `"EAR" + loanAccountEntity.getId() + new Date().getTime()` (time-based)
- Batch-level idempotency (confirmed):
  - staging reader selects only rows where:
    - failure flag false, is_deleted false, refund_allowed true
  - on success it sets `is_deleted=true` and stores `transactionReferenceNumber`
- Writer exception behavior (confirmed risk surface):
  - writer catches exceptions and logs debug without guaranteeing staging status update (see edge-case doc).

#### `runInboundReverseExcessAmountRefundJob` / `InboundReverseExcessAmountRefundJobProcessor`
- Config class: `RunInboundReverseExcessAmountRefundConfigService`
- Schedule (confirmed): `group_code = LMS-PRRF`, `cron_expression = 0 0 9 * * ?`
- Behavior (confirmed):
  - uses inbound file upload runner
- Posting calls: no direct `postTransaction` found in discovered inbound processor path.

#### `ProactiveReverseTransaction` (scheduled)
- Config class: `ProactiveReverseTransactionBatchConfigService`
- Schedule (confirmed): `group_code = LMS-PRRF`, `cron_expression = 0 0 9 * * ?`
- Posting call (confirmed):
  - writer calls internal `reverseTransaction` (`accounting_reverseTransaction`)
- Idempotency (confirmed):
  - staging rows set `is_deleted=true` on processing
  - `ReverseTransactionProcessor` throws if original transaction master is already reversed (`originalTransactionMasterEntity.getReversed()==true`)

### Bulk refund marking jobs (file-upload driven; posting not found)
- `BulkFileToSGRefundMarkingJobProcessor`:
  - routes to inbound bulk upload job runner; no `postTransaction` found in shown paths.
- `SGToRefundMarkingBatch`:
  - updates `refund_allowed`/`refund_remarks` flags in `loan_account` based on staging rows;
  - no direct `postTransaction` in found writer path.


