# 10 · Accounting / LMS — debugging runbook

> **Purpose:** when a Trustt LMS issue lands ("loan stuck", "GL off", "child events not processing", "EOD didn't run") this is the playbook. Each scenario lists: symptoms → first SQL → likely cause → code/config to check → fix path. All references stay within `/home/darpan/darpan/`.

---

## 0. Prep — tenant & schema

Every issue is per-tenant. Confirm:
- The tenant code (e.g. `mfi`, `mfit1`).
- The schema is `mfi_accounting` (same name across tenants — the datasource URL differs).
- The branch you're reading is `mfi_integration_v3.2.8.4.1` (see [../workspace-state.md](../workspace-state.md)).

> Boundary rule: this runbook is **read-only diagnosis** from the darpan checkout. Any DB / Kafka / config change must be done in the appropriate target environment, not here.

---

## Scenario 1 — "Disbursement webhook fired but loan never went ACTIVE"

### Symptom
- LOS sent the disburse Kafka message; LMS log shows `LmsMessageBrokerConsumer` received it; but `loan_account.loan_status` is still `APPROVED` or no loan_account row exists.

### First SQL
```sql
SELECT a.account_number, la.loan_status, la.disbursement_status, la.created_on, la.updated_on
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE a.account_number = ? OR la.external_ref_number = ?;

SELECT * FROM mfi_accounting.bank_service_call_retry
 WHERE loan_account_id = ? ORDER BY id DESC LIMIT 5;

SELECT * FROM mfi_accounting.loan_disbursement_transaction
 WHERE loan_account_id = ? ORDER BY id DESC;
```

### Decision tree
1. **No `loan_account` row at all** → the consumer was skipped at `getDisburseSkipReason`. Check Redis ACCOUNTING db (index 5) for keys matching `*disburseLoan{productId}_{externalRefNumber}*` and `dl{...}`. If `dl…` exists, the previous attempt crashed before cleanup ([known gap, 05-flows.md §1](05-flows.md#1-disbursement-los--accounting-via-kafka)). Mitigation: delete the stale Redis key, replay the Kafka message.
2. **`loan_status = APPROVED`, `disbursement_status` in {`LAN_CREATED`, `LOAN_BOOKED`, `NEFT_STAGE_*`, `REINITIATE_BANK`}** → bank-call leg is mid-progress or stuck. Cross-check the disburseLoan state machine in [07-loan-account-lifecycle.md §3](07-loan-account-lifecycle.md#3-the-disburseloan-state-machine--driven-by-function_sub_code). Validate `accountingBankServiceRetryJob` is scheduled and ran recently in the batch service.
3. **`loan_status = APPROVED`, `disbursement_status = COMPLETED`** → impossible per the lock-step rule; suggests a partial commit. Read the most recent `audit_log` row for the loan; manual operator intervention required.

### Code to check
- [LmsMessageBrokerConsumer.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java) — the `getDisburseSkipReason` method names the four skip reasons.
- [mfi_orc.xml:4-200](../../novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml#L4) — the `function_sub_code` IParam matrix tells you which steps are gated for each stage.

---

## Scenario 2 — "SHG/JLG parent loan ACTIVE but no children created"

### Symptom
- Parent loan_account row is ACTIVE; `getChildLoanAccountList` returns empty.
- 360 view shows the group exists but no member-level loans.

### First SQL
```sql
-- Parent ID
SELECT id FROM mfi_accounting.account WHERE account_number = ? AND parent_account_id IS NULL;

-- Pending CLB events for that parent
SELECT id, event_type, event_status, created_on,
       SUBSTRING(data, 1, 200) AS data_preview
  FROM mfi_accounting.loan_account_events_queue
 WHERE parent_account_id = <parent_id> AND event_type = 'CLB';
```

### Likely causes
1. **CLB row exists with `event_status='P'`** → the `childLoanEventProcessingBatchJob` has not run, or it ran and the per-child Request threw. Per [06-shg-jlg-group-loans.md §2](06-shg-jlg-group-loans.md#2-the-event-queue--how-parent-dispatches-to-children), the processor catches all exceptions and only logs them, so the row stays at P forever. **Check the application log for a `ChildLoanEventsProcessingProcessor` ERROR around the relevant timestamp.**
2. **CLB row exists with `event_status='C'`** but no children → `bookChildLoanProcessor` failed silently, or the JSON `data` was empty. Inspect the JSON.
3. **No CLB row at all** → the parent disbursement never reached `PARENT_SUCCESS`, so `CreateClmtLoanAccountEventsProcessor` ([disbursement/processor/](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/disbursement/processor/CreateClmtLoanAccountEventsProcessor.java)) never ran. Treat as Scenario 1 instead.

### Fix path
- Manually re-fire `childLoanEventProcessingBatchJob` from the batch service (Request name `childLoanEventProcessingBatchJob`).
- After fixing the underlying error, mark stuck rows `event_status='P'` to retry.
- **Don't manually flip event_status='C'** without the children existing — it suppresses the only signal that fan-out is incomplete.

---

## Scenario 3 — "Repayment posted but customer says wrong amount went to interest vs principal"

### Symptom
- `loanRepayment` ran cleanly; trial balance fine; but the customer disputes how the money was allocated.

### First SQL
```sql
-- Latest payment record
SELECT * FROM mfi_accounting.loan_account_payments_details
 WHERE loan_account_id = ? ORDER BY id DESC LIMIT 5;

-- Per-component due rows at the time of payment (snapshot)
SELECT due_date, component_type, due_amount, paid_amount, waived_amount, current_paid_amount
  FROM mfi_accounting.loan_due_details
 WHERE loan_account_id = ? ORDER BY due_date, component_type;

-- The product's appropriation rule
SELECT lpac.* FROM mfi_accounting.loan_product_asset_criteria lpac
  JOIN mfi_accounting.loan_account la ON la.loan_product_id = lpac.product_id
                                    AND la.asset_criteria_slabs_id = lpac.asset_criteria_slabs_id
 WHERE la.id = (SELECT id FROM mfi_accounting.loan_account WHERE account_id = (SELECT id FROM mfi_accounting.account WHERE account_number = ?));
```

### Diagnose against [08-gl-posting-engine.md §7](08-gl-posting-engine.md#7-the-repayment-appropriation-step-preceeds-posting)

The four `comp*` columns in `loan_product_asset_criteria` are the precedence (1→2→3→4). The `liquidationOrder` column controls within-due ordering (`LIQ_INSTL` vs `LIQ_COMP` vs `LIQ_INSTL_CHRG_COMP`). Walk the algorithm by hand against the due rows; if the actual settled amounts don't match what the algorithm would produce, the bug is in either:

- The `loan_product_asset_criteria` row (master data wrong).
- The `asset_criteria_slabs_id` on the loan (wrong slab assigned — check NPA jobs).
- A stale due row (e.g. a billing job didn't run, so a missing INT row caused the engine to over-pay PRIN).
- `npa_ageing_start_date` non-null on the loan → the interest portion is shunted to suspense, customer-facing reports might show "INT 0, suspense 1500" which looks like under-payment.

---

## Scenario 4 — "Trial balance off — debits don't equal credits"

### Symptom
- `trialBalanceCalculation` for date D shows non-zero net.

### First SQL
```sql
SELECT business_date, gl_code, debit_amount, credit_amount,
       (debit_amount - credit_amount) AS net
  FROM mfi_accounting.trial_balance
 WHERE business_date = ? ORDER BY ABS(debit_amount - credit_amount) DESC LIMIT 50;

-- Drill into a suspect GL
SELECT tm.transaction_ref_no, tm.transaction_catalogue_id, tpd.account_number,
       tpd.cr_dr_indicator, tpd.amount, tpd.gl_code, tm.created_on
  FROM mfi_accounting.transaction_partition_details tpd
  JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_master_id
 WHERE tpd.gl_code = ?
   AND tm.created_on::date = ?
 ORDER BY tm.created_on;
```

### Likely causes (per [08-gl-posting-engine.md §9](08-gl-posting-engine.md#9-things-that-go-wrong-and-where-the-bug-lives))
1. A rule's debit and credit placeholder both resolve to the same internal account — sum to zero on that account but the *other* account in the pair shows imbalance.
2. A condition_expression used a value that wasn't populated (defaulted to zero or null) — only one leg posted.
3. A child-loan transaction posted with `is_child_account=false` — the leg that should have hit `CG…` GL hit the parent GL instead.

### Investigation steps
- Take the smallest-imbalance GL row first.
- Pull all `transaction_partition_details` for that GL on that date.
- For each, find the sibling row (same `transaction_master_id`, opposite `cr_dr_indicator`). The sibling tells you what the other side hit.
- Map the catalogue → rule list → placeholder bindings to verify expected behaviour.

---

## Scenario 5 — "EOD didn't run — `runEODJobs` never fired"

### Symptom
- Today's `interest_accrual_details` has no rows.
- `loan_account_derived_fields.business_date` is yesterday's, not today's.

### First check
- The batch service is **the scheduler** (see [03-batch-dependency.md](03-batch-dependency.md)). Look in `mfi_batch.batch_schedule` for `name = 'runEODJobs'` (or the per-job rows if the deployment uses individual schedules).
- Confirm the scheduler thread pool is alive — `AutoScheduler` + `ThreadPoolTaskScheduler` in `novopay-platform-batch`.
- `BatchExecutionContextHelper` populates the tenant; if the tenant resolution returned null, the job won't fire.

### If the schedule exists but nothing happened
- The batch service tried to call into accounting but got a 404 — common cause: `BatchJob.name` was renamed in the registry without a matching `<Request name="…">` rename in `mfi_orc.xml` / `loans_orc.xml`. Cross-check both names.
- Or accounting was up but the Request validators rejected `function_sub_code='BATCH'` / `op_code='RESTART'` (forced by `DirectJobExecutor`) — see [03-batch-dependency.md gotchas](03-batch-dependency.md#gotchas).

### If `runEODJobs` ran but a child job didn't
- `runEODJobs` is itself an orchestration that internally calls each step Request in sequence. Reading the orchestration block in `mfi_orc.xml` and the application log around the run timestamp will show which step exited early. Each step is a separate Spring Batch job — failures are surfaced in `batch_failure_audit` (per-row failures) and Spring Batch meta-tables (`BATCH_STEP_EXECUTION` for step-level status).

---

## Scenario 6 — "A loan is stuck in a `*_FREEZE` state"

### Symptom
- `loan_status` shows `FORECLOSURE_FREEZE` / `PART_PREPAYMENT_FREEZE` / `LOAN_RESTR_FREEZE` / etc. for an unreasonable time.

### First SQL
```sql
-- Open task for this loan (operator side)
-- (this is in mfi_task; query against the task service or its DB)

-- Audit trail for the maker action
SELECT * FROM mfi_audit.audit_log
 WHERE entity_type LIKE 'SEND_FOR_APPROVAL_%'
   AND new_data LIKE '%' || ? || '%'   -- account_number
 ORDER BY created_on DESC LIMIT 10;

-- Approval workflow rows
-- (in mfi_approval — query against the approval service)
```

### Decision tree
1. **Pending in approval** (`mfi_approval` shows a row in PENDING) → the checker has not yet APPROVE/REJECT'd. No action on accounting — push the operator.
2. **Approved in approval but loan still FREEZE** → the checker-side Request fired but failed mid-pipeline. Look in app logs for the relevant Request name (e.g. `loanForeclosure` with `function_code=APPROVE`) around the approval timestamp.
3. **No approval row** → maker-side Request failed before submitApplication ran. The loan is incorrectly stuck. Check `loan_account` audit row sequence.

### What NOT to do
- **Do not directly UPDATE `loan_status` back to ACTIVE.** Each FREEZE state is paired with a draft + workflow + (often) a Task row. Direct DB writes leave orphans that future flows then re-encounter.

---

## Scenario 7 — "DPD / NPA bucket looks wrong"

### Symptom
- A clearly-overdue loan is marked STD; or a paid-up loan is still SMA-1.

### First SQL
```sql
SELECT la.past_due_days, la.asset_criteria_slabs_id, la.npa_ageing_start_date,
       la.updated_on
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE a.account_number = ?;

SELECT MAX(business_date) FROM mfi_accounting.loan_account_derived_fields WHERE loan_account_id = ?;

-- Slab boundaries
SELECT acs.*  FROM mfi_accounting.asset_criteria_slabs acs
              JOIN mfi_accounting.loan_account la ON la.asset_criteria_slabs_id = acs.id
              WHERE la.id = ?;
```

### Likely causes
1. **`updated_on` is yesterday or older** → `loanAccountDpdCalcJob` / `loanAccountAssetCriteriaJob` / `loanAccountAssetClassificationJob` did not run for this loan today. Probably a batch failure — see Scenario 5.
2. **DPD looks right but slab is wrong** → `asset_criteria_slabs` ranges configured incorrectly (master data). Unusual but possible after a recent slab update.
3. **NPA bucket reverse-flowed**: when a payment cleared the overdue, `loanAccountAutoClosureProcessor` triggers `checkNPAReverseMovementRequiredProcessor` (visible in `childLoanRepayment` orchestration). If the reverse-movement check failed, the loan stays in NPA. Inspect that processor's logic for the loan in question.
4. **Manual override**: `bulkFileToSGAssetCriteriaGroupUpdateJob` allows ops to upload a CSV that overrides the slab. Check `file_staging_*` for recent rows.

---

## Scenario 8 — "Repayment from Payments service didn't reach LMS"

### Symptom
- `novopay-platform-payments` shows the collection processed; `loan_account_payments_details` has no matching row.

### Likely cause
Per [04-cross-module-deps.md](04-cross-module-deps.md), Payments calls `loanRepayment` (or `loanRepaymentInquiry` for a preview) over the gateway. Failure modes:

- Gateway routing wrong (Request `loanRepayment` should route to accounting). Validate the service registry.
- Maker-checker enabled on `loanRepayment` for this tenant → first call only created an approval draft; no settlement until the checker approves. Check `mfi_approval` for a row tagged `loanRepayment_submitApplication`.
- The collection record went through but failed validation in `checkEligibleForRepaymentAppropriationProcessor` (e.g. loan in `InactiveLoanStatus`). Check the response code returned to Payments.

---

## Scenario 9 — "Foreclosure ran but loan didn't auto-close"

### Symptom
- `loan_status = FORECLOSED` but no `CLOSED` transition.
- `loan_account_closure_details` has a partial row.

### Diagnose
- `individualChildLoanForeclosure` (group_mfi_orc.xml:256) ends with `loanAccountAutoClosureProcessor` then `pushLoanAccountClosureDetailsProcessor` then `createLoanAccountClosureDetailsProcessor`. If any of these threw, the chain aborted past `loanAccountStatusProcessor → FORECLOSED` but before `CLOSED`.
- For non-group flows, the equivalent chain is in the parent `loanForeclosure` Request in `loans_orc.xml` / `mfi_orc.xml`.

### Fix path
- Look for the exception in app logs.
- For child loans: `loanAccountClosure` batch job (scheduled via batch service) will retry auto-closure for any FORECLOSED-but-not-CLOSED rows on its next run. Confirm the job is scheduled.

---

## Scenario 10 — "I need to safely add a new transaction-catalogue + posting"

This is **not** a bug — it's a config-change runbook. Steps (touch only the right tables; no Java changes needed for the engine itself):

1. **Create or reuse `placeholder_master`** rows for any new symbolic accounts. Decide `is_actor_account` / `is_externally_passed_account` correctly — getting this wrong will route to the wrong account.
2. **Insert `transaction_catalogue`** row with the new code.
3. **Insert N `transaction_accounting_rule`** rows (one per leg) with: `sequence_number`, `source_amount`, `debit_account_placeholder`, `credit_account_placeholder`, `entry_type` (`TRANSFER` for plain transfer; `PRICE` for chargeable; `TAX` for tax; or anything that resolves to a `*Engine` Spring bean), `reference_code`, optional `condition_expression`.
4. **Insert `product_transaction_catalogue_placeholder`** rows for each `(product_id, transaction_catalogue_id, placeholder_code)` you need. Each row binds the placeholder to an `internal_account_definition_id` and a `gl_code`. Without these, the engine throws `134207`.
5. **Confirm `internal_account`** instances exist for every office that will use the catalogue. Without them, the engine throws `134182`.
6. **Test with `run_mode=TRIAL`** first against a sample loan; the engine returns the partition list without persisting.
7. **Then `run_mode=REAL`** for a single low-value loan; verify trial balance net = 0 for the affected GLs.

---

## Cross-reference — code anchors used here

- Disbursement state machine: [mfi_orc.xml:4-200](../../novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml#L4) + [LoanAccountEntity.java:33-72](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java#L33-L72)
- Kafka consumer: [LmsMessageBrokerConsumer.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java)
- Group event queue: [LoanAccountEventsQueueEntity.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java) + [ChildLoanEventsProcessingProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java)
- Repayment appropriation: [RepaymentApproppriationProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java)
- Posting engine: [ExecuteTransactionRulesProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java)
- `postTransaction` Request: [product_transaction_orc.xml:3-37](../../novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml#L3-L37)
- Group-loan flows: [group_mfi_orc.xml](../../novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml)
- Status sync: [AssetsConstants.LOAN_ACCOUNT_ACCOUNT_STATUS_MAP](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/common/AssetsConstants.java)
