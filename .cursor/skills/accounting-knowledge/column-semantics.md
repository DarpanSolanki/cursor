<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.md only routes here. -->

## Key entities and column semantics

### loan_due_details (LoanDueDetailsEntity)
- **due_amount**: total amount due for this component in this installment
- **paid_amount**: cumulative actual payments received (persisted, updated after each repayment)
- **waived_amount**: cumulative amount waived/written off (loss bucket, NOT actual payment)
- **current_paid_amount**: TRANSIENT — amount paid in the current transaction only; NOT persisted
- **component_type**: PRIN, INT, PINT (penal), FEE
- **Outstanding = due_amount - paid_amount - waived_amount**
- **CRITICAL**: paid_amount ≠ waived_amount. paid = actual money received. waived = forgiven/loss. Never mix them when computing "extra interest paid" or similar.

### Who writes paid_amount
- RepaymentApproppriationProcessor → sets currentPaidAmount → CreateRepaymentInstallmentDetailsProcessor adds to paidAmount
- UpdateLoanDueDetailsProcessor (repayment, DCF)
- DeathForeclosureInsuranceWriter (BPI paid)

### Who writes waived_amount
- UpdateLoanDueDetailsForWaiverProcessor
- UpdateDueDetailsForPrepaymentProcessor (foreclosure waivers)
- DeathForeclosureInsuranceWriter (interest/penal/fee waivers)

### loan_account (LoanAccountEntity)
- **loan_status**: APPROVED, ACTIVE, DEATH_FORECLOSURE_FREEZE, FORECLOSURE_FREEZE, CLOSED, etc.
- **excess_amount**: money overpaid by customer sitting in loan account
- **loan_amount**: total loan (may include insurance premium)
- **approved_amount**: sanctioned amount (use this for net disbursement calcs, NOT loan_amount)
- **disbursement_status**: BANK_SUCCESS, COMPLETED, NEFT stages, etc.

### Group / individual child loan — bank `externalReferenceNo` vs `client_request_response_log`
- **Dedupe / lookup**: `CallBankAPIForIndividualChildLoanDisbursementProcessor` + `ChildDisbursementBankCallService` (`loan.disbursement.bank.child`) keep **`client_request_response_log.loan_account_number` = parent loan account number** (same key as verified parent dedupe), with **child-scoped `transaction_type`** (suffix includes child id, e.g. `…_EXTREF<childExternalRef>_MFT` / `_NEFT_NEF` / `_NEFT_NEI`).
- **Generated bank reference string**: `ExternalReferenceNoUtil.computeDeterministicExternalReferenceNo(..., clientReferenceBaseOverride)` uses **`clientReferenceBaseOverride = parentLAN + child_seq_no`** for child disbursement bank calls (`CreateClmtLoanAccountEventsProcessor` sets `child_seq_no` as 1..N and `ChildLoanMoneyTransferEventsQueueDataPopulator` carries it in queue payload). `CallBankAPIForIndividualChildLoanDisbursementProcessor` now treats `child_seq_no` as mandatory and fails fast (`MFI-40001`) if missing, to avoid long `externalReferenceNo` fallback paths. Lookup stays parent LAN + child-scoped `transaction_type`.
- **GL CBS disbursement NET-OFF external key**: `DisbGLCBSIntegrationProcessor` uses leg prefix `01` + `DISB_GL_CBS_INTEGRATION` for the main leg and `04` + `DISB_GL_CBS_INTEGRATION_NETOFF` for NET-OFF so full `client_reference_number` never collides with the main leg while counters stay per-type (standard `ExternalReferenceNoUtil` FAIL/SUCCESS retry). `GLCBSIntegrationService` dedupe remains by `loan_account_number` + `transaction_type` + SUCCESS for both disbursement types.
- **Child money-transfer queue payload** (`ChildLoanMoneyTransferEventsQueueDataPopulator`): `ACCOUNT_NUMBER` in the JSON is the **parent** LAN from the batch execution context (not a resolved child LAN).
- **`client_request_response_log.status = UNKNOWN` (MFT/NEFT disbursement bank calls only)**: `ParentDisbursementBankCallService` (`bank.parent`) / `ChildDisbursementBankCallService` (`bank.child`) persist **UNKNOWN** for ambiguous/non-success outcomes on bank calls, not just uncertain transport:
  - **MFT status inquiry**: if the parsed inquiry outcome is **not** a definitive success (`isMFTTransactionSuccess == false`), log **UNKNOWN** (instead of logging SUCCESS).
  - **MFT status inquiry (try-path mapping)**: when `errorCode=0` and parsing can extract `transactionStat`:
    - `transactionStat != "Failure"` => log **SUCCESS**
    - `transactionStat == "Failure"` => log **FAIL**
    - otherwise (parsing can’t be trusted) => log **UNKNOWN**
  - **MFT status inquiry (exception path)**: if the inquiry call throws (catch path), log **UNKNOWN** (instead of FAIL) so retries preserve idempotency.
  - **MFT status inquiry (HDFC GTSI) `externalReferenceNo`**: session `externalReferenceNo` uses leg prefix **`06`** plus the **same numeric attempt counter** as the corresponding `DISBURSEMENT_*_MFT` payment ref (leg **`02`**). `refUsrNo` / `transaction_ref_number` remains the **original MFT payment** `client_reference_number`. This avoids bank duplicate-session rejection; `ExternalReferenceNoUtil` UNKNOWN-stability logic parses inquiry refs with **`06`** or legacy rows that reused **`02`**.
  - **MFT status inquiry retry/stop decision (`DO_TRANSACTION`)**:
    - `SUCCESS` => `DO_TRANSACTION=false` (do not re-initiate `DISBURSEMENT_MFT`)
    - definitive `FAIL` (`inquiryLogStatus=FAIL`) => `DO_TRANSACTION=true` (re-initiate `DISBURSEMENT_MFT`)
    - `UNKNOWN` => `DO_TRANSACTION=false` (processor does not re-initiate immediately; later replay relies on deterministic ref reuse)
  - **NEFT v1 payment**: if `out_transaction_id` is blank, log **UNKNOWN** (instead of FAIL).
  - **NEFT v1 sender/debit account (child-loans)**: child-loan NEFT v1 now sets `from_account_number=parent_disbursement_account_number` (and `from_customer_id=parent_disbursement_bank_customer_id`) in the execution context, and the HDFC NEFT v1 lib (`NeftTransaction`) uses these values when present; otherwise it falls back to configured `hdfc.bank.neft.sender.account.number` / `hdfc.bank.neft.customer.id`. This matches the existing `MiscFundTransfer` override pattern and prevents debiting the global config account for child transfers.
 - **Child charges distribution**: falls back to **parent-level** charges when the request contains an **empty/null** member charge payload for **any** member. When all members have **non-empty** details, charge amounts are computed **per child** from that child's payload (prevents PROC_FEE/child amount mismatches for `[]` cases).
  - Existing **uncertain transport** handling still applies (connect/read timeout, `NovopayFatalException` **408**, `BANK-100001` / `BANK-100004` when not SSL peer verification) with `DisbursementBankCallUncertainty`.
  - Other/non-disbursement steps still log **FAIL** (e.g. `getCustomerDetails` / Actor errors) because UNKNOWN is tied to MFT/NEFT disbursement call contexts.
  - Same ref on retry: `ExternalReferenceNoUtil` bumps counter only on **definitive FAIL** for the last MFT payment attempt. Additionally, if the latest **MFT inquiry** is `UNKNOWN`, it **reuses the inquiry counter** for the next MFT payment initiation to avoid double-disbursement risk. **GL CBS** CRR remains **FAIL** on error (`GLCBSIntegrationService` unchanged for UNKNOWN). Detection: `DisbursementBankCallUncertainty`.
- **NEFT v2 stage-wise flow (child-loans)**: when `disbursement_mode=OTHBACCT`, the child processor initiates NEFT in two stages and updates `loan_account_events_queue` via the WebClient post-processor:
  - stage-1: `disbursement_status=DTFC_SUCCESS` -> `ST_NEF`, sets `NEFT_STAGE_1_PENDING`, and logs child-scoped `..._NEFT_NEF`
  - stage-2: `disbursement_status=NEFT_STAGE_1_SUCCESS` (or `NEFT_STAGE_2_PENDING`) -> `ST_NEI`, sets `NEFT_STAGE_2_PENDING`, and logs child-scoped `..._NEFT_NEI`; callbacks progress the CLMT queue to `COMPLETED`
  - **NEFT v2 NEI callback CLMT parity with single-loan (UD)**: For **single-loan** NEFT v2, `DoGenericSyncSTPBankNeftCallBackProcessor` `processInProgressCallback` already sets `loan_account.disbursement_status=COMPLETED` on NEI **in-progress** (`codstatus` **N** / NDF path) as well as terminal **P**. For **CLMT**, `processInProgressCallbackForChild` now mirrors that for **`ST_NEI`** when queue `disbursement_status=NEFT_STAGE_2_PENDING`: sets embedded `COMPLETED`, `event_status=C`, preserves `BN`+reason on queue JSON like the parent in-progress path, and calls **`ParentGroupDisbursementStatusSyncService.syncParentAfterChildQueueProgress`**. **ST_NEI** success (`P`) child path also invokes **`syncParentAfterChildQueueProgress`** after saving CLMT (same as post-processor parity).
- **CLMT status persistence guard (post-processor)**: `ChildNeftClmtPostBankService.persistClmtAfterNeftBankResponse(...)` sets `loan_account_events_queue.event_status='C'` only when the embedded `disbursement_status` is `COMPLETED`; otherwise it remains `P` so the child event-processing job can pick it up for further stages.
- **Multi-path persistence reminder (child disbursement)**: CLMT status can be persisted via multiple entry points — (a) bank callback processors (`DoGenericSyncSTPBankNeftCallBackProcessor`), (b) inquiry/WebClient post-processors (`PostNEFTChildLoanBankDisbursementProcessor` / `PostMFTChildLoanBankDisbursementProcessor`), and (c) the pending-events batch (`childLoanEventProcessingBatchJob`). Any change to completion/status must keep **both** the queue row (`event_status`) and embedded JSON (`disbursement_status`) consistent across all paths, otherwise parent status sync can stall.
- **NEFT v2 STP inquiry success detection (parent + child-safe)**: HDFC `doGenericSyncSTPInquiry` returns numeric `errorcode` (e.g. `0`). The parent NEFT inquiry processor compares using `String.valueOf(executionContext.get("errorCode"))` (type-tolerant) so a successful inquiry is not misclassified as `FAIL` due to `getStringValue(...)` returning null for numeric values.
- **NEFT v2 inquiry reference key (parent + child, strict)**: inquiry/NEI resolve bank batch key from the persisted NEF request payload (`paymentrefno` preferred, fallback `batchnumext`) via `NeftV2BankReferenceUtil`. No fallback to `client_reference_number` in strict rollout mode; if payload is missing/unparseable or both keys are absent, flow fails fast with `MFI-40001` to avoid sending wrong inquiry keys to bank.
- **NEFT v2 stage-2 idempotency (child-loans)**: if a `client_request_response_log` row with `status=SUCCESS` already exists for the parent loan account + the child-scoped `..._NEFT_NEI` `transaction_type`, the processor skips re-initiating `ST_NEI` for **either** `disbursement_status=NEFT_STAGE_1_SUCCESS` or `NEFT_STAGE_2_PENDING` (queue can lag after a successful NEI); waits for callback to complete CLMT -> `COMPLETED`.
- **NEFT v2 stage-2 idempotency (parent / JLG–INDL)**: `CallBankAPIForDisbursementProcessor` skips `ST_NEI` when a **SUCCESS** CRR exists for the orchestration-scoped `…_NEFT_NEI` type (from `transaction_type` + `_NEFT_NEI`), for **both** `NEFT_STAGE_1_SUCCESS` and `NEFT_STAGE_2_PENDING`, matching child behaviour; `doNEFTTransaction` defends again before `neftPaymentV2Stage2`.
- **Disbursement status inquiry vs current rail**: `CallBankAPIForDisbursementProcessor` runs bank **status inquiry** only when `disbursement_mode` matches the latest `client_request_response_log` leg (**ACCTWB** + `…_MFT`, **OTHBACCT** + `…_NEFT_*`). If the user switches from MFT to NEFT, a stale latest MFT leg no longer drives MFT inquiry before the NEFT initiation path.
- **NEFT v2 stage-1 inquiry gate (parent + child, `NeftStage1InquiryGate`)**: run bank stage-1 inquiry when `disbursement_status=NEFT_STAGE_1_PENDING` **or** when `disbursement_status=DTFC_SUCCESS` and the selected NEF CRR row is **not** `status=SUCCESS` (reconcile before controlled ST_NEF retry). When `DTFC_SUCCESS` and NEF CRR is already `SUCCESS`, skip inquiry and set `DO_TRANSACTION=false` (no duplicate ST_NEF leg from inquiry routing). For `NEFT_STAGE_1_SUCCESS` / `NEFT_STAGE_2_PENDING` without entering stage-1 inquiry, `DO_TRANSACTION=true` allows leg-2 NEI.
- **NEFT v2 ST_NEF idempotency (parent + child)**: before initiating ST_NEF from `DTFC_SUCCESS`, if a **SUCCESS** NEF CRR already exists for the same scoped `transaction_type`, skip the bank initiation (`DO_TRANSACTION=false`) as defence-in-depth vs duplicate debit.
- **PostNEFT child CRR `transaction_type`**: `PostNEFTChildLoanBankDisbursementProcessor` derives child-scoped `…_EXTREF{n}_NEFT_NEF` / `…_NEFT_NEI` from `transaction_type`, `external_ref_number`, and `next_disbursement_status` when the WebClient callback omits `transactionIdentifier`, so `client_request_response_log.transaction_type` is always populated for STP callbacks and forensics.
- **CLMT `loan_account_events_queue`**: `PerformChildLoanBankDisbursementProcessor` relies on `CreateClmtLoanAccountEventsProcessor` to **`saveAll`** member CLMT rows up front (pending **P**), not `create_event_data_only=false` (which skipped `saveAll` and left child-loan bank calls without a persisted row). **`filler_2`** is set at CLMT row creation from the child **`external_ref_number`** on the same member `eventData` that `ChildLoanMoneyTransferEventsQueueDataPopulator` uses for queue `data`, so **`DisbursementClmtCashOverrideHandler`** / LAR can correlate pending CLMT even when the bank leg fails before **`PostNEFTChildLoanBankDisbursementProcessor`** runs (post-processors may still refresh `filler_2` on success paths). For **NEFT v2**, WebClient calls invoke `PostNEFTChildLoanBankDisbursementProcessor` to update CLMT after bank responses; for **NEFT v1**, `doNEFTTransactionVersion1` calls `PostNEFTChildLoanBankDisbursementProcessor.updateChildClmtQueueAfterNeftV1` after inline CRR because `neftPayment` does not invoke the WebClient post-processor. After processing all children, `PerformChildLoanBankDisbursementProcessor` calls **`ParentGroupDisbursementStatusSyncService.syncParentAfterChildQueueProgress`** (fresh DB read of CLMT rows). **Gap closed**: child bank calls can finish on **WebClient** threads **after** that synchronous sync runs — **`PostMFTChildLoanBankDisbursementProcessor`** and **`PostNEFTChildLoanBankDisbursementProcessor`** (NEF/NEI WebClient path) call **`syncParentAfterChildQueueProgress`** again after persisting CLMT so mixed MFT/NEFT multi-child runs still move the parent from **`PARENT_SUCCESS`** to **`CHILD_SUCCESS`** when all CLMT are **C** and CLB is still **P**.

### interest_accrual_details (InterestAccrualDetailsEntity)
- **totalAccruedAmount**: interest accrued for this period
- **totalAccrualPostedAmount**: how much of accrued has been posted via INTEREST/NORMAL_ACCRUAL txn
- **lastAccrualPostedDate**: last date accrual was posted
- Booking = posting the accrual (totalAccrualPostedAmount catches up to totalAccruedAmount)

### loan_account_billing_details (LoanAccountBillingDetailsEntity)
- Tracks which installments have been billed (BILLING/NORMAL_BILLING posted)
- **transactionValueDate**: installment date that was billed
- Billing ≠ Accrual: billing generates dues, accrual recognizes interest income

### death_foreclosure_details (DeathForeclosureDetailsEntity)
- **outstandingLoanBalance**: computed as-of death date
- **balanceClaimAmount**: sum_assured - outstandingLoanBalance (sent to insurer)
- **excessAmount**: from deathForeclosureDetailsEntity (customer excess used in settlement)

### death_foreclosure_insurance_staging_details
- Stores claim data sent to/from insurer (outbound/inbound files)
- **balanceClaimAmount** here drives the insurance file, independent of GL posting
- **Row reuse (initiation path)**: when (re)initiating an insurance claim for the same `death_foreclosure_details_id`, the flow **reuses** the existing staging row if present (looked up by `death_foreclosure_details_id`) and resets `file_upload_id`, `status`, and `inout_status` to null, then sets `claim_status='PENDING'`. A new row is created only if no row exists for that `death_foreclosure_details_id`. (Evidence: `ProcessDeathForeclosureAsPerStageProcessor.populateDeathForeclosureInsuranceStagingDetails()`.)
- **Reverse-feed rework loop (`Pending for FR`) risk**: `deathForeclosureInsuranceJob` processes inbound reverse-feed rows (`inout_status='INBOUND_SUCCESS'`) with insurer statuses like `Pending for FR` and `Claim Closed`. For `Pending for FR`, it attempts a task workflow update (`updateTaskWorkflow`) and then marks the staging row as handled by setting `claim_status='REJECTED'`. Because the task update is a separate microservice transaction, a failure/rollback after that call can leave the staging row still eligible (`Pending for FR` + `INBOUND_SUCCESS`) while task state has changed. In chunk/partition execution, a single such poison row can fail the job and block other eligible records. (See `system_brain/edge_cases/death_foreclosure_insurance_pending_fr_partial_progress_blocks_batch.md`.)

### loan_account_closure_details (LoanAccountClosureDetailsEntity)
- Records closure event: identifierType = FORECLOSURE, DEATH_FORECLOSURE, REPAYMENT, AUTOCLOSURE
- Can be used for idempotency checks

