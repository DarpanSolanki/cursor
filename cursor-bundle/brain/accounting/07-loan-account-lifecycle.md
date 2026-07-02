# 07 · Loan account lifecycle (status state machine, code-anchored)

> **Why this file:** debugging an LMS issue almost always starts with "what status is the loan in, and how did it get there?". The status enums and the transitions between them are scattered across entities, processors, and orchestration XMLs. This page is the single map.

---

## 1. Two enums, one table — `LoanStatus` vs `AccountStatus`

A loan account row in the `loan_account` table has **both**:

- `account.status` — the generic [`AccountStatus`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/common/entity/AccountEntity.java#L24): `ACTIVE`, `INACTIVE`, `CLOSED`, `CANCELLED`, `APPROVED`. This is what every Account (savings or loan) carries.
- `loan_account.loan_status` — the loan-specific [`LoanStatus`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java#L33): a 16-value enum that drives all servicing logic.

The two are kept in sync by a static map `LOAN_ACCOUNT_ACCOUNT_STATUS_MAP` in [AssetsConstants.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/common/AssetsConstants.java) — every `LoanStatus` write goes through `loanAccountEntity.setStatus(LOAN_ACCOUNT_ACCOUNT_STATUS_MAP.get(loanStatus))` so that the parent `account.status` reflects the right generic state.

**Always query `loan_account.loan_status` in SQL — `account.status` alone won't tell you whether a loan is in `FORECLOSURE_FREEZE` vs healthy `ACTIVE`.**

---

## 2. The full `LoanStatus` enum — every value with meaning

Source: [LoanAccountEntity.java:33-36](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java#L33-L36)

```java
public enum LoanStatus {
    APPROVED, ACTIVE, FORECLOSURE_FREEZE, WRITOFF, CLOSED,
    PART_PREPAYMENT_FREEZE, DISB_CNCL_FREEZE, DISB_CNCL,
    LOAN_REBKG_FREEZE, LOAN_RESTR_FREEZE,
    DEATH_FORECLOSURE_FREEZE, FORECLOSED,
    DEATH_FORECLOSURE_FREEZE_RSCH, DISB_CNCL_FREEZE_RSCH, FORECLOSURE_FREEZE_RSCH,
    LOCK
}
```

| Status | Meaning | Set by | Cleared by |
|---|---|---|---|
| `APPROVED` | Loan account row created (LAN assigned) but disbursement not yet posted to GL | [CreateLoanAccountProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/processor/CreateLoanAccountProcessor.java) (initial state during `disburseLoan` stage `LAN_CREATED`) | next `disburseLoan` stage when GL posts |
| `ACTIVE` | Loan booked, GL hit posted, accruing interest, eligible for repayment | end of `disburseLoan` happy path (function_sub_code progression, see §3) | any servicing action that locks it |
| `LOCK` | Generic short-lived lock used by `LmsMessageBrokerConsumer` to dedup concurrent disbursement attempts | inside the Kafka consumer just before processing | end of `executeServiceOrchestration` (success or failure) |
| `PART_PREPAYMENT_FREEZE` | Part-prepayment maker submitted, awaiting checker | `loanAccountPartPrepayment` Request (maker) | checker `APPROVE` or rejection |
| `LOAN_RESTR_FREEZE` | Restructuring proposed, awaiting approval | `LoanAccountRestructuring` family | approval / rejection |
| `LOAN_REBKG_FREEZE` | Rebooking proposed | `loanAccountRebooking` family | approval / rejection |
| `DISB_CNCL_FREEZE` | Disbursement-cancellation maker submitted | `loanDisbursementCancellation` (maker) | checker action |
| `DISB_CNCL_FREEZE_RSCH` | After child cancel approved, parent awaits repayment-schedule recompute | `childLoanDisbursementCancellationParentRescheduling` start | reschedule processor success |
| `DISB_CNCL` | Disbursement fully cancelled, account no longer accruing | end of `loanDisbursementCancellation` checker | terminal |
| `FORECLOSURE_FREEZE` | Foreclosure initiated, awaiting approval | `loanForeclosure` (maker) | checker action |
| `FORECLOSURE_FREEZE_RSCH` | After foreclosure approved on a child, parent awaits reschedule | child foreclosure parent-side processor | reschedule success |
| `FORECLOSED` | Foreclosure complete, full prepayment posted | end of foreclosure checker chain | terminal (becomes `CLOSED` after auto-closure) |
| `DEATH_FORECLOSURE_FREEZE` | Death-foreclosure initiated | `deathForeclosureInsuranceJob` family | insurance response (FTR/FTNR) |
| `DEATH_FORECLOSURE_FREEZE_RSCH` | Awaiting parent reschedule after death-fc on a child | child death-fc parent-side processor | reschedule success |
| `WRITOFF` | Loan written off | `loanWriteoff` Request after approval | terminal |
| `CLOSED` | Auto-closed (paid up to zero) or manually closed after foreclosure / writeoff / cancel | `loanAccountAutoClosureProcessor`, `loanAccountClosure` batch, `pushLoanAccountClosureDetailsProcessor` | terminal |

### `InactiveLoanStatus` — quick "can I service this?" check

Defined [LoanAccountEntity.java:38-57](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java#L38-L57). The static helper `InactiveLoanStatus.isInactive(LoanStatus)` returns true if the loan is in any of:

`FORECLOSURE_FREEZE`, `DISB_CNCL_FREEZE`, `LOAN_RESTR_FREEZE`, `LOAN_REBKG_FREEZE`, `DEATH_FORECLOSURE_FREEZE`, `PART_PREPAYMENT_FREEZE`, `CLOSED`, `DISB_CNCL`, `WRITOFF`.

Several validators (`valdiateLoanAccountNumberAndStatusProcessor`, `checkEligibleForRepaymentAppropriationProcessor`) gate their work on this — a loan in any of those statuses **cannot accept a new repayment**.

> Note: the *FREEZE_RSCH* variants and `FORECLOSED` are NOT in `InactiveLoanStatus`. That's deliberate — those are transient states between maker-checker steps that still expect downstream processors to keep running.

---

## 3. The `disburseLoan` state machine — driven by `function_sub_code`

`disburseLoan` is **not** a single end-to-end Request. Inside [mfi_orc.xml:4-200](../../novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml#L4) the Request branches on the `function_sub_code` field, and each branch sets a different combination of `IParam`s on a `dummyProcessor` that becomes the master switchboard for the rest of the orchestration. The 9 stages map to the disbursement journey:

```
DEFAULT  ─→  LAN_CREATED  ─→  LOAN_BOOKED  ─→  DTFC_SUCCESS  ─→
NEFT_STAGE_1_PENDING  ─→  NEFT_STAGE_1_SUCCESS  ─→  NEFT_STAGE_2_PENDING  ─→
REINITIATE_BANK  ─→  PARENT_SUCCESS

                                      └→  REJECT   (any failure path)
```

What each stage does (the IParam matrix in mfi_orc.xml is the source of truth — these are the deltas):

| Stage | Re-creates loan_account? | Re-generates schedule? | Calls bank? | Posts real GL? | Marks ACTIVE? |
|---|:--:|:--:|:--:|:--:|:--:|
| `DEFAULT` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `LAN_CREATED` | × | ✓ | ✓ | ✓ | ✓ |
| `LOAN_BOOKED` | × | × | ✓ | × | × |
| `DTFC_SUCCESS` | × | × | ✓ | × | × |
| `NEFT_STAGE_1_PENDING` | × | × | retry-only | × | × |
| `NEFT_STAGE_1_SUCCESS` | × | × | proceed to stage 2 | × | × |
| `NEFT_STAGE_2_PENDING` | × | × | retry-only | × | × |
| `REINITIATE_BANK` | × | × | ✓ (re-attempt) | × | × |
| `PARENT_SUCCESS` | × | × | × | × | ✓ + queues child CLB events |
| `REJECT` | × | × | × | × | sets `DISB_CNCL` |

### What advances the stage?

- The Kafka consumer pushes a fresh `disburseLoan` message with `function_sub_code` set per stage. Source-of-truth for the "what to send next" decision is in `accountingBankServiceRetryJob` (for bank stages) and the inline `*BankCallProcessor` flow ([loan/disbursement/bank/](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/bank/)).
- The `DISBURSEMENT_BLOCK_STATUSES` list in [LoanAccountEntity.java:59-63](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java#L59-L63) (`BANK_SUCCESS`, `LOAN_BOOKED`, `REINITIATE_BANK`, `NEFT_STAGE_1_PENDING`, `NEFT_STAGE_1_SUCCESS`, `NEFT_STAGE_2_PENDING`, `PARENT_SUCCESS`, `CHILD_SUCCESS`, `COMPLETED`) is the **disbursement_status** column on the loan_account row — it is *not* `LoanStatus`. Both progress in lock-step: `LoanStatus` is set to `ACTIVE` only when `disbursement_status` reaches `COMPLETED`.

### Practical implication

If you see a loan with `loan_status = APPROVED` and `disbursement_status` still `LOAN_BOOKED` for hours, the bank-call retry has stalled. Check `bank_service_call_retry` table and the `accountingBankServiceRetryJob` last execution.

---

## 4. State transitions — full graph (servicing actions)

Each arrow shows the orchestration Request that drives the transition. Maker-checker pairs collapse into a single arrow.

```
                         ┌────────────────────────────────────────┐
        Kafka            │  LOS publishes disburseLoan            │
        ──────────▶  consumer dedup (LOCK)                        │
                         ▼                                        │
                     APPROVED ──── disburseLoan stages ──▶ ACTIVE │
                                                              │   │
                       ┌──────────────────────────────────────┤   │
                       │                                      │   │
                       ▼                                      │   │
              loanRepayment / childLoanRepayment              │   │
              loanAdvanceRepayment                            │   │
                       │                                      │   │
                  (stays ACTIVE; DPD recomputed)              │   │
                       │                                      │   │
        ┌──────────────┼──────────────┬──────────────┬────────┘   │
        │              │              │              │            │
        ▼              ▼              ▼              ▼            │
 loanForeclosure  loanAccountPart  LoanAccount  loanDisburse-  loanWriteoff
 (maker)          Prepayment       Restructuring mentCancel-   (maker)
        │              │              │           lation           │
        ▼              ▼              ▼              ▼              ▼
 FORECLOSURE_   PART_PREPAY-    LOAN_RESTR_    DISB_CNCL_      stays ACTIVE
 FREEZE         MENT_FREEZE     FREEZE         FREEZE          until APPROVE
        │              │              │              │              │
   APPROVE        APPROVE        APPROVE        APPROVE         APPROVE
        ▼              ▼              ▼              ▼              ▼
 FORECLOSED ──   ACTIVE ──→     ACTIVE ──→      DISB_CNCL ──→   WRITOFF ──→
 auto-close      (new schedule  (new schedule   (terminal)      (terminal)
        │         applied)       applied)
        ▼
   CLOSED
```

### Death foreclosure adds one more row

`DEATH_FORECLOSURE_FREEZE` is set when the death-claim form is uploaded; `DEATH_FORECLOSURE_FREEZE_RSCH` is set on the parent loan when one child has gone into death-fc and the parent's schedule needs recomputation.

### Reopening reverses a closure

`childLoanReopening` (and `loanAccountReopening`) reverses the closure transaction, recomputes DPD/asset criteria, and **flips the status back to ACTIVE**. See [group_mfi_orc.xml:204-247](../../novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml#L204).

---

## 5. Where the status writes happen

| Status | Processor that writes it | File |
|---|---|---|
| `APPROVED` | `CreateLoanAccountProcessor` (initial value when `loan_status` IParam = "APPROVED") | [account/loans/processor/CreateLoanAccountProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/processor/CreateLoanAccountProcessor.java) |
| `ACTIVE` | `updateLoanAccountStatusProcessor` (called from `disburseLoan` `PARENT_SUCCESS` branch and from reopening flows) | grep `class UpdateLoanAccountStatusProcessor` |
| `LOCK` | `LmsMessageBrokerConsumer` (cache flag, not a DB write) | [consumers/LmsMessageBrokerConsumer.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java) |
| `*_FREEZE` family | each maker-side processor in `loan/<flow>/processor/` (e.g. `populateChildLoanWaiverDataProcessor`, `populateChildLoanDisbursementCancellationDataProcessor`) | per-flow |
| `CLOSED` | `loanAccountAutoClosureProcessor` (inline) and `loanAccountClosureService` (batch) | [batchnew/loanaccountclosure/LoanAccountClosureService.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/loanaccountclosure/LoanAccountClosureService.java) |
| `WRITOFF` | `loanWriteoff` Request — checker branch | grep `loanWriteoffProcessor` |
| `FORECLOSED` | inside `individualChildLoanForeclosure` chain — `updateLoanAccountStatusProcessor` with `loan_status=FORECLOSED` IParam | [group_mfi_orc.xml:343-346](../../novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml#L343) |

`updateLoanAccountStatusProcessor` is the central writer — it takes `IParam fieldName="loan_status" value="…"` from the orchestration and writes it both to `loan_account.loan_status` and (via `LOAN_ACCOUNT_ACCOUNT_STATUS_MAP`) to `account.status`.

---

## 6. Quick SQL to read the current state

```sql
-- Single loan
SELECT a.account_number,
       a.status               AS account_status,
       la.loan_status,
       la.disbursement_status,
       la.past_due_days,
       la.asset_criteria_slabs_id,
       la.parent_account_id
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE a.account_number = ?;

-- All children of a parent (SHG/JLG roster)
SELECT child.account_number, child.fraction, child.loan_status, child.disbursement_status
  FROM mfi_accounting.loan_account child
  JOIN mfi_accounting.account ca ON ca.id = child.account_id
 WHERE ca.parent_account_id = (
   SELECT pa.id FROM mfi_accounting.account pa
    WHERE pa.account_number = ?  -- parent LAN
 );

-- Pending child events for a parent
SELECT id, event_type, event_status, created_on
  FROM mfi_accounting.loan_account_events_queue
 WHERE parent_account_id = ? AND event_status = 'P'
 ORDER BY id;
```

---

## 7. Mistakes that recur because of this state machine

1. **Reading `account.status` instead of `loan_account.loan_status`** — `account.status` is `ACTIVE` for everything except `CLOSED/CANCELLED/INACTIVE`. It cannot tell you if the loan is in any FREEZE state.
2. **Assuming `LoanStatus.ACTIVE` ⇒ disbursed** — a parent can be ACTIVE while its CLB event is pending and children don't exist yet. Cross-check `disbursement_status = 'COMPLETED'`.
3. **Assuming a closed loan stays closed** — `loanAccountReopening` reverses the closure and writes back to `ACTIVE`. The `closing_date` column on `account` keeps the original date, but a re-opened loan's `loan_status` will read `ACTIVE`.
4. **Treating `FORECLOSED` as terminal** — it isn't in `InactiveLoanStatus`. The auto-closure step that follows transitions to `CLOSED`. If auto-closure failed, you'll see a loan stuck in `FORECLOSED` indefinitely.
5. **Forcing the status manually** — every `*_FREEZE` state is paired with a maker-checker draft and (often) a Task and an Audit row. Updating the status column directly leaves orphan drafts/tasks. Always go through the corresponding orchestration Request.
