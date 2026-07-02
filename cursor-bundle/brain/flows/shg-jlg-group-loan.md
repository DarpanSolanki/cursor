# Flow — SHG / JLG group loan, end-to-end

## Mental model

A SHG/JLG loan is **one parent loan_account + N child loan_accounts**. Parent is what gets disbursed and what posts to the GL. Children are bookkeeping projections that let collections, NPA, and 360 views work per-member. Children are **never created inline** — they're queued in `loan_account_events_queue` and replayed by `childLoanEventProcessingBatchJob`.

> This is the cross-service version. The deep LMS-only version is [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md). Read that first.

## Services involved

| Service | Role |
|---|---|
| LOS | Group formation (FLCC), per-member application, group-level eligibility, disbursement trigger with `child_account_list[]` |
| accounting | Parent loan creation, parent GL hit, child event queue, async child loan creation, per-child posting |
| batch | Schedules `childLoanEventProcessingBatchJob` (every few minutes) |
| payments | Per-member collection capture |
| actor | Group / meeting-centre / member master |

## Lifecycle, end-to-end

```
GROUP FORMATION (LOS)
  ─ each member onboarded individually (see customer-onboarding.md)
  ─ createOrUpdateGroup, updateGroupSignatories
  ─ eligibility checks: processGroupFormationEligibilityRules
  ─ FLCC + meeting centre allocation

LOAN APPLICATION (LOS, per group)
  ─ same stages as individual but variant: LOAN_JLG / LOAN_SHG
  ─ child_account_list[] built — one per member with fraction (sum=1)

DISBURSEMENT TRIGGER (LOS)
  ─ Kafka publish disburse_loan_api_<tenant>
  ─ payload includes parent loan fields + child_account_list[]

ACCOUNTING — PARENT LEG (sync within Kafka consumer)
  ─ disburseLoan state machine progresses to PARENT_SUCCESS
  ─ parent loan_account inserted, parent GL hit posted
  ─ CreateClmtLoanAccountEventsProcessor enqueues CLB event
       INSERT loan_account_events_queue (
         parent_account_id = parent.id,
         event_type        = 'CLB',
         event_status      = 'P',
         data              = JSON array of children
       )

ACCOUNTING — CHILD FAN-OUT (async, batch-driven)
  ─ childLoanEventProcessingBatchJob fires (every few minutes)
  ─ ChildLoanEventsProcessingProcessor:
       finds rows event_status='P', skips EVENT_TYPE_IGNORE_API_MAP types (CLMT)
       for CLB: invokes childLoanDisbursement once with full event_array
            populateDataForChildLoanBookingProcessor
            bookChildLoanProcessor:
              ─ INSERT each child loan_account (parent_account_id + fraction)
              ─ split parent EMI via GroupLoanUtility.getFinalAmountListUsingCarryOver
              ─ INSERT per-child loan_installment_details / loan_due_details
              ─ per-child GL postings via postTransaction (gl_code prefixed "CG")
       marks event row event_status='C'

SERVICING — per-member events queue back to siblings
  ─ each child action (REP, FCL, WAIVER, RSTCRE, REOPN, TXNREV, PRTPRE, REBK, CANCL, LEAR)
    fires its individual orchestration Request inline
  ─ side-effects on the OTHER children/parent enqueue events of the same type
  ─ batch replayer picks them up and dispatches each
```

## The 13 event types

(per [`LoanAccountEventsQueueEntity.java:50-66`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java#L50-L66))

| event_type | Description | Replays |
|---|---|---|
| `CLB` | Child Loan Booking | `childLoanDisbursement` |
| `CLMT` | Child Loan Money Transfer | (ignored — `EVENT_TYPE_IGNORE_API_MAP`) |
| `FCL` | Foreclosure | `childLoanForeclosure` |
| `RSCH` | Reschedule | (no remap — handled inline) |
| `REP` | Repayment | `childLoanRepayment` |
| `WAIVER` | Waiver | `childWaiveLoanAccountCharges` |
| `RSTCRE` | Restructuring | `childLoanRestructuring` |
| `REOPN` | Reopening | `childLoanReopening` |
| `TXNREV` | Transaction Reversal | `childLoanTransactionReversal` |
| `PRTPRE` | Part Prepayment | `childLoanPartPrepayment` |
| `REBK` | Rebooking | `childLoanRebooking` |
| `CANCL` | Disbursement Cancellation | `childLoanDisbursementCancellation` |
| `LEAR` | Loan Excess Amount Refund | `childLoanAccountExcessAmountRefund` |

## Critical invariants

1. **Sum of child fractions == 1**. `GroupLoanUtility.getFinalAmountListUsingCarryOver` raises `NovopayFatalException("1111")` if the per-child split doesn't add to the parent amount. Carry-over rounding pushes the residue to the **last child** — by design.
2. **Parent and children commit in separate transactions.** A parent in `ACTIVE` with no children = the CLB event is stuck.
3. **Child GL hits use the `CG` prefix.** Set `is_child_account=true` in the ExecutionContext so [`ExecuteTransactionRulesProcessor.java:391-393`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java#L391-L393) prefixes `gl_code = "CG" + glCode`.
4. **Member-level NPA is independent.** A child can be SMA-2 while siblings are STD; parent's DPD = max across children.
5. **`ChildLoanEventsProcessingProcessor` catches all exceptions and only logs them.** Failed child events stay at `'P'` forever unless someone resets them. **This is the main failure mode.**
6. **`childLoanForeclosure` (dispatcher) vs `individualChildLoanForeclosure` (per-child)** — both match the same grep; check which one you're reading.

## DB writes summary

| Table | Notes |
|---|---|
| `account` | parent + N children rows; child rows have `parent_account_id = parent.id` |
| `loan_account` | parent + N children; children have `fraction` set |
| `loan_installment_details` / `loan_due_details` | parent + per-child sets |
| `loan_account_events_queue` | One CLB row at parent disbursement; per-event-type rows for servicing fan-out |
| `transaction_partition_details` | parent rows with normal `gl_code`; child rows with `CG`-prefixed `gl_code` |
| `child_general_ledger` | child GL master (auto-created from parent GL via `ChildGeneralLedgerEntity.mapToChild`) |

## Failure modes → runbook

See [`../runbooks/shg-jlg-children-missing.md`](../runbooks/shg-jlg-children-missing.md).

## Code anchors

- Event-queue entity + type map: [`LoanAccountEventsQueueEntity.java`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java)
- Replayer: [`ChildLoanEventsProcessingProcessor.java`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java)
- EMI splitter: [`GroupLoanUtility.java`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/utility/GroupLoanUtility.java)
- Orchestration: [`group_mfi_orc.xml`](../../novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml) (687 lines)
- Per-flow generators: `loan/grouploan/<flow>/processor/*EventGenerationProcessor.java`
- Per-flow populators: `loan/grouploan/<flow>/service/*EventsQueueDataPopulator.java`

## Where to dig deeper

- LMS-only deep version: [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md)
- LOS-side group formation: [`customer-onboarding.md`](customer-onboarding.md) §"Group formation"
- Disbursement: [`disbursement-end-to-end.md`](disbursement-end-to-end.md)
