# SHG/JLG fan-out → tables touched

Flow narrative: [`../../../flows/shg-jlg-group-loan.md`](../../../flows/shg-jlg-group-loan.md)
Deep model: [`../../06-shg-jlg-group-loans.md`](../../06-shg-jlg-group-loans.md)

The fan-out is asynchronous: parent flow enqueues an event in `loan_account_events_queue`; batch job replays it on each child.

## Phase 1 — Parent flow enqueues (synchronous, within parent Request)

| Step | Table | Action | Processor |
|---|---|---|---|
| 1 | (parent flow does its own writes — see disbursement.md, repayment.md, foreclosure.md) | | |
| 2 | `loan_account_events_queue` | INSERT (event_type per the fan-out kind, event_status='P', data=JSON array of children) | `Create*EventGenerationProcessor` per flow (see [loan_account_events_queue.md writers](../tables/loan_account_events_queue.md#writers)) |

## Phase 2 — Batch replay (async, every few minutes)

Triggered by `childLoanEventProcessingBatchJob` schedule.

| Step | Table | Action | Processor |
|---|---|---|---|
| 3 | `loan_account_events_queue` | SELECT WHERE event_status='P' | `ChildLoanEventsProcessingProcessor` |
| 4 | (per event row) — invokes the mapped Request from `EVENT_TYPE_ORC_API_MAP`: `childLoanDisbursement`, `childLoanRepayment`, `childLoanForeclosure`, etc. | runs the per-child orchestration | |
| 5 | `loan_account_events_queue.event_status` | UPDATE 'C' (on success) | `ChildLoanEventsProcessingProcessor` |

## Per-event-type child writes (representative)

### `CLB` (Child Loan Booking) — most complex

For each child (in `data` JSON array):
| Table | Action | Processor |
|---|---|---|
| `account` | INSERT (child) | `bookChildLoanProcessor` (`parent_account_id` set to parent's id) |
| `loan_account` | INSERT (child, with `fraction` column) | `bookChildLoanProcessor` |
| `loan_installment_details` | INSERT (child's per-installment, split via `GroupLoanUtility.getFinalAmountListUsingCarryOver`) | `bookChildLoanProcessor` |
| `loan_due_details` | INSERT (child's per-component) | `bookChildLoanProcessor` |
| `transaction_master` | INSERT (per-child GL hit via `<API id="postTransaction">`) | `CreateTransactionMasterProcessor` |
| `transaction_partition_details` | INSERT N legs with `CG`-prefixed `gl_code` | `ExecuteTransactionRulesProcessor` (with `is_child_account=true`) |

### `REP`, `FCL`, `WAIVER`, etc. — per-child orchestration

Each child in `data` triggers the mapped child Request (e.g. `childLoanRepayment`). That Request follows the [repayment](repayment.md) / [foreclosure](foreclosure.md) flow but scoped to the child loan. All writes are `is_child_account=true` → CG-prefixed GLs.

## The "stuck row" failure mode

`ChildLoanEventsProcessingProcessor` catches all exceptions and only logs ([source](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java#L70-L72)). A failed row stays at `event_status='P'` forever.

**Diagnostic:** [`db-tools/canned-queries/03-pending-event-queue.sql`](../../../db-tools/canned-queries/03-pending-event-queue.sql)
**Runbook:** [`../../../runbooks/shg-jlg-children-missing.md`](../../../runbooks/shg-jlg-children-missing.md)

## Cross-references

- Event queue table: [`../tables/loan_account_events_queue.md`](../tables/loan_account_events_queue.md)
- Disbursement (parent): [disbursement.md](disbursement.md)
- Repayment (per child): [repayment.md](repayment.md)
- Foreclosure (per child): [foreclosure.md](foreclosure.md)
