# Flow — Foreclosure → auto-closure → NOC

## Mental model

Customer wants to close the loan early. Maker initiates `loanForeclosure` (or `childLoanForeclosure` for SHG/JLG members), which freezes the loan, computes prepayment + foreclosure charges, and waits for checker approval. On approval, the system books pending accruals, posts the foreclosure transaction (DR customer / CR principal + interest + fc charge + tax), updates due/installment, transitions `loan_status = FORECLOSED`, then `loanAccountAutoClosureProcessor` finalises to `CLOSED`. NOC is queued for issuance.

## Services involved

| Service | Role |
|---|---|
| webapp / android | Operator initiates + approves |
| accounting | Entire foreclosure pipeline |
| approval | Maker-checker workflow (non-MFI flow only — see "Two foreclosure flows" below) |
| task | 3-stage workflow tasks (Review / Approval / Final Submission) for MFI |
| payments | Bank deposit callback (`updateSchedulePayment`) for MFI cash foreclosure |
| dms | Foreclosure receipt (CDS doc) + NOC document |
| notifications | Customer SMS confirmation |

## Two foreclosure flows

The code base ships **two distinct foreclosure flows**; pick by entry-point Request:

| Flow | Request | Trigger UI | Approval gating |
|---|---|---|---|
| **Non-MFI maker-checker** (described in §"Step-by-step" below) | `loanForeclosure` | Standard webapp Approve form | `mfi_approval.application` (single approve) |
| **MFI 3-stage task workflow** (described in §"MFI 3-stage workflow" below) | `loanPrepayment` (with `function_code=DEFAULT` → `APPROVE_TASK` → `APPROVE_TASK` → `APPROVE` chain) | `loan-foreclosure` module → `updateTaskWorkflow` per stage | `mfi_task.workflow_master.code='FORECLOSURE'` → `workflow_stage_details` (3 stages); no `mfi_approval.application` row |

Both end at the same final state (`loan_status=CLOSED`, `loan_account_closure_details` row, NOC queued) but the operator journey, audit trail, and tables touched are different. The MFI 3-stage version is what production runs for SHG/JLG/INDL retail loans through the webapp; the non-MFI version is used by older tenants and the legacy "Foreclosure" screen.

When debugging a stuck loan: **check `mfi_task.task` first** (look for tasks with `task_type_id IN (117, 118, 119)` for the LAN), then `mfi_accounting.prepayment_details` for `task_status`/`prepayment_status` audit, then `mfi_approval.application` only if you don't find anything in task table.

## Step-by-step (individual loan)

```
1. Maker hits Request loanForeclosure (function_code=DEFAULT)
   ─ valdiateLoanAccountNumberAndStatusProcessor
   ─ fetchSuperDataForForeclosureProcessor
   ─ createPrepaymentDetailsProcessor + createPrepaymentChargeDetailsProcessor
   ─ validateFinalPrepaymentProcessor
   ─ if maker_checker_enabled=1:
       loanForeclosure_submitApplication → approval (response 30003)
   ─ populateDataForRulesProcessor
   ─ createTaskWorkFlowHelpingProcessor (creates task in task service; throws fatal on pre-step API failure since 154b500c0)
   ─ updateLoanAccountStatusProcessor + updateLoanStatusForSHGProcessor
       loan_status → FORECLOSURE_FREEZE (persisted ONLY after task creation succeeds — see changelog 2026-05-04 SDCP_task-id-orphan)
   ─ updatePrepaymentTaskDetailsProcessor (writes task_id onto prepayment row)

2. Checker reviews, approves
   approval:approveApplication → re-fires loanForeclosure with function_code=APPROVE

3. APPROVE branch:
   ─ checkLoanAccountInterestAccrualBookingProcessor (book any pending accrual)
   ─ bookingNonPostedPenalProcessor
   ─ updateDueDetailsForPrepaymentProcessor
   ─ populateAdditionalAmountAndAccountDetailsForForeclosureProcessor
   ─ populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails
   ─ getPrepaymentDetailsProcessor
   ─ populateAmountComponentsForAppropriationProcessor
   ─ prepaymentApproppriationProcessor
   ─ <API id="postTransaction">
        DR  CUSTOMER_AC                ₹full outstanding
        CR  LOAN_PRIN_AC               ₹principal due
        CR  INT_RECEIVABLE_AC          ₹interest due
        CR  FORECLOSURE_CHRG_INCOME_AC ₹fc charge
        CR  TAX_GST_PAYABLE_AC         ₹tax
   ─ extractOverallTransactionDetailsAndNetAmountForAccountProcessor
   ─ updateLoanAccountTaxDetailsExternalReferenceIdProcessor
   ─ updateLoanDueDetailsProcessor / updateLoanInstallmentDetailsProcessor
   ─ getLoanRepaymentModeDetailsProcessor
   ─ createLoanAccountPaymentsDetailsProcessor
   ─ populateLoanAutoClosureReqProcessor
   ─ loanAccountDpdCalcProcessor (final DPD)
   ─ checkMovementForPrincipalWaiver
   ─ loanAccountAssetCriteriaProcessor + loanAccountAssetClassificationProcessor
   ─ updateLoanAccountStatusProcessor
        loan_status → FORECLOSED
   ─ pushLoanAccountClosureDetailsProcessor
   ─ updateExcessAmountForPrepaymentProcessor
   ─ updatePrepaymentTaskDetailsProcessor (close task)
   ─ deleteDraftProcessor (clear approval draft)
   ─ updateCollectionForClosureProcessor (notify LCS)
   ─ createLoanDueDetailsLoanAccountPaymentsDetailsProcessor
   ─ createLoanAccountClosureDetailsProcessor
   ─ prepaymentSMSNotification (notifications)

4. Auto-closure (inline if eligible)
   ─ loan_status → CLOSED via loanAccountAutoClosureProcessor

5. If inline auto-closure failed, the scheduled loanAccountClosure batch picks it up later.

6. NOC issuance
   ─ loan_account_noc_details row created (status=PENDING)
   ─ generateNocFileJob (scheduled) renders the NOC file
   ─ DMS upload + customer notification
```

## MFI 3-stage workflow (loanPrepayment)

This is the path the production webapp uses for foreclosure. The orchestration is `loanPrepayment` in [`loans_orc.xml`](../../trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml) (≈ line 1675). Workflow definition lives in `mfi_task.workflow_master` (code=`FORECLOSURE`) → `workflow_stage_details` rows pointing at 3 task types.

### Stage table (workflow_master.code='FORECLOSURE')

| Stage | Sequence | Task type | task_type_id | Role | Channel | API on Approve | function_code on Approve |
|---|---|---|---|---|---|---|---|
| 1 | 1 | Foreclosure Review | 117 | RM | WEB | `loanPrepayment` | `VALIDATE` |
| 2 | 2 | Foreclosure Approval | 118 | BH/PH/RBH/ZH | WEB | `loanPrepayment` | `APPROVE_TASK` |
| 3 | 3 | Foreclosure Final Submission | 119 | OPS_MAKER/RM/SO | WEB | `loanPrepayment` | `APPROVE_TASK` |

Mapping lives in `mfi_task.task_type_api_execution`. Each `updateTaskWorkflow` call moves the workflow forward by one stage; the same `mfi_task.task` row is mutated (current_status / task_type_id) — a NEW task row is **not** created per stage.

### Lifecycle per stage

```
Maker initiates → loanPrepayment(DEFAULT)
  ─ validateForChildLoanPrepayment + validateLoanPrepaymentProduct + checkLoanAccountInterestAndPenalAccrual + validateLoanPrepaymentData
  ─ create_task=true branch:
     ─ fetchBulkUniqueMasterData (forclosure_mode / closure_reason / paid_by masters)
     ─ createTaskDataPreProcessor
     ─ createPrepaymentDetailsProcessor (writes mfi_accounting.prepayment_details row with task_status=PENDING, prepayment_status=PENDING)
     ─ createPrepaymentChargeDetailsProcessor (writes mfi_accounting.prepayment_charge_details rows)
     ─ createDocumentProcessor + createPrepaymentDocumentDetailsProcessor (attached docs)
     ─ insertForeclosureInitiationSimDocumentEventsProcessor (queue SIM doc generation)
     ─ populateSIMDocumentPreProcessor
     ─ constructRequestForApprovalUsingApprovalTemplate
     ─ constructRequestForTaskCreationProcessor (task_type=LOAN_ACCOUNT_PREPAYMENT, current_status=UN_ASSIGNED, name='Loan Account Prepayment')
     ─ populateDataForRulesProcessor
     ─ createTaskWorkFlowHelpingProcessor (workflow_master_code=FORECLOSURE — creates the workflow row + task row in mfi_task)
     ─ updateLoanAccountStatusProcessor (loan_status → FORECLOSURE_FREEZE)
     ─ updateLoanStatusForSHGProcessor
     ─ callCollectionForBatchIdProcessor (if proceed=true)
     ─ updatePrepaymentTaskDetailsProcessor (sets task_id onto prepayment row, task_status=PENDING)
```

```
Stage 1 (Review) Approve → updateTaskWorkflow → loanPrepayment(VALIDATE)
  ─ validateLoanPrepaymentProduct + checkLoanAccountInterestAndPenalAccrual + validateLoanPrepaymentData
  ─ do_validate branch:
     ─ validateDateForForeclosureProcessor
  (no state change to prepayment_details; workflow advances stage)
```

```
Stage 2 (Approval) Approve → updateTaskWorkflow → loanPrepayment(APPROVE_TASK)
  ─ approve_task=true branch:
     ─ getPrepaymentDetailsProcessor (task_status=PENDING)
     ─ validateDateForForeclosureProcessor
     ─ populateLoanAccountCollectionRequestProcessor + callCollectionForBatchIdProcessor (mints challan via payments service)
     ─ getOfficeDetails (loan_office_id)
     ─ populateForeclosureReportAmountDataProcessor
     ─ insertForeclosureApproveDocumentEventsProcessor (queue CDS doc generation)
     ─ updatePrepaymentTaskDetailsProcessor → sets task_status=APPROVED, approved_on=now (for sequence=2 only — see populateTaskDetails) — although workflow continues to stage 3, the prepayment row is already flagged APPROVED at this point
     ─ deleteDraftProcessor
```

```
Stage 3 (Final Submission) Approve → updateTaskWorkflow → loanPrepayment(APPROVE_TASK, sequence=3)
  ─ approve_task=true branch (same processor list as stage 2):
     ─ populateForeclosureReportAmountDataProcessor
     ─ insertForeclosureApproveDocumentEventsProcessor
     ─ updatePrepaymentTaskDetailsProcessor — populateTaskDetails first-if branch (sequence=3 + channel=NOVOPAY) → task_status=APPROVED, attaches challan_number / receipt_number / merchant_id / cds_document_id / sim_document_id (via extractForeclosureDocumentDetails)
     ─ deleteDraftProcessor
  Task row in mfi_task is deleted (delete_task=true for sequence=3 + NOVOPAY).
```

```
Customer deposits at bank → bank sends callback → payments:updateSchedulePayment
  ─ updateSchedulePaymentProcessor → MfiCollectionsDAOService.updatePaymentDetails
     - Marks collection_reference_details.batch_status = DEPOSITED
     - Marks collection_payment_tracking_details.payment_status = DEPOSITED
  ─ pushCollectionUpdateToLLMS → branches on CollectionType
     - FORECLOSURE → pushLoanPrePaymentToLMS → calls accounting:loanPrepayment(APPROVE) async
```

```
loanPrepayment(APPROVE) / do_prepayment branch (deposit-driven, see line 2004 in loans_orc.xml):
  ─ fetchSuperDataForForeclosureProcessor + validateFinalPrepaymentProcessor
  ─ getPrepaymentDetailsProcessor (task_status=APPROVED) — reads the row prepared at stage 3
  ─ checkLoanAccountInterestAccrualBookingProcessor (book any pending accrual)
  ─ bookingNonPostedPenalProcessor (book pending penal accrual)
  ─ updateDueDetailsForPrepaymentProcessor
  ─ populateAdditionalAmountAndAccountDetailsForForeclosureProcessor
  ─ populateAmountComponentsForAppropriationProcessor
  ─ prepaymentApproppriationProcessor
  ─ <API id="postTransaction">    DR  CUSTOMER_AC      / CR  principal+interest+fc+tax
  ─ prePaymentGLCBSIntegrationProcessor
  ─ updateLoanAccountTaxDetailsExternalReferenceIdProcessor
  ─ updateLoanDueDetailsProcessor + updateLoanInstallmentDetailsProcessor
  ─ getLoanRepaymentModeDetailsProcessor + createLoanAccountPaymentsDetailsProcessor
  ─ populateLoanAutoClosureReqProcessor + loanAccountDpdCalcProcessor + checkMovementForPrincipalWaiver
  ─ loanAccountAssetCriteriaProcessor + loanAccountAssetClassificationProcessor (final DPD/asset state)
  ─ updateLoanAccountStatusProcessor (loan_status → CLOSED, account_status → CLOSED)
  ─ updateLoanStatusForSHGProcessor (stage=FINAL)
  ─ pushLoanAccountClosureDetailsProcessor + updateExcessAmountForPrepaymentProcessor
  ─ updatePrepaymentTaskDetailsProcessor (sets task_status=APPROVED, prepayment_status=APPROVED — see "Gotcha" below)
  ─ updateCollectionForClosureProcessor (notifies payments to close collection)
  ─ createLoanDueDetailsLoanAccountPaymentsDetailsProcessor + createLoanAccountClosureDetailsProcessor
  ─ (if child) callInternalOrchestrationProcessor → parentLoanAccountPartPrepayment
  ─ childLoanForeclosureEventGenerationProcessor (fires SHG/JLG event)
  ─ prepaymentSMSNotification
```

### Audit field semantics (mfi_accounting.prepayment_details)

| Field | Set when |
|---|---|
| `task_id` | createTaskWorkFlowHelpingProcessor (stage 0/initiation) |
| `task_status` | Maker initiation: PENDING. Stage 2 approve (sequence=2): APPROVED. Stage 3 approve (sequence=3 + NOVOPAY): APPROVED. Deposit (APPROVE/do_prepayment): APPROVED. REJECT path: REJECTED. |
| `prepayment_status` | Maker / stage 2 / stage 3: PENDING. Deposit (APPROVE/do_prepayment): APPROVED. REJECT: REJECTED. |
| `approved_on` | Stage 2 approve (sequence=2 + function_code=APPROVE_TASK) only. |
| `challan_number`, `receipt_number`, `merchant_id`, `challan_number_expiry_date` | Stage 3 approve (sequence=3 + channel=NOVOPAY + function_code=APPROVE_TASK) |
| `cds_document_id`, `sim_document_id` | Stage 3 approve via `extractForeclosureDocumentDetails` (reads `dbDocumentIdList` from context) |

### Gotcha — `UpdatePrepaymentTaskDetailsProcessor` IParam was historically ignored

Before [the SDCP-foreclosure-task-status fix], the processor **computed** `task_status` from `populateTaskDetails(taskId, sequence, channelCode, entity, isProceed, functionCode)` and silently fell back to `PENDING` when `function_code != "APPROVE"` AND `taskId != null` AND `sequence == null`. This caused the deposit-flow `task_status` to regress to PENDING because runtime processors in `do_prepayment` could leave `function_code` as something other than `APPROVE` when this processor was finally invoked. The XML `<IParam fieldName="task_status" value="APPROVED" />` was a lie — the processor ignored it.

The fix in [`UpdatePrepaymentTaskDetailsProcessor.java`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/prepayment/processor/UpdatePrepaymentTaskDetailsProcessor.java) reads the explicit `task_status` IParam after `populateTaskDetails` and overrides if present. This makes the XML the source of truth and is the pattern you should follow when wiring NEW prepayment stages.

If you see a closed loan with `prepayment_details.task_status='PENDING' AND prepayment_status='APPROVED' AND loan_status='CLOSED'`, it's a pre-fix row — safe to data-patch to `task_status='APPROVED'`.

## SHG / JLG variant

For a single member exit:
- `childLoanForeclosure` (dispatcher in `group_mfi_orc.xml:250`) → invokes `individualChildLoanForeclosure` per child
- Individual flow (lines 256-376) is the per-child version of the steps above
- Parent loan transitions to `FORECLOSURE_FREEZE_RSCH` while reschedule recomputes; subsequent `childLoanDisbursementCancellationParentRescheduling`-style reschedule restores parent

For the entire group exiting:
- One `childLoanForeclosure` call iterates all children
- After all children CLOSED, parent auto-closes

## DB writes summary

| Table | Change |
|---|---|
| `loan_account.loan_status` | FORECLOSURE_FREEZE → FORECLOSED → CLOSED |
| `loan_account.closing_date` | set to current business date |
| `loan_account_closure_details` | new row (closure type, charges, refund amount) |
| `loan_account_payments_details` | foreclosure payment row |
| `loan_account_charge_details` | foreclosure charge row |
| `loan_account_tax_details` | tax components |
| `loan_due_details` / `loan_installment_details` | all paid_amount / status updated to closed |
| `transaction_master` + `transaction_partition_details` | new foreclosure txn |
| `loan_account_noc_details` | NOC pending row |
| `audit_log` | framework auto |

## Failure modes → runbook

| Symptom | Likely cause |
|---|---|
| Loan stuck in `FORECLOSURE_FREEZE` | Approval pending, or checker action threw mid-pipeline |
| `loan_account_part_prepayment_details.task_id IS NULL` AND loan in FORECLOSURE_FREEZE (≤ 154b500c0) | Pre-154b500c0 swallow-and-return path in `CreateTaskWorkFlowHelpingProcessor` when `getCustomerDetails` / `getUserDetails` / `getBankEmployeeDetails` failed. Fixed on `mfi_integration_v3.2.8.4`+ (commit `154b500c0`). Existing orphans require the data patch in [`../runbooks/task-id-orphan-data-patch.md`](../runbooks/task-id-orphan-data-patch.md). |
| Loan stuck in `FORECLOSED` (not CLOSED) | Inline auto-closure failed; check `loanAccountClosure` batch |
| Trial balance off after foreclosure | foreclosure-charge GL or tax GL placeholder mis-bound; cross-link [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md) §9 |
| NOC not issued | `generateNocFileJob` last-run; check `loan_account_noc_details.status` |

## Reopening a closed loan

`loanAccountReopening` (or `childLoanReopening`) reverses the closure transaction, recomputes DPD/asset criteria, and flips `loan_status` back to ACTIVE. `closing_date` on `account` is *not* cleared — it keeps the original date as historical record. See [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md).

## Foreclosure QUOTE / simulation (the screen before initiation)

The "Loan Foreclosure" screen (Balanced Principal / Interest / Current+Future LPP / Foreclosure Fee / **CBC Fee**) is a **live quote**, computed on the fly — there is **no `prepayment_details` row yet** (that's only created on initiation; the post-initiation *view* is `getLoanForeclosureDetails` → `GetLoanForeclosureDetailsProcessor`, which reads `prepayment_details`/`prepayment_charge_details`). Don't confuse the two.

- **Request:** `fetchLoanForeclosureSimulationDetails` ([loans_orc.xml:3401](../../trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml)) → `FetchLoanForeclosureSimulationDetailsProcessor`. The maker/validate path computes the same quote via `ValidateLoanPrepaymentDataProcessor` under `loanPrepayment` DEFAULT.
- **Each charge line is resolved through the product scheme's price-setup**, not read raw. The charge code is resolved by `findPriceSetupCodeByProductSchemeIdAndCatalogueTypeAndSubType(schemeId, TYPE, DEFAULT)` against an **active** `product_scheme__transaction_catalogue__price_setup` mapping, then the matching outstanding `loan_due_details` rows are summed. If the mapping is missing/`is_deleted`, the line silently shows **0.00**.
- **CBC Fee** in particular is sourced from `loan_due_details` (charge_code = resolved CBC code, tenant = `SI_Fee`), **NOT** from `presentation_bounce_charge_details` (that's the SI bounce ledger, batch-only).
- Full chain + the "charge shows 0" failure mode: [`../accounting/charge-price-setup-resolution.md`](../accounting/charge-price-setup-resolution.md) · runbook [`../runbooks/charge-amount-shows-zero.md`](../runbooks/charge-amount-shows-zero.md) · `kg why fetchLoanForeclosureSimulationDetails`.

## Code anchors

- Individual: `loans_orc.xml::loanForeclosure`
- Group dispatcher: `group_mfi_orc.xml:250` (`childLoanForeclosure`)
- Per-child: `group_mfi_orc.xml:256-376` (`individualChildLoanForeclosure`)
- Closure tables: see [`../accounting/09-data-model.md`](../accounting/09-data-model.md)

## Where to dig deeper

- Loan lifecycle states: [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md)
- Maker-checker mechanics: [`maker-checker.md`](maker-checker.md)
- Posting engine: [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md)
