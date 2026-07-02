# Flow — Disbursement, end-to-end

## Mental model

LOS publishes a Kafka event when CPDC + approval are complete. Accounting consumes it, runs the `disburseLoan` Request which is a **9-stage state machine** driven by `function_sub_code`. Bank NEFT call happens mid-stage with retry on stall. On success, accounting publishes a result event back to LOS. For SHG/JLG, per-child loan accounts are then created asynchronously by the event-queue replayer.

This is the canonical "money goes out" path. **Read [`../accounting/05-flows.md`](../accounting/05-flows.md) §1, [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md) §3, and the LOS-side [`../services/novopay-mfi-los.md`](../services/novopay-mfi-los.md) before this.**

## Services involved

| Service | Role |
|---|---|
| LOS | Triggers, consumes result, updates loan_app state |
| Kafka | Transport |
| accounting | The entire disbursement state machine |
| approval | Optional maker-checker (per tenant config) |
| dms | `verifyDocuments` — gates execution on KYC + agreement + NACH mandate |
| actor | `getCustomerDetails`, `getOfficeDetails`, `createActorAccountDetails` |
| Bank (external) | NEFT call out + callback |
| reporting / audit / notifications | Side effects |

## Step-by-step

### Phase 1 — LOS publishes

```
LOS:triggerDisburseLoan (after approval + CPDC)
  ▼
PrepareDisburseLoanAPIRequestService
  ├ assembles disburseLoan body (loan_app fields + child_account_list[] for SHG/JLG)
  └ DisburseLoanAPIUtil.publish:
       sets Redis dl<…> dedup key (DB 5)
       Kafka publish: topic disburse_loan_api_<tenant>
                      key   = disburseLoan{productId}_{externalRefNumber}
                      value = "disburseLoan|<json>|disburseLoan{productId}_{externalRefNumber}"
```

### Phase 2 — accounting consumes

```
LmsMessageBrokerConsumer.processConsumerRecord
  ▼
getDisburseSkipReason(externalRefNumber, productId, cacheKey, tenant):
  ├ if loan ACTIVE & disbursement_status=COMPLETED → ALREADY_ACTIVE → publish SUCCESS to los_lms_disbursement_sync, return
  ├ if loan in LOCK status → LOCK_LOAN_STATUS → return silently
  ├ if Redis "dl"+cacheKey already set → LOCK_CACHE_IN_PROGRESS → return silently
  └ else → NONE
  ▼
NovopayCacheClient.set("dl"+cacheKey, "true")  ← Redis ACCOUNTING DB 5
  ▼
executeServiceOrchestration ─ ServiceOrchestrator.executeProcessors("disburseLoan", ...)
```

### Phase 3 — the 9-stage state machine

Defined in `mfi_orc.xml:4-200`. Each stage is selected by `function_sub_code` and toggles a different `IParam` matrix on the master `dummyProcessor`. Per [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md) §3:

| Stage | Re-creates loan_account? | Re-generates schedule? | Bank call? | Real GL post? | ACTIVE? |
|---|:--:|:--:|:--:|:--:|:--:|
| `DEFAULT` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `LAN_CREATED` | × | ✓ | ✓ | ✓ | ✓ |
| `LOAN_BOOKED` | × | × | ✓ | × | × |
| `DTFC_SUCCESS` | × | × | ✓ | × | × |
| `NEFT_STAGE_1_PENDING` | × | × | retry-only | × | × |
| `NEFT_STAGE_1_SUCCESS` | × | × | proceed to stage 2 | × | × |
| `NEFT_STAGE_2_PENDING` | × | × | retry-only | × | × |
| `REINITIATE_BANK` | × | × | ✓ (re-attempt) | × | × |
| `PARENT_SUCCESS` | × | × | × | × | ✓ + queue child CLB events |
| `REJECT` | × | × | × | × | sets DISB_CNCL |

What happens inside `DEFAULT` (the "first time" path):

```
1. verifyDocuments → DMS (gate on KYC + agreement + NACH mandate)
2. disburseLoan_getLoanAccountDetails (self check)
3. disburseLoan_submitApplication (if maker_checker_enabled=1)
4. domain processors:
     - createOrUpdateLoanAccount (INSERT loan_account, status=APPROVED)
     - assign LAN (Loan Account Number)
     - generateRepaymentSchedule (loan_installment_details + loan_due_details)
     - outboundDisbursement<provider>InsuranceJob (if applicable)
     - bank NEFT call (or queue STP-bank retry)
5. postTransaction → GL hit:
     DR  internal_account(BANK_DISB_AC)   ₹X
     CR  internal_account(LOAN_PRIN_AC)   ₹X
6. CreateClmtLoanAccountEventsProcessor → INSERT loan_account_events_queue (CLB rows for children)
7. updateLoanAccountStatusProcessor → loan_status = ACTIVE
8. audit + notification
```

### Phase 4 — bank NEFT progression

If the bank call is async (STP), the Request returns at stage `LOAN_BOOKED` or `NEFT_STAGE_1_PENDING`. The `accountingBankServiceRetryJob` (scheduled by batch service) periodically:

```
SELECT * FROM bank_service_call_retry WHERE status='PENDING'
For each row:
  - re-call the bank service
  - on success: re-publish disburseLoan with function_sub_code = NEFT_STAGE_1_SUCCESS (or next)
  - on failure: increment retry count
```

The bank's NEFT callback hits gateway → `doGenericSyncSTPBankNEFNeftCallBack` (or `…NEINeftCallBack`) → re-fires `disburseLoan` with the next stage.

### Phase 5 — accounting publishes result

In `LmsMessageBrokerConsumer.finally`:

```
sendResultMessageToKafka(externRefNumber, isSuccess, exception)
  ─ topic: los_lms_disbursement_sync
  ─ payload: { external_ref_number, status, error_code?, error_message?, tenant_code, timestamp }
cleanupCacheKeys (delete dl<…> from Redis)
```

### Phase 6 — LOS consumes result

```
LOS:disbursementSyncConsumer (3 threads, critical)
  ─ updates los.loan_app + disburse_loan_process.disbursement_status
  ─ closes the disbursement task (task service)
  ─ may trigger downstream: NOC, document dispatch, customer notification
```

### Phase 7 — SHG/JLG child fan-out (separate cycle)

```
batch service fires childLoanEventProcessingBatchJob (every few minutes)
  ▼
ChildLoanEventsProcessingProcessor:
  ─ pulls loan_account_events_queue WHERE event_status='P'
  ─ for CLB events: invokes childLoanDisbursement once with full event_array
       bookChildLoanProcessor → INSERT each child loan_account
       splits parent EMI via GroupLoanUtility.getFinalAmountListUsingCarryOver
       per-child GL postings via postTransaction (gl_code prefixed "CG")
  ─ marks event row event_status='C'
```

See [`shg-jlg-group-loan.md`](shg-jlg-group-loan.md) for the deep version.

## DB writes summary

| Service | Tables |
|---|---|
| accounting | `account`, `loan_account`, `loan_installment_details`, `loan_due_details`, `loan_repayment_schedule_details`, `interest_accrual_details`, `transaction_master`, `transaction_partition_details`, `transaction_metadata`, `transaction_details`, `account_balance`, `loan_disbursement_transaction`, `loan_disbursement_charge_details`, `loan_disbursement_mode_details`, `loan_account_events_queue` (SHG/JLG), `bank_service_call_retry` (on async path) |
| LOS | `loan_app.disbursement_status`, `disburse_loan_process` |
| audit | `audit_log` (framework auto) |
| dms | `document_master.isVerified=true` |

## Failure modes → runbook

See [`../runbooks/disbursement-stuck.md`](../runbooks/disbursement-stuck.md) for the full playbook. Most common:

| Symptom | Cause | Fix |
|---|---|---|
| LOS sees no result event | Consumer crashed mid-flow; `dl<…>` Redis key still present | Delete the stale Redis key; replay Kafka |
| Loan stuck APPROVED with NEFT_STAGE_1_PENDING | Bank retry job failing | Check `bank_service_call_retry` last attempt; verify bank API health |
| Children missing for SHG/JLG | `childLoanEventProcessingBatchJob` failed silently | Check app log around batch run; reset event_status='P' to retry |
| Maker-checker pending forever | No checker action | Check `mfi_approval` for the application row |

## Code anchors

- LOS publish: [`DisburseLoanAPIUtil.java`](../../novopay-mfi-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java)
- Accounting consume: [`LmsMessageBrokerConsumer.java`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java)
- State machine XML: [`mfi_orc.xml:4-200`](../../novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml)
- LoanStatus: [`LoanAccountEntity.java:33`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java#L33)
- Disbursement_status block list: [`LoanAccountEntity.java:59-63`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java#L59-L63)
- LOS result consumer: `disbursementSyncConsumer` in [`MessageBroker.xml`](../../novopay-mfi-los/deploy/application/messagebroker/MessageBroker.xml)
- SHG/JLG fan-out: [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md)
