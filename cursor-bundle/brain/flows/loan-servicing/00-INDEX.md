# Loan servicing flows — master index

> Every loan-servicing operation in Trustt LMS, end-to-end. Each doc covers: what triggers it, the orchestration `<Request>` chain, every DB table written, every GL hit, child fan-out for SHG/JLG, idempotency, failure modes, runbook cross-link.

> **Start here:** [`lan-transactions-reference.md`](lan-transactions-reference.md) — single-page reference covering all 18 LAN transaction types, the 3 gating models (approval-service / task-workflow / direct), and the analysis methodology. Use this BEFORE drilling into a per-flow doc.

## Already-documented in `../`

| Flow | Doc |
|---|---|
| **Disbursement** (LOS → Kafka → accounting → bank) | [`../disbursement-end-to-end.md`](../disbursement-end-to-end.md) |
| **Repayment** (collection → appropriation → posting → auto-closure) | [`../repayment-end-to-end.md`](../repayment-end-to-end.md) |
| **Foreclosure & closure** (maker-checker → posting → CLOSED) | [`../foreclosure-and-closure.md`](../foreclosure-and-closure.md) |
| **SHG/JLG fan-out** (parent → event queue → child replays) | [`../shg-jlg-group-loan.md`](../shg-jlg-group-loan.md) |
| **EOD/BOD cycle** (interest accrual, NPA, billing, TB) | [`../eod-bod-cycle.md`](../eod-bod-cycle.md) |
| **NPA classification + provisioning** | [`../npa-and-provisioning.md`](../npa-and-provisioning.md) |
| **Maker-checker meta-pattern** | [`../maker-checker.md`](../maker-checker.md) |

## Documented here

| Flow | Doc | Trigger Request |
|---|---|---|
| **Part-prepayment** (reduce EMI / reduce tenor) | [part-prepayment.md](part-prepayment.md) | `loanAccountPartPrepayment`, `parentLoanAccountPartPrepayment`, `childLoanPartPrepayment` |
| **Death foreclosure** (insurance-partner integration, 6 stages) | [death-foreclosure.md](death-foreclosure.md) | `loanDeathForeclosure` |
| **Transaction reversal** (single + bulk) | [transaction-reversal.md](transaction-reversal.md) | `loanAccountTransactionReversal`, `childLoanTransactionReversal`, `bulkSGToTransactionReversalJob` |
| **Restructuring** (UPDATE_EMI / UPDATE_TENURE / ROI change) | [restructuring.md](restructuring.md) | `loanAccountRestructuring`, `childLoanRestructuring` |
| **Rebooking** (re-issue after cancellation) | [rebooking.md](rebooking.md) | `loanAccountRebooking`, `individualLoanAccountRebooking`, `groupLoanAccountRebooking`, `childLoanRebooking` |
| **Reopening** (reverse a closure) | [reopening.md](reopening.md) | `loanAccountReopening`, `childLoanReopening` |
| **Waiver** (charge waiver, principal waiver) | [waiver.md](waiver.md) | `waiveLoanAccountCharges`, `childWaiveLoanAccountCharges` |
| **Excess amount refund** (proactive + standard) | [excess-amount-refund.md](excess-amount-refund.md) | `loanAccountExcessAmountRefund`, `childLoanAccountExcessAmountRefund`, `proactiveExcessAmountRefund` |
| **Disbursement cancellation** (+ parent reschedule for SHG/JLG) | [disbursement-cancellation.md](disbursement-cancellation.md) | `loanDisbursementCancellation`, `childLoanDisbursementCancellation`, `childLoanDisbursementCancellationParentRescheduling` |
| **Write-off / settlement** (accounting write-off) | [write-off.md](write-off.md) | `loanWriteoff` |
| **Advance repayment** (auto-apply excess to next due) | [advance-repayment.md](advance-repayment.md) | `loanAdvanceRepayment` |

## How to read each flow doc

Same structure across all:
1. **What it is** — one-paragraph mental model
2. **Trigger + orchestration entry** — Request name + XML location + `function_code` / `function_sub_code` matrix
3. **Validators** — what input shape is enforced
4. **Maker-side processor chain** (if maker-checker)
5. **Checker / APPROVE-side chain** — the heavy work
6. **DB writes** in order (tables touched + columns updated)
7. **GL hits** — DR/CR pairs via `postTransaction` (linked to txn_catalogue)
8. **SHG/JLG fan-out** — what's enqueued in `loan_account_events_queue` (event_type)
9. **Status transitions** — `loan_account.loan_status` and `disbursement_status` changes
10. **Idempotency + concurrency** — what dedups, what locks
11. **Failure modes** — known issues + runbook link
12. **Code anchors** — orchestration XML line + key processor file paths

## Cross-cutting reference

For the **orchestration meta-pattern** every servicing flow follows (validators → maker → submitApplication → checker → APPROVE branch → posting → status update → audit), see [`../maker-checker.md`](../maker-checker.md).

For the **GL posting engine** that every "money moves" step funnels through, see [`../../accounting/08-gl-posting-engine.md`](../../accounting/08-gl-posting-engine.md).

For **per-table writes** invoked by these flows, see [`../../accounting/db-code-map/by-flow/`](../../accounting/db-code-map/by-flow/).
