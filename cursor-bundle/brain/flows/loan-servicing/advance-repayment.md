# Loan servicing — Advance Repayment

> Auto-applies the customer's `excess_amount` (from prior overpayments) to the next due EMI when it falls due. Runs as a scheduled batch. No customer interaction. No maker-checker.

## Single Request

| Request | XML |
|---|---|
| `loanAdvanceRepayment` | `loans_orc.xml` (also called as a batch from `mfi_batch.batch_job`) |

## Purpose

Customers may pay extra (excess sits in `loan_account.excess_amount`). When the next EMI falls due, the system can auto-apply the excess to settle it without the customer having to act. This is the mechanism.

## Trigger

Scheduled by `novopay-platform-batch` — `loanAdvanceRepayment` runs daily (or per business day depending on config). Reads loans with `excess_amount > 0` AND `next_due_date <= today`.

## Processor chain

(Standard for batch-fired Requests; `function_sub_code=BATCH`, `op_code=RESTART` forced by `DirectJobExecutor`)

1. `populateUserDetails` (system user — batch context)
2. `validateLoanAccountForAdvanceRepayment` — guard:
   - `loan_account.loan_status = ACTIVE`
   - `excess_amount > 0`
   - At least one due row with `due_date <= today` and pending amount > 0
3. `populateAdvanceRepaymentAmountProcessor` — compute `repayment_amount = MIN(excess_amount, total_pending_today)`
4. `RepaymentApproppriationProcessor` — same engine as `loanRepayment`. Walks `loan_due_details` and splits the `repayment_amount` per component (priority via `loan_product_asset_criteria`)
5. `updateLoanDueDetailsProcessor` — UPDATE paid_amount per row touched
6. `updateLoanInstallmentDetailsProcessor`
7. `updateLoanAccountForExcessAmountProcessor` — `excess_amount -= settled`
8. `<API id="postTransaction">` (txn_catalogue=`LOAN_ADVANCE_REPAYMENT` or similar — variant of LOAN_REPAYMENT):
   ```
   DR  EXCESS_AMOUNT_PAYABLE_AC      ₹settled  (excess pool reduces)
   CR  LOAN_PRIN_AC                  ₹principal portion
   CR  INT_INCOME_AC                 ₹interest portion
   CR  PINT_INC_AC                   ₹penal portion
   CR  FEE_INC_AC                    ₹fee portion
   ```
   (No customer-facing leg — the cash already came in earlier as part of the repayment that created the excess.)
9. `createLoanAccountPaymentsDetailsProcessor` — INSERT (tagged as advance repayment)
10. DPD/asset criteria/classification refresh
11. `checkAccountAutoClosureEligibilityProcessor` — fires auto-closure if loan now fully paid
12. (no notification — customer often unaware until statement)

## DB writes

| Table | Action |
|---|---|
| `loan_due_details` | UPDATE `paid_amount` per row settled |
| `loan_installment_details` | UPDATE installment_status |
| `loan_account.excess_amount` | UPDATE — reduced by settled amount |
| `transaction_master`, `transaction_partition_details`, `transaction_details` | INSERT (advance repayment txn) |
| `loan_account_payments_details` | INSERT (tagged advance) |
| `loan_account.past_due_days`, `asset_*`, `npa_*` | UPDATE (recompute) |
| `loan_account.loan_status` | UPDATE → CLOSED (only if loan fully paid) |
| `batch_failure_audit` | INSERT per failed loan |

## Why no maker-checker

The customer already authorised the payment that became the excess. Auto-applying it to a subsequent EMI is a default behaviour (controllable via `loan_account.refund_allowed` and tenant config). Maker-checker would defeat the purpose.

## Status transitions

```
ACTIVE (with excess) ──advance batch fires──► ACTIVE (excess reduced) — or CLOSED if fully paid
```

## Failure modes

| Symptom | Cause | Triage |
|---|---|---|
| Loan with excess didn't auto-apply | Batch didn't run, or `next_due_date` not yet today | Check `mfi_batch.batch_schedule WHERE name='loanAdvanceRepayment'`; verify due_date |
| Wrong amount applied | Appropriation order ambiguous | Same as [repayment-mismatch runbook](../../runbooks/repayment-mismatch.md) |
| Failure on one loan | Per-loan failure goes to `batch_failure_audit` | Investigate, fix data, re-run batch |

## Cross-references

- [Repayment](../repayment-end-to-end.md) — same appropriation engine, customer-driven version
- [Excess amount refund](excess-amount-refund.md) — alternative path: refund the excess instead of auto-applying
- [Repayment-mismatch runbook](../../runbooks/repayment-mismatch.md)

## Code anchors

- **Orchestration**: `loans_orc.xml::loanAdvanceRepayment`
- **Batch wiring**: `mfi_batch.batch_job` row with name='loanAdvanceRepayment'
- **Reuses**: [`RepaymentApproppriationProcessor`](../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java) (same engine as user-driven repayment)
