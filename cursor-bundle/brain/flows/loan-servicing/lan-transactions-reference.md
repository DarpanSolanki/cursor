# LAN Transactions — single reference

> Every transaction that mutates a loan account (LAN) in `mfi_accounting.loan_account` or `mfi_accounting.transaction_master`. Pinpoints the entry-point Request, the workflow gating (3-stage task workflow vs. classic maker-checker vs. direct), the audit tables, and the gotchas. **Use this BEFORE grepping code or writing SQL.**
>
> When you need step-by-step processor chains, jump to the per-flow doc linked in the `Doc` column.

## A. The meta-patterns

There are **three distinct gating models** in the LMS. Knowing which one a transaction uses is the first question to answer when debugging.

### Model 1 — Approval-service maker-checker (1 stage)

Maker submits → `mfi_approval.application` row created (PENDING) → Checker approves via `approveApplication` → original Request re-fired with `function_code=APPROVE` → posting happens. Documented end-to-end in [`../maker-checker.md`](../maker-checker.md).

Audit footprint per LAN: 1 row in `mfi_approval.application`, 1 row in `mfi_task.task` (optional, role-based), audit log entry of type `SEND_FOR_APPROVAL_*`.

Used by: most non-MFI flows; classic webapp forms with single "Approve" button.

### Model 2 — Task workflow with N sequential stages (multi-stage)

Maker initiates → `mfi_task.workflow_master` row + N `workflow_stage_details` rows define a chain of task types. The same task row is mutated stage-by-stage via `updateTaskWorkflow`. Each stage's Approve dispatches a configured API call (see `task_type_api_execution`) — typically back to the same originating Request with a stage-specific `function_code`.

Audit footprint per LAN: 1 row in `mfi_task.task` (`current_status` and `task_type_id` change as stages progress), audit lifecycle entries in `mfi_task.task_activity`. **No `mfi_approval.application` row.**

Used by: MFI Foreclosure (3 stages: Review / Approval / Final Submission), Death Foreclosure (6 stages), some MFI part-prepayment variants.

### Model 3 — Direct (no gating)

Customer / system event drives the change directly without an operator approving. Either a callback from an external system (bank deposit, NACH return), or an internal batch job, or an asynchronous fanout via Kafka.

Audit footprint per LAN: no `mfi_task.task` row, no `mfi_approval.application` row. The transaction is captured in `mfi_accounting.transaction_master` + per-flow detail tables + `mfi_audit.audit_log`.

Used by: Repayment via Kafka (`bulk_collection_data_*`), Advance Repayment auto-apply, SHG/JLG child fan-out events, EOD/BOD batch effects (accrual, billing, NPA, asset criteria).

## B. Transaction-by-transaction reference

> "Detail tables" lists the rows written in addition to `transaction_master` / `transaction_partition_details`.

### B.1 — Disbursement

| Field | Value |
|---|---|
| Entry-point Request | `disburseLoan` (via Kafka `disburse_loan_api_<tenant>` → `LmsMessageBrokerConsumer`) |
| Gating model | Model 3 (Kafka-async; LOS produces the trigger) |
| Function-code matrix | 9-stage `function_sub_code` pipeline: BPI_INTEREST → ACCRUAL_CALC → DISBURSE → BANK_CALL → POST_BANK_CALL → POST_NEFT → POST_MFT → APPROVE_DISBURSEMENT → COMPLETED (varies by mode) |
| Loan-status transitions | APPROVED → LOAN_BOOKED → NEFT_STAGE_1_PENDING → ... → ACTIVE |
| Detail tables | `loan_disbursement_transaction`, `loan_disbursement_mode_details`, `loan_disbursement_charge_details`, `loan_account_events_queue` (SHG/JLG fan-out), `bank_service_call_retry`, `client_request_response_log` |
| GL legs | DR  LOAN_PRIN_AC / CR  CUSTOMER_AC + tax/charge legs |
| Gotchas | Redis dedup key `dl<productId>_<extRefNumber>`; CAS-only mutation of `disbursement_status` post-`4c339282f`; never call setters on the CLMT entity after `ChildClmtStateMachineService.transition` |
| Doc | [`../disbursement-end-to-end.md`](../disbursement-end-to-end.md), [`../../engines/disbursement-engine.md`](../../engines/disbursement-engine.md) |

### B.2 — Disbursement Cancellation

| Field | Value |
|---|---|
| Entry-point Request | `loanDisbursementCancellation` (individual) / `childLoanDisbursementCancellation` (child) / `childLoanDisbursementCancellationParentRescheduling` (parent reschedule after child cancel) |
| Gating model | Model 1 (approval-service maker-checker: DISBURSEMENT_CANCELLATION_RECOMMEND + DISBURSEMENT_CANCELLATION_APPROVAL) |
| Function codes | DEFAULT (initiate) / APPROVE / REJECT |
| Loan-status transitions | ACTIVE → DISB_CANCEL_FREEZE → CLOSED (full reversal) / ACTIVE (post-reschedule for SHG/JLG) |
| Detail tables | `loan_disbursement_cancellation_details`, `loan_disbursement_cancellation_insurance_staging_details`, `loan_account_closure_details`, `loan_account_events_queue` |
| GL legs | Reverse of disbursement (DR CUSTOMER_AC / CR LOAN_PRIN_AC) + cancellation charge |
| Gotchas | Refund routing depends on `disbursement_mode` (CASA / NEFT / cash); SHG parent reschedule re-emits CLMT events |
| Doc | [`disbursement-cancellation.md`](disbursement-cancellation.md) |

### B.3 — Repayment (standard)

| Field | Value |
|---|---|
| Entry-point Request | `loanRepayment` (direct) / `collectionLoanRepayment` (LCS-routed) / `recurringPayment` (SI/eNACH) |
| Gating model | Model 3 (no operator approval; cash receipt or auto-debit drives it) |
| Function codes | DEFAULT (post + appropriate) |
| Loan-status transitions | ACTIVE → ACTIVE (no status change unless final EMI → may auto-close) |
| Detail tables | `loan_due_details`, `loan_account_payments_details`, `loan_due_details_loan_account_payments_details`, `loan_account_billing_details`, optionally `loan_account_closure_details` |
| GL legs | DR CUSTOMER_AC / CR LOAN_PRIN_AC + INT_RECEIVABLE_AC + penal_lpp + tax (per appropriation order) |
| Gotchas | Idempotency on `client_reference_number` (receipt_number); appropriation order is data-driven from product master; advance-repayment is a separate flow ([`advance-repayment.md`](advance-repayment.md)) |
| Doc | [`../repayment-end-to-end.md`](../repayment-end-to-end.md), [`../../engines/repayment-engine.md`](../../engines/repayment-engine.md) |

### B.4 — Foreclosure (MFI 3-stage)

| Field | Value |
|---|---|
| Entry-point Request | `loanPrepayment` (NOT loanForeclosure on MFI flow) |
| Gating model | **Model 2** (3-stage task workflow, code=FORECLOSURE in `mfi_task.workflow_master`) |
| Function codes | DEFAULT (initiate) → VALIDATE (Review approve) → APPROVE_TASK (Approval approve) → APPROVE_TASK (Final Submission approve) → APPROVE (deposit-driven, via payments callback) → REJECT path |
| Workflow stages | 1=Review (task_type_id=117, RM) → 2=Approval (118, BH/PH/RBH/ZH) → 3=Final Submission (119, OPS_MAKER/RM/SO) |
| Loan-status transitions | ACTIVE → FORECLOSURE_FREEZE → FORECLOSED → CLOSED |
| Detail tables | `prepayment_details`, `prepayment_charge_details`, `prepayment__document`, `loan_account_closure_details`, `loan_account_payments_details`, `loan_due_details`, `loan_installment_details`, `loan_account_tax_details`, `loan_account_noc_details` (NOC queue) |
| GL legs | DR CUSTOMER_AC ₹full outstanding / CR LOAN_PRIN_AC + INT_RECEIVABLE_AC + FORECLOSURE_CHRG_INCOME_AC + TAX_GST_PAYABLE_AC |
| Deposit trigger | `payments:updateSchedulePayment` → `MfiCollectionsDAOService.pushLoanPrePaymentToLMS` → `accounting:loanPrepayment` (function_code=APPROVE) — this is what posts the transaction and closes the loan |
| Audit fields (`prepayment_details`) | `task_status` PENDING → APPROVED (post stage 2). `prepayment_status` PENDING → APPROVED (post deposit). `approved_on` set during stage 2. Challan/receipt set during stage 3. |
| Gotchas | (1) `UpdatePrepaymentTaskDetailsProcessor.populateTaskDetails` historically ignored the XML `task_status` IParam — fixed: explicit IParam now wins. (2) `loan_status=FORECLOSURE_FREEZE` is only persisted AFTER task creation succeeds (`154b500c0` fix). (3) For SHG/JLG child, parent's part-prepayment is invoked inline (`callInternalOrchestrationProcessor → parentLoanAccountPartPrepayment`). |
| Doc | [`../foreclosure-and-closure.md`](../foreclosure-and-closure.md) |

### B.5 — Foreclosure (non-MFI / classic)

| Field | Value |
|---|---|
| Entry-point Request | `loanForeclosure` |
| Gating model | Model 1 (`mfi_approval.application`, single Approve) |
| Function codes | DEFAULT (initiate) → APPROVE / REJECT |
| Loan-status transitions | ACTIVE → FORECLOSURE_FREEZE → FORECLOSED → CLOSED |
| Detail tables | Same as B.4 |
| GL legs | Same as B.4 |
| Doc | [`../foreclosure-and-closure.md`](../foreclosure-and-closure.md) §"Step-by-step (individual loan)" |

### B.6 — Death Foreclosure

| Field | Value |
|---|---|
| Entry-point Request | `loanDeathForeclosure` |
| Gating model | **Model 2** (6-stage task workflow for the death-claim lifecycle: Recommend → Review → Approval → Insurance Push → FTR/FTNR processing → Closure) plus Model 3 for insurance partner async response |
| Function codes | DEFAULT / APPROVE / REJECT / multiple stage-specific codes |
| Loan-status transitions | ACTIVE → DEATH_FORECLOSURE_FREEZE → DECEASED → CLOSED |
| Detail tables | `death_foreclosure_details`, `death_foreclosure_appointee_details`, `death_foreclosure_nominee_details`, `death_foreclosure_insurance_staging_details`, `death_foreclosure_payment_mode_details`, `death_foreclosure_details__document`, `loan_account_closure_details`, `prepayment_details` (for the FC posting), `loan_account_tax_details` |
| GL legs | Foreclosure-style (B.4) + insurance reverse-feed legs (premium refund / claim received) |
| Gotchas | SDCP-9301 (`mfi_release_v3.3.1.0.1`) fixed billed-principal split + force-billing on partial-cycle DCF — placeholder swap `LOSSES_INT_WAIVED_AIR` → `LOSSES_INT_WAIVED` lives in [`../../changelog/CHANGELOG.md`](../../changelog/CHANGELOG.md) entry 2026-05-07. Always invoke `forceBilling=true` for partial-cycle. |
| Doc | [`death-foreclosure.md`](death-foreclosure.md) |

### B.7 — Part-Prepayment

| Field | Value |
|---|---|
| Entry-point Request | `loanAccountPartPrepayment` / `parentLoanAccountPartPrepayment` / `childLoanPartPrepayment` |
| Gating model | Model 1 (approval-service maker-checker) for self-serve; Model 3 if invoked inline by a parent flow (child foreclosure → parent reschedule) |
| Function codes | DEFAULT / APPROVE / REJECT |
| Loan-status transitions | ACTIVE → PART_PREPAYMENT_FREEZE → ACTIVE |
| Impact options | `part_prepayment_impact = REDUCE_EMI | REDUCE_TENOR` |
| Detail tables | `loan_account_part_prepayment_details`, `loan_account_payments_details`, `loan_account_tax_details`, `loan_due_details` + `loan_installment_details` (re-amortised), `loan_repayment_schedule_details` (replaced) |
| GL legs | DR CUSTOMER_AC / CR LOAN_PRIN_AC (no full-closure legs) |
| Gotchas | EMI/tenor recalculation generates a new repayment schedule — preserve identifiers (due_id) for already-paid installments; tenor-reduction does NOT re-amortise paid rows |
| Doc | [`part-prepayment.md`](part-prepayment.md) |

### B.8 — Restructuring

| Field | Value |
|---|---|
| Entry-point Request | `loanAccountRestructuring` / `childLoanRestructuring` |
| Gating model | Model 1 |
| Function codes | DEFAULT / APPROVE / REJECT (with `restructure_type=UPDATE_EMI|UPDATE_TENURE|ROI_CHANGE`) |
| Loan-status transitions | ACTIVE → LOAN_RESTR_FREEZE → ACTIVE |
| Detail tables | `loan_account_restructuring_details`, `loan_account_reschedule_details`, `loan_repayment_schedule_details` (replaced), `loan_due_details` (replaced for future installments) |
| GL legs | None directly; subsequent EOD interest accrual reflects new ROI/tenure |
| Gotchas | Identifier preservation for paid installments matters; charges_to_apply_during_restructure read from product scheme |
| Doc | [`restructuring.md`](restructuring.md) |

### B.9 — Rebooking

| Field | Value |
|---|---|
| Entry-point Request | `loanAccountRebooking` / `individualLoanAccountRebooking` / `groupLoanAccountRebooking` / `childLoanRebooking` |
| Gating model | Model 1 (LOAN_REBOOKING_CHECKER / GROUP_LOAN_REBOOKING_CHECKER task type) |
| Function codes | DEFAULT / APPROVE / REJECT |
| Loan-status transitions | CLOSED (cancelled) → REBOOKED → ACTIVE (new loan terms) |
| Detail tables | `loan_account_rebooking_details`, recreated `loan_repayment_schedule_details`, `loan_due_details` |
| GL legs | Re-disbursement legs (essentially a new disburseLoan posting under the same account number) |
| Gotchas | Original LAN is retained; the rebooking writes a new disbursement_transaction row referencing the same loan_account_id |
| Doc | [`rebooking.md`](rebooking.md) |

### B.10 — Reopening

| Field | Value |
|---|---|
| Entry-point Request | `loanAccountReopening` / `childLoanReopening` |
| Gating model | Model 1 (LOAN_REOPEN_CHECKER) |
| Function codes | DEFAULT / APPROVE / REJECT |
| Loan-status transitions | CLOSED → REOPENED → ACTIVE |
| Detail tables | `loan_account_reopening_details`; reverses the latest `loan_account_closure_details` row; restores `loan_due_details` / `loan_installment_details` |
| GL legs | Exact reverse of the closure transaction (typically the foreclosure posting) |
| Gotchas | `loan_account.la_closing_date` is **NOT** cleared on reopen — preserves historical record. NOC may have been issued before reopen — flag for revocation. |
| Doc | [`reopening.md`](reopening.md) |

### B.11 — Waiver (charges / principal)

| Field | Value |
|---|---|
| Entry-point Request | `waiveLoanAccountCharges` / `childWaiveLoanAccountCharges` |
| Gating model | Model 1 (LOAN_ACCOUNT_CHARGE_WAIVER task) |
| Function codes | DEFAULT / APPROVE / REJECT |
| Loan-status transitions | None (loan stays ACTIVE) |
| Detail tables | `waiver_details`, `waiver_loan_due_details`, `waiver_document` |
| GL legs | DR LOSSES_INT_WAIVED / CR INT_RECEIVABLE_AC (interest waiver); similar for principal waiver via LOSSES_PRIN_WAIVED |
| Gotchas | Principal waiver triggers asset-class movement; SDCP-9301 placeholder swap applies for death-foreclosure cycle. The waived components reduce the foreclosure amount in subsequent foreclosure. |
| Doc | [`waiver.md`](waiver.md) |

### B.12 — Excess Amount Refund

| Field | Value |
|---|---|
| Entry-point Request | `loanAccountExcessAmountRefund` / `childLoanAccountExcessAmountRefund` / `proactiveExcessAmountRefund` |
| Gating model | Model 1 (EXCESS_AMOUNT_REFUND_CHECKER) — except proactive which is Model 3 (batch-driven) |
| Function codes | DEFAULT / APPROVE / REJECT |
| Loan-status transitions | None for standard; `loan_account.excess_amount` is reduced |
| Detail tables | `loan_account_excess_amount_refund_details`, `loan_account_payments_details` (negative payment) |
| GL legs | DR CUSTOMER_EXCESS_AC / CR CUSTOMER_AC (bank refund); reverses the original excess credit |
| Gotchas | Proactive refund runs as batch (`proactive_excess_amount_refund` job) and fails to a retrigger table; replays via batch retry |
| Doc | [`excess-amount-refund.md`](excess-amount-refund.md) |

### B.13 — Write-off

| Field | Value |
|---|---|
| Entry-point Request | `loanWriteoff` |
| Gating model | Model 1 (corporate level approval, usually finance) |
| Function codes | DEFAULT / APPROVE / REJECT |
| Loan-status transitions | NPA → WRITEOFF → CLOSED (technical write-off) |
| Detail tables | `loan_provisioning_details` (final provisioning adjustment), `loan_account_closure_details` |
| GL legs | DR PROVISION_AC + WRITEOFF_LOSS_AC / CR LOAN_PRIN_AC + INT_RECEIVABLE_AC |
| Gotchas | Sub-cases: full WO vs partial WO; settlement WO at a fraction; recovery posting reverses partial WO |
| Doc | [`write-off.md`](write-off.md) |

### B.14 — Advance Repayment

| Field | Value |
|---|---|
| Entry-point Request | `loanAdvanceRepayment` (job-triggered) |
| Gating model | Model 3 (batch driver — `loanAdvanceRepayment` Request runs in EOD context) |
| Function codes | DEFAULT |
| Loan-status transitions | None usually; may close loan if all dues paid up |
| Detail tables | `loan_account_payments_details`, `loan_due_details` (auto-appropriated) |
| GL legs | Same as standard repayment (B.3) |
| Gotchas | Sources excess from `loan_account.excess_amount`; runs after EOD billing so it sees the latest due |
| Doc | [`advance-repayment.md`](advance-repayment.md) |

### B.15 — Transaction Reversal

| Field | Value |
|---|---|
| Entry-point Request | `loanAccountTransactionReversal` / `childLoanTransactionReversal` / `bulkSGToTransactionReversalJob` |
| Gating model | Model 1 (TRANSACTION_REVERSAL_CHECKER task) — or Model 3 for the bulk job |
| Function codes | DEFAULT / APPROVE / REJECT |
| Loan-status transitions | None directly; recomputes loan state if the reversed txn was a foreclosure |
| Detail tables | `transaction_reversal_document`; cancels rows in `transaction_master` (via `reverseTransaction` API); replays affected `loan_due_details` rows |
| GL legs | Exact reverse of the original transaction |
| Gotchas | Reverse-of-closure restores loan to its pre-closure state — implicit reopen; verify `loan_status` is restored before NOC reversal |
| Doc | [`transaction-reversal.md`](transaction-reversal.md) |

### B.16 — Standing Instruction (SI) / eNACH presentation

| Field | Value |
|---|---|
| Entry-point Request | `generateSIPresentationFiles`, `consumeSIPresentationFile` (batch); `recurringPayment` per LAN |
| Gating model | Model 3 (batch + bank file roundtrip) |
| Function codes | DEFAULT, ACK, FAIL |
| Loan-status transitions | None on presentation; recurringPayment posts the actual repayment |
| Detail tables | `si_presentation_details`, `si_presentation_loan_account_details`, `si_presentation_file_details`, `si_failed_presentation_details`, `si_lien_presentation_file_details`, `si_auto_hold_presentation_file_details`, `enach_presentation_*` |
| GL legs | On success: standard repayment legs. On fail: no GL effect; row in `si_failed_presentation_details` for replay. |
| Gotchas | Customer-name mismatch fix (SDCP-8576 series) on payments side; SDCP-9301 birth-date validation; consumer batch is single-node-locked (see [`../../platform/multinode-batch.md`](../../platform/multinode-batch.md)) |
| Doc | [`../repayment-end-to-end.md`](../repayment-end-to-end.md) (SI section), runbook [`../../runbooks/repayment-mismatch.md`](../../runbooks/repayment-mismatch.md) |

### B.17 — EOD/BOD-driven derived state

Not transactions per se, but they mutate `loan_account` and write detail rows.

| Effect | Job | Function code | Touches |
|---|---|---|---|
| DPD bucket update | `loanAccountDpdCalcJob` | DEFAULT | `loan_account.dpd_bucket_id`, `loan_account_derived_fields` |
| Asset criteria | `loanAccountAssetCriteriaJob` | DEFAULT | `loan_account.asset_criteria_group_id`, asset GL movement on bucket flip |
| Asset classification | `loanAccountAssetClassificationJob` | DEFAULT | `loan_account.asset_classification_slabs_id`, NPA-flag |
| Interest accrual calc | `interestAccrualCalculation` | DEFAULT | `interest_accrual_details` (calc) → BOOK by interestAccrualPosting |
| Penal accrual | `penalInterestAccrualCalculation` + `penalInterestAccrualBooking` | DEFAULT | `penal_interest_accrual_details` |
| Billing | `loanAccountBillingJob` | DEFAULT | `loan_account_billing_details`, posts billing legs to `transaction_master` |
| Auto-closure | `loanAccountClosure` | DEFAULT | `loan_account.loan_status=CLOSED`, `loan_account_closure_details` |

See [`../../accounting/03-batch-dependency.md`](../../accounting/03-batch-dependency.md) for job dependency order; [`../eod-bod-cycle.md`](../eod-bod-cycle.md) for the narrative.

### B.18 — Child fan-out events (SHG/JLG)

A parent action enqueues `loan_account_events_queue` rows that the `childLoanEventProcessingBatchJob` processor consumes to fire per-child Requests.

| Parent action | Event types | Child Request |
|---|---|---|
| Parent disbursement | CHILD_DISBURSEMENT | `childLoanDisbursement` |
| Parent foreclosure | CHILD_FORECLOSURE | `childLoanForeclosure` → `individualChildLoanForeclosure` |
| Parent rebooking | CHILD_REBOOKING | `childLoanRebooking` |
| Single child cancel | CHILD_DISB_CANCEL | `childLoanDisbursementCancellation` |
| Child cancel parent reschedule | CHILD_PARENT_RESCH | `childLoanDisbursementCancellationParentRescheduling` |

See [`../shg-jlg-group-loan.md`](../shg-jlg-group-loan.md) and [`../../accounting/06-shg-jlg-group-loans.md`](../../accounting/06-shg-jlg-group-loans.md).

## C. Analysis methodology — how to trace a "flow movement" for a LAN

Use this when (a) investigating a reported issue, or (b) adding a new transaction to a flow.

1. **Identify the gating model** (A.1 / A.2 / A.3). Decide which audit tables matter:
   - Model 1 → `mfi_approval.application`, `mfi_task.task` (optional)
   - Model 2 → `mfi_task.task`, `mfi_task.workflow_master` + `workflow_stage_details`, `mfi_task.task_type_api_execution`
   - Model 3 → `mfi_accounting.transaction_master` + detail rows + Kafka offset of relevant topic

2. **Locate the entry-point Request** in section B. Read the orchestration XML (`loans_orc.xml`, `group_mfi_orc.xml`, `mfi_orc.xml`, etc.) — the Request name + the `<Control method="regExp" pattern="${function_code}" ...>` blocks tell you which sub-flow runs for each operator action.

3. **Match each Approve action to the right `function_code`.** For Model 2 flows, the mapping lives in `mfi_task.task_type_api_execution.api_function_code` per `(task_type_version_id, action)`. Query first; don't guess.

4. **For each processor in the chain, classify the side effect**:
   - **Read-only** (validation, fetch) — won't change state; only the data it loads into context.
   - **State change** (sets a status, writes a row) — note exactly which table column + what value.
   - **API sub-call** (e.g. `<API id="postTransaction">`) — opens a new Request context; IParam values with `scope="local"` are visible only inside the sub-call.
   - **Async fanout** (writes `loan_account_events_queue`, publishes Kafka) — the change will be applied by a different processor in a separate transaction. Track the event_type.

5. **Confirm with QA-DB ground truth.** Match expected vs. actual:
   - Time-correlate `transaction_master.created_on` with `task_activity.activity_time` and `loan_account.updated_on`.
   - For Model 2 flows, check `prepayment_details.task_status` / `prepayment_status` after each stage approve; for Model 1, check `mfi_approval.application.status`.
   - Use the `lan-360` skill for one-shot full-state dump.

6. **Identify the smallest reproducer.** For Model 2 flows: which **single processor** invocation flipped the wrong state? Re-read its Java source; look for IParam-from-XML semantics vs. computed-internally divergence (the prepayment task_status bug was exactly this pattern — see "Common gotcha" below).

## D. Common gotchas across LAN transactions

### D.1 — XML IParam silently ignored by Java processor

If an XML processor is wired with `<IParam fieldName="X" value="Y" />` but the Java code doesn't `executionContext.getValue("X")`, the value is ignored. The compiler doesn't catch this. Always grep the processor Java file for the IParam field names before trusting the XML — especially when the processor name implies "set X" but the side effect is actually computed.

The historical foreclosure `task_status` bug ([`UpdatePrepaymentTaskDetailsProcessor.populateTaskDetails`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/prepayment/processor/UpdatePrepaymentTaskDetailsProcessor.java)) was exactly this — the XML said `task_status="APPROVED"` but the processor computed PENDING when `function_code != APPROVE`. Fix: read the explicit IParam after the computation.

### D.2 — `function_code` is global; sub-API calls leak

`<IParam fieldName="function_code" value="DEFAULT" scope="local"/>` is supposed to scope to the sub-API call only. In some processor chains the value still surfaces in the parent context — relying on `function_code` to drive state-machine decisions in a processor that runs *after* a sub-API call is fragile. Prefer explicit branch flags (`do_prepayment`, `approve_task`, `create_task`) set by a dedicated `dummyProcessor` inside the right `<Control>` block.

### D.3 — `loan_account` status updates after task creation, never before

Per [`rules/multi-path-state-persistence-safety.md`](../../rules/multi-path-state-persistence-safety.md) and SDCP-9301, persist `loan_status` to `*_FREEZE` **after** the task workflow row is created; otherwise a task-creation failure leaves the loan frozen with no task to release it (the [`task-id-orphan-data-patch`](../../runbooks/task-id-orphan-data-patch.md) runbook is the cleanup story).

### D.4 — CAS contract on `loan_account.disbursement_status` and `loan_account_events_queue.data->>'disbursement_status'`

For disbursement flows: never call setters on the entity returned by `ChildClmtStateMachineService.transition`. Hibernate auto-flush will overwrite the CAS-stamped row when the outer transaction commits. See [`state-machine-safety` skill](../../../skills/state-machine-safety) and the post-`4c339282f` rule. This is the most common race-bug source in 2026.

### D.5 — Posting placeholder swaps

Several flows use placeholder names that have changed across 3.3.1.0.x — e.g., `LOSSES_INT_WAIVED_AIR` → `LOSSES_INT_WAIVED` on death foreclosure (SDCP-9301). Before adding a new flow, run [`posting-rule-resolver` skill](../../../skills/posting-rule-resolver) to resolve current placeholder bindings.

### D.6 — Idempotency keys

| Flow | Idempotency key | Storage |
|---|---|---|
| Disbursement | `dl<productId>_<externRefNumber>` | Redis ACCOUNTING DB 5 |
| Repayment | `client_reference_number` (receipt_number) | `transaction_master.client_reference_number` UNIQUE |
| Foreclosure / Part-prepayment | `prepayment_details.id` + state machine | DB row |
| SI presentation | `si_presentation_file_details.id` + `si_failed_presentation_details` for retry | DB |
| Kafka consumers | offset commit after success | Kafka |

## E. When you're stuck

- `lan-360` skill — single-LAN ground truth across all tables.
- `txn-graph` skill — Request → processor chain at file:line for any flow.
- `rca-workflow` skill — race / stuck-row playbook.
- Brain doc per flow — column 7 ("Doc") in section B.
- Service-specific runbook — [`../../runbooks/`](../../runbooks/).
