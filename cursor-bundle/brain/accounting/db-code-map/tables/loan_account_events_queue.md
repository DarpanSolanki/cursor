# `mfi_accounting.loan_account_events_queue`

> **The SHG/JLG fan-out queue.** When a parent loan does something that affects children (or vice-versa), the side-effect is enqueued here and replayed asynchronously by `childLoanEventProcessingBatchJob`.

## Purpose

Decouples parent-side flows from per-child fan-out. The parent flow commits its own state (parent loan, GL hit) synchronously, then enqueues per-child events. A separate batch job replays those events on each child.

This is the central mechanism for SHG/JLG. Misbehaviour here = silently broken group loans.

## Schema (live)

| Column | Type | Null? | Meaning |
|---|---|:-:|---|
| `id` | bigint | NOT NULL | PK |
| `parent_account_id` | bigint | NOT NULL | The parent loan's `account.id` |
| `event_type` | varchar | NOT NULL | One of 13 enum values: `CLB`, `CLMT`, `FCL`, `RSCH`, `REP`, `WAIVER`, `RSTCRE`, `REOPN`, `TXNREV`, `PRTPRE`, `REBK`, `CANCL`, `LEAR` |
| `event_status` | varchar | NOT NULL | `P` (pending) or `C` (completed) |
| `data` | text | NOT NULL | JSON array — one element per child to process |
| `event_id` | bigint | NULL | Server-generated correlation id |
| `is_deleted` | boolean | NOT NULL | Soft-delete |
| `created_on`, `updated_on` | timestamp | various | Standard audit |

(Run `tools/inspect-table.sh loan_account_events_queue` for the full column list with defaults.)

## JPA entity

[`account/loans/entity/LoanAccountEventsQueueEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java)

Defines two enums + two static maps:

- `EventType` (13 values, with descriptions): `CLB` (Child Loan Booking), `CLMT` (Child Loan Money Transfer), `FCL` (Foreclosure), `RSCH` (Reschedule), `REP` (Repayment), `WAIVER`, `RSTCRE` (Restructure), `REOPN` (Reopening), `TXNREV` (Txn Reversal), `PRTPRE` (Part Prepayment), `REBK` (Rebooking), `CANCL` (Cancellation), `LEAR` (Loan Excess Amount Refund)
- `EventStatus`: `P` / `C`
- `EVENT_TYPE_ORC_API_MAP` — `EventType.toString()` → orchestration Request name (e.g. `FCL` → `childLoanForeclosure`)
- `EVENT_TYPE_IGNORE_API_MAP` — types skipped by replayer (currently just `CLMT`)

## DAO

[`account/loans/repository/LoanAccountEventsQueueDAOService.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/repository/LoanAccountEventsQueueDAOService.java)

## Writers (per event type)

| Event type | Writer | Triggered by Request |
|---|---|---|
| `CLB` | [`CreateLoanAccountEventsProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/custom/mfi/disburse/processor/CreateLoanAccountEventsProcessor.java) and [`CreateClmtLoanAccountEventsProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/disbursement/processor/CreateClmtLoanAccountEventsProcessor.java) | `disburseLoan` PARENT_SUCCESS stage |
| `REP` | `loan/grouploan/repayment/...EventGenerationProcessor` | parent-level repayment that needs per-child reflection |
| `FCL` | `loan/grouploan/foreclosure/...` | parent-level foreclosure |
| `WAIVER` | `loan/grouploan/waiver/...` | |
| `RSTCRE` | `loan/grouploan/restructuring/...` | |
| `REOPN` | `loan/grouploan/reopening/...` | |
| `TXNREV` | [`ChildLoanTxnReversalEventGenerationProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/txnreversal/processor/ChildLoanTxnReversalEventGenerationProcessor.java) | `loanAccountTransactionReversal` |
| `PRTPRE` | [`ChildLoanPartPrepaymentEventGenerationProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/partprepayment/processor/ChildLoanPartPrepaymentEventGenerationProcessor.java) | `parentLoanAccountPartPrepayment` |
| `REBK` | [`ChildLoanRebookingEventGenerationProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/rebooking/processor/ChildLoanRebookingEventGenerationProcessor.java) | `loanAccountRebooking` |
| `CANCL` | [`ChildLoanCancellationEventGenerationProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/cancellation/processor/ChildLoanCancellationEventGenerationProcessor.java) | `loanDisbursementCancellation` |
| `LEAR` | `loan/grouploan/excessamountrefund/...` | parent excess refund |
| `CLMT` | `loan/grouploan/disbursement/...` | child money transfer (audit trail only — never replayed) |
| `RSCH` | inline | (no remap; handled inline) |

Each writer enqueues with `event_status='P'`.

## The replayer

[`ChildLoanEventsProcessingProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java) (called from `ChildLoanEventProcessingJobProcessor` / `ChildLoanEventProcessingItemProcessor`).

Behaviour:
1. `findAllByEventStatus("P")` — pulls every pending row.
2. Skips event types in `EVENT_TYPE_IGNORE_API_MAP` (currently `CLMT`).
3. For `CLB`: runs the mapped Request once with the full `event_array`.
4. For all other types: iterates the JSON array, runs the Request once per element.
5. Marks the event row `event_status = 'C'` on success.
6. **Catches all exceptions and only logs them** — failed events stay at `'P'` forever.

## Readers

| Reader | Triggered by |
|---|---|
| `ChildLoanEventsProcessingProcessor.findAllByEventStatus("P")` | `childLoanEventProcessingBatchJob` (every few minutes) |
| `GetLoanAccountDetailsProcessor` | reads pending events for the loan to surface in 360 view |

## Related Requests

- `childLoanEventProcessingBatchJob` (group_mfi_orc.xml:614) — the batch entry point that runs the replayer
- `childLoanBooking` (group_mfi_orc.xml:3) — wraps the replayer for synchronous CLB invocation
- The 12 `child*` Requests in group_mfi_orc.xml — replayed by event type

## Related flows

- [SHG/JLG group loan](../../../flows/shg-jlg-group-loan.md)
- Deep model: [`../../06-shg-jlg-group-loans.md`](../../06-shg-jlg-group-loans.md)
- Runbook: [`../../../runbooks/shg-jlg-children-missing.md`](../../../runbooks/shg-jlg-children-missing.md)

## Common diagnostic queries

```sql
-- All pending events, oldest first
SELECT id, parent_account_id, event_type, event_status, created_on,
       SUBSTRING(data FOR 200) AS data_preview
  FROM mfi_accounting.loan_account_events_queue
 WHERE event_status = 'P'
 ORDER BY created_on
 LIMIT 50;

-- Pending events for a specific parent
SELECT id, event_type, event_status, created_on
  FROM mfi_accounting.loan_account_events_queue
 WHERE parent_account_id = (SELECT id FROM mfi_accounting.account WHERE account_number = ?)
   AND event_status = 'P'
 ORDER BY id;

-- Oldest stuck event per parent (signal of broken fan-out)
SELECT parent_account_id, event_type,
       MIN(created_on) AS oldest_pending,
       NOW() - MIN(created_on) AS age
  FROM mfi_accounting.loan_account_events_queue
 WHERE event_status = 'P'
   AND created_on < NOW() - INTERVAL '1 hour'
 GROUP BY parent_account_id, event_type
 ORDER BY oldest_pending;

-- Event-type distribution (P vs C)
SELECT event_type, event_status, COUNT(*) FROM mfi_accounting.loan_account_events_queue
 GROUP BY 1,2 ORDER BY 1,2;
```

## Gotchas — read this section

1. **`CLMT` is ignored by design.** Listed in `EVENT_TYPE_IGNORE_API_MAP`. It exists for audit/trace; never replayed.
2. **Replayer catches all exceptions.** A bad row stays `P` forever. Only the application log shows what went wrong (around the batch run timestamp).
3. **Don't manually flip `event_status='C'` to clear stuck rows.** It suppresses the only signal that fan-out is broken. Either:
   - Fix the root cause and let the batch retry it (still at `P`), OR
   - If the row is bad data, soft-delete via `is_deleted=true` (don't fake completion).
4. **For `CLB`, `data` is the full JSON array of children, processed in one Request call.** For all other event types, `data` is iterated and the Request runs once per child.
5. **`childLoanEventProcessingBatchJob` runs every few minutes** in QA — frequency configured in `mfi_batch.batch_schedule`.
6. **The QA env (`mfi_qa3`) currently has stuck rows from 2024-10-16** — confirmed with `db-query.sh mfi_qa3 --canned 03-pending-event-queue`. These are real instances of the [shg-jlg-children-missing runbook](../../../runbooks/shg-jlg-children-missing.md) gap.
