# 06 · SHG / JLG group loans (parent + child model)

> **Why this file:** the MFI business at Trustt is dominated by **SHG** (Self-Help Group) and **JLG** (Joint Liability Group) lending. The accounting service models these as a **parent loan account + N child loan accounts**, dispatched through a queue-based event mechanism that is not obvious from `01-overview.md` or `02-architecture.md`. Read this before touching anything in [`group_mfi_orc.xml`](../../novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml) or `in.novopay.accounting.loan.grouploan.*`.

---

## 1. The mental model

```
                       Group / Centre (SHG or JLG)
                                │
                    one parent loan_account (status=ACTIVE)
                                │
        ┌──────────┬────────────┼────────────┬──────────┐
        │          │            │            │          │
   child loan  child loan   child loan   child loan  child loan
   (member 1)  (member 2)   (member 3)   (member 4)  (member 5)
   parent_account_id = parent.id;  fraction = member share of EMI
```

- **One parent loan_account row** holds the *aggregate* SHG/JLG loan: total disbursed amount, master repayment schedule, GL postings.
- **N child loan_account rows** (one per group member) carry `parent_account_id = <parent.id>` and a `fraction` column representing each member's share of the parent EMI. Sum of fractions == 1.
- **`account.parent_account_id`** is the FK that wires the child to the parent ([AccountEntity.java:52](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/common/entity/AccountEntity.java#L52)).
- **`loan_account.fraction`** is the per-member share, used for installment-amount split. Allocation logic is in [GroupLoanUtility.getFinalAmountListUsingCarryOver](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/utility/GroupLoanUtility.java#L48) — splits an EMI across children proportionally with carry-over rounding so the **sum of child amounts equals the parent amount exactly** (line ~75 raises `NovopayFatalException("1111")` if it doesn't).

The parent is what gets disbursed and what posts to the GL. Children are *bookkeeping projections* that let collections, NPA tagging, and 360 views work per-member.

---

## 2. The event queue — how parent dispatches to children

When a servicing action happens on the parent (or on one child), the side-effects on the *other* child accounts are **not** executed inline. They are written to `loan_account_events_queue` and replayed asynchronously by a batch job.

### Schema — `loan_account_events_queue`

Mapped by [LoanAccountEventsQueueEntity.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java):

| Column | Purpose |
|---|---|
| `parent_account_id` | the parent loan_account.id this event belongs to |
| `event_type` | one of the codes below |
| `data` | JSON array of per-child payloads |
| `event_status` | `P` pending / `C` completed |
| `event_id` | server-generated correlation id |
| `is_deleted` | soft-delete flag |

### Event-type → orchestration-Request map

Defined in [LoanAccountEventsQueueEntity.java:50-66](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java#L50-L66):

| `event_type` | Description | Replays Request |
|---|---|---|
| `CLB` | Child Loan Booking | `childLoanDisbursement` |
| `CLMT` | Child Loan Money Transfer | *(ignored — see EVENT_TYPE_IGNORE_API_MAP)* |
| `FCL` | Foreclosure | `childLoanForeclosure` |
| `RSCH` | Reschedule | *(no remap — handled inline)* |
| `REP` | Repayment | `childLoanRepayment` |
| `WAIVER` | Waiver | `childWaiveLoanAccountCharges` |
| `RSTCRE` | Restructuring | `childLoanRestructuring` |
| `REOPN` | Reopening | `childLoanReopening` |
| `TXNREV` | Transaction Reversal | `childLoanTransactionReversal` |
| `PRTPRE` | Part Prepayment | `childLoanPartPrepayment` |
| `REBK` | Rebooking | `childLoanRebooking` |
| `CANCL` | Disbursement Cancellation | `childLoanDisbursementCancellation` |
| `LEAR` | Loan Excess Amount Refund | `childLoanAccountExcessAmountRefund` |

### Replayer — `childLoanEventProcessingBatchJob`

`mfi_batch.batch_job` row with `name='childLoanEventProcessingBatchJob'` is scheduled by the batch service (see [03-batch-dependency.md](03-batch-dependency.md)). It hits Request `childLoanEventProcessingBatchJob` ([group_mfi_orc.xml:614-618](../../novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml#L614-L618)) → `childLoanEventProcessingJobProcessor` → which is the wrapper around [ChildLoanEventsProcessingProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java).

The processor:
1. `findAllByEventStatus("P")` — pulls every pending event ([line 39](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java#L39))
2. Skips event types in `EVENT_TYPE_IGNORE_API_MAP` (only `CLMT` today)
3. For `CLB` events, runs the mapped Request **once with the full JSON array** in `event_array`
4. For all other event types, **iterates** the JSON array and runs the Request **once per child element**, putting each child's fields into the ExecutionContext via `executionContext.putAll(indChildJsonData)`
5. Resolves the Request via `OrchestrationXMLParser.getRequestFromOrcXML(tenant, eventTypeOrcApiMap[type])` and runs it through `ServiceOrchestrator.executeProcessors(...)`
6. Marks the event row `event_status = 'C'` on success
7. **Catches all exceptions and only logs** ([line 70-72](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java#L70-L72)) — a failed child event stays at `P` forever unless someone resets it. **This is the main way SHG/JLG state goes "stuck".**

### Who *writes* to the queue?

Events are populated by per-flow `*EventGenerationProcessor` / `*EventsQueueDataPopulator` classes (one per servicing flow):

| Flow | Generator | Populator |
|---|---|---|
| Child cancellation | [ChildLoanCancellationEventGenerationProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/cancellation/processor/ChildLoanCancellationEventGenerationProcessor.java) | [ChildLoanCancellationEventsQueueDataPopulator.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/cancellation/service/ChildLoanCancellationEventsQueueDataPopulator.java) |
| Child rebooking | [ChildLoanRebookingEventGenerationProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/rebooking/processor/ChildLoanRebookingEventGenerationProcessor.java) | [ChildLoanRebookingEventsQueueDataPopulator.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/rebooking/service/ChildLoanRebookingEventsQueueDataPopulator.java) |
| Child part-prepayment | [ChildLoanPartPrepaymentEventGenerationProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/partprepayment/processor/ChildLoanPartPrepaymentEventGenerationProcessor.java) | [ChildLoanPartPrepaymentEventsQueueDataPopulator.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/partprepayment/service/ChildLoanPartPrepaymentEventsQueueDataPopulator.java) |
| Child txn reversal | [ChildLoanTxnReversalEventGenerationProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/txnreversal/processor/ChildLoanTxnReversalEventGenerationProcessor.java) | [ChildLoanTransactionReversalEventsQueueDataPopulator.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/txnreversal/service/ChildLoanTransactionReversalEventsQueueDataPopulator.java) |

The pattern: the **inline flow on the parent** runs synchronously and posts the parent-side GL hit; the **child fan-out is queued** so that (a) the synchronous call returns fast, and (b) child failures don't roll back the parent.

---

## 3. Request inventory — `group_mfi_orc.xml`

| Request | What it does | Notes |
|---|---|---|
| `childLoanBooking` | Wraps a `childLoanEventsProcessingProcessor` invocation — pull + replay pending CLB events | one-liner orchestration |
| `getChildLoanAccountList` | List children of a parent loan account | read-only |
| `childLoanRepayment` | Apply a single child's share of a repayment: appropriation → due updates → `postTransaction` → optional auto-closure | inline. NPA-reverse and auto-closure hooks present (`checkNPAReverseMovementRequiredProcessor`, `loanAccountAutoClosureProcessor`) |
| `childWaiveLoanAccountCharges` | Apply waiver to one child | populates child row, updates due + waiver tables |
| `childLoanRestructuring` | Restructure one child loan | optional `loanAdvanceRepaymentProcessor` post-step |
| `childLoanReopening` | Reverse a closure on one child | reverses transaction, recalcs DPD/asset criteria, replays non-posted penal |
| `childLoanForeclosure` | Trigger child foreclosure | wraps `individualChildLoanForeclosure` per child |
| `individualChildLoanForeclosure` | Per-child foreclosure: validate → fetch super-data → create prepayment + charge details → bookings → `postTransaction` → auto-closure → notification | longest single Request in the file (~120 lines) |
| `childLoanTransactionReversal` | Reverse a child txn, recompute DPD/asset criteria | |
| `childLoanPartPrepayment` | Inline child part-prepayment when triggered from the parent flow | calls `childLoanRestructuringProcessor` first |
| `parentLoanAccountPartPrepayment` | Parent-side part-prepayment that then queues per-child events | uses `registerLoanAccountRescheduleEventProcessor` + `loanAccountRescheduleBatchProcessor` |
| `childLoanDisbursementCancellation` | Cancel one child's disbursement; reverse GL hit; update due/installment | calls `postTransaction` |
| `childLoanDisbursementCancellationParentRescheduling` (`explicitTxnMgmt="true"`) | After child cancel, recompute parent's repayment schedule | uses `customCallRepaymentScheduleGenerateProcessor` |
| `childLoanAccountExcessAmountRefund` | Refund excess to one child + post the reverse txn | |
| `childLoanDisbursement` | Internal — per-child book leg of a CLB event | calls `bookChildLoanProcessor` |
| `childLoanEventProcessingBatchJob` | The batch entry point — runs the queue replayer | scheduled by mfi_batch.batch_job |
| `childLoanRebooking` | Rebook a child after major change (save adjustment, restructure, then post adjustment txn) | three processors in sequence |
| `childLoanRebookingAdjustmentTransaction` | The actual `postTransaction` leg of a rebooking | |
| `updateChildLoanDisbursementStatus` | Update one child's disbursement_status (used during STP staging) | |

---

## 4. Concrete flow — Group Loan Disbursement (SHG / JLG)

This is the canonical SHG/JLG path. Use it to anchor every other group-flow discussion.

```
LOS publishes disburseLoan to Kafka (per-tenant topic disburse_loan_api_<tenant>)
  body includes:  parent loan_account fields + child_account_list[]
  (each entry = { external_ref_number, fraction, customer_id, ... })

──────────────────────────────────────────────────────
Path A — Parent leg (synchronous within the consumer)
──────────────────────────────────────────────────────
LmsMessageBrokerConsumer.processConsumerRecord  (loans_orc/mfi_orc → disburseLoan)
  ▼
mfi_orc.xml :: <Request name="disburseLoan" isAsync="true" explicitTxnMgmt="true">
  ▼  (function_sub_code drives a 9-stage state machine — see 02-architecture.md
      and the IParam matrix in mfi_orc.xml lines 60-200)
  Stages: DEFAULT → LAN_CREATED → LOAN_BOOKED → DTFC_SUCCESS
        → NEFT_STAGE_1_PENDING → NEFT_STAGE_1_SUCCESS → NEFT_STAGE_2_PENDING
        → REINITIATE_BANK → PARENT_SUCCESS → REJECT
  ▼
  At PARENT_SUCCESS: parent loan_account is ACTIVE, parent GL hit posted
  ▼
  CreateClmtLoanAccountEventsProcessor writes per-child CLB events to loan_account_events_queue
    ([CreateClmtLoanAccountEventsProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/disbursement/processor/CreateClmtLoanAccountEventsProcessor.java))

──────────────────────────────────────────────────────
Path B — Child fan-out (asynchronous, batch-driven)
──────────────────────────────────────────────────────
Scheduler fires childLoanEventProcessingBatchJob (default cadence: every few minutes,
  configured in mfi_batch.batch_schedule)
  ▼
ChildLoanEventsProcessingProcessor pulls every event row with event_status='P'
  ▼
  For event_type='CLB' (one row per parent), executes Request `childLoanDisbursement`
    once with the full event_array (because CLB is a bulk per-parent event)
  ▼
  childLoanDisbursement → populateDataForChildLoanBookingProcessor → bookChildLoanProcessor
    creates each child loan_account row (parent_account_id = parent.id, fraction set)
    splits the parent installment via GroupLoanUtility.getFinalAmountListUsingCarryOver
    inserts per-child loan_installment_details / loan_due_details
  ▼
  Marks the parent CLB event row event_status='C'
```

### What this means for ops

- A SHG/JLG disbursement is **never atomic across parent + children**. Parent and children commit in separate transactions.
- A parent in `ACTIVE` with **no child rows** = the CLB event is stuck at `P`. Check `loan_account_events_queue WHERE parent_account_id=? AND event_type='CLB'`.
- A repayment posted to the parent does **not** automatically split to children inline — it goes through queue event `REP` and gets fanned out by the same batch job.

---

## 5. Common SHG/JLG-only edge cases (with code anchors)

### 5a. Member-level NPA promotion (one bad member, rest healthy)

NPA tagging runs per-account in `loanAccountAssetClassificationJob`. A child can be SMA-2 while siblings are STD because each child has its own DPD count derived from its share of due. **The parent's DPD is the max across children** — see [`loan_account.pastDueDays`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java#L98) and the per-account computation inside `batchnew/derivedfields`.

### 5b. Carry-over rounding — child amounts may be off by ±1 paisa

[GroupLoanUtility.java:48-82](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/utility/GroupLoanUtility.java#L48) does the per-child split. The last child absorbs the rounding residue (`isLastItem` branch). If child fractions are unusual (e.g., `0.333… × 3`), the last child's installment will be 1 paisa larger than the others — **this is intentional and not a bug**.

### 5c. Child cancellation forces a parent reschedule

`childLoanDisbursementCancellation` does not change the parent installment. The follow-up `childLoanDisbursementCancellationParentRescheduling` Request (`explicitTxnMgmt="true"`) is what calls `customCallRepaymentScheduleGenerateProcessor` to redraw the parent schedule. If only the cancel ran and the reschedule did not, the parent's repayment schedule will be inflated by the cancelled child's share.

### 5d. CLMT events — the only ignored type

`CLMT` (Child Loan Money Transfer) is in `EVENT_TYPE_IGNORE_API_MAP`. It is written to the queue for trace purposes but never replayed by the batch job. If a downstream report needs it, it must read the queue table directly.

### 5e. `childLoanForeclosure` vs `individualChildLoanForeclosure`

- `childLoanForeclosure` (group_mfi_orc.xml:250) is the **dispatcher** — its only processor is `childLoanForeclosureProcessor` which iterates the children and invokes the individual one.
- `individualChildLoanForeclosure` (group_mfi_orc.xml:256) does the actual per-child work — booking, txn posting, auto-closure, notification.

If you grep for `<Request name="childLoanForeclosure">`, both match — make sure you are reading the dispatcher, not the individual one. The individual one is ~120 lines; the dispatcher is ~5.

---

## 6. Where each piece of code lives

| Concern | Path |
|---|---|
| Parent-account entity (`account.parent_account_id`) | [account/common/entity/AccountEntity.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/common/entity/AccountEntity.java) |
| Child-loan entity (specialisation, `fraction`) | [account/loans/entity/LoanAccountEntity.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java) |
| Event-queue entity + type map | [account/loans/entity/LoanAccountEventsQueueEntity.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java) |
| Replayer | [loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java) |
| EMI splitter (carry-over) | [loan/grouploan/utility/GroupLoanUtility.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/utility/GroupLoanUtility.java) |
| Per-flow event generators | `loan/grouploan/<flow>/processor/*EventGenerationProcessor.java` |
| Per-flow queue populators | `loan/grouploan/<flow>/service/*EventsQueueDataPopulator.java` |
| Group rebooking validator/executor | [loan/rebooking/group/processor/](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/rebooking/group/processor/) |
| Orchestration XML | [deploy/application/orchestration/group_mfi_orc.xml](../../novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml) (687 lines) |

---

## 7. What this file deliberately does NOT cover

- The **LOS-side** SHG/JLG concepts (centre/group master, member onboarding, DDE, BET, BPM workflow). Those live in `novopay-mfi-los`. This file is the **accounting view** of the same loan.
- Insurance (death-foreclosure, disbursement insurance) is per-child but is described in [05-flows.md §3](05-flows.md) and in `loans_insurance_orc.xml`.
- The **GL-hit derivation** for child transactions — that is in [08-gl-posting-engine.md](08-gl-posting-engine.md). The relevant bit there: `is_child_account=true` causes `glCode = ChildGeneralLedgerEntity.CHILD_GL_CODE_PREFIX + glCode` ([ExecuteTransactionRulesProcessor.java:391-393](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java#L391-L393)).
