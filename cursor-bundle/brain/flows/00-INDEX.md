# Flows — end-to-end journey narratives

> Each file traces one user-facing journey across every service it touches: which Request, which processor, which DB write, which Kafka event. **Use these when implementing a new feature** so you understand the full surface area, or **when investigating a flow-wide issue** before drilling into a single service.

| Flow | When to read it |
|---|---|
| [`customer-onboarding.md`](customer-onboarding.md) | KYC, customer creation, OTP, eKYC; group formation for SHG/JLG |
| [`loan-application-underwriting.md`](loan-application-underwriting.md) | LOS application stages QDE → DDE → BET → CU → CPDC; bureau / dedupe pipelines |
| [`disbursement-end-to-end.md`](disbursement-end-to-end.md) | LOS-trigger → Kafka → accounting state machine → bank → callback → child fan-out |
| [`repayment-end-to-end.md`](repayment-end-to-end.md) | Collection capture → appropriation → posting → DPD/NPA recompute → auto-closure |
| [`shg-jlg-group-loan.md`](shg-jlg-group-loan.md) | Parent + N children, event queue, async fan-out, per-child posting |
| [`foreclosure-and-closure.md`](foreclosure-and-closure.md) | Maker-checker foreclosure → auto-closure → NOC issuance |
| [`npa-and-provisioning.md`](npa-and-provisioning.md) | Daily NPA recompute, asset criteria → classification → provisioning |
| [`eod-bod-cycle.md`](eod-bod-cycle.md) | The complete daily cycle: BOD → EOD → reporting → trial balance zeroisation |
| [`maker-checker.md`](maker-checker.md) | Generic maker-checker pattern: draft → submitApplication → approve/reject → target replay |

## Loan-servicing flows (deeper bundle)

For the **complete inside-out coverage of every loan-servicing operation**, see [`loan-servicing/`](loan-servicing/) — 11 flow docs covering:

| Flow | Doc |
|---|---|
| Part-prepayment | [`loan-servicing/part-prepayment.md`](loan-servicing/part-prepayment.md) |
| Death foreclosure (6-stage insurance flow) | [`loan-servicing/death-foreclosure.md`](loan-servicing/death-foreclosure.md) |
| Transaction reversal (single + bulk) | [`loan-servicing/transaction-reversal.md`](loan-servicing/transaction-reversal.md) |
| Restructuring (UPDATE_EMI / UPDATE_TENURE / ROI) | [`loan-servicing/restructuring.md`](loan-servicing/restructuring.md) |
| Rebooking (re-issue cancelled loan) | [`loan-servicing/rebooking.md`](loan-servicing/rebooking.md) |
| Reopening (reverse a closure) | [`loan-servicing/reopening.md`](loan-servicing/reopening.md) |
| Waiver (charge waiver) | [`loan-servicing/waiver.md`](loan-servicing/waiver.md) |
| Excess amount refund (standard + proactive) | [`loan-servicing/excess-amount-refund.md`](loan-servicing/excess-amount-refund.md) |
| Disbursement cancellation (+ parent reschedule) | [`loan-servicing/disbursement-cancellation.md`](loan-servicing/disbursement-cancellation.md) |
| Write-off / settlement | [`loan-servicing/write-off.md`](loan-servicing/write-off.md) |
| Advance repayment (auto-apply excess) | [`loan-servicing/advance-repayment.md`](loan-servicing/advance-repayment.md) |

Index: [`loan-servicing/00-INDEX.md`](loan-servicing/00-INDEX.md)

## How to read a flow doc

Each flow doc has the same structure:
1. **What it is** — one paragraph mental model.
2. **Services involved** — table.
3. **Step-by-step trace** — numbered, with anchors back to source code where useful.
4. **DB writes** — what changes in which table.
5. **Failure modes** — common ways it breaks, with cross-link to runbook.
6. **Where to dig deeper** — links into per-service docs and accounting deep-dive.

## Cross-references

- For LMS-internal mechanics (GL hit, repayment math, NPA, lifecycle): [`../accounting/`](../accounting/)
- For one-service mental models: [`../services/`](../services/)
- For cross-service maps: [`../system/`](../system/)
- For production debugging: [`../runbooks/`](../runbooks/)
