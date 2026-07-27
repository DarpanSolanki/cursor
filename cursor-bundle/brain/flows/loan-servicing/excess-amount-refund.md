# Loan servicing — Excess Amount Refund

> Customer overpaid (paid more than total due). The excess sits in `loan_account.excess_amount`. Two refund paths: **standard** (operator-initiated, maker-checker) and **proactive** (auto-batch when loan closes with excess and refund_allowed=true).

## Variants

| Request | XML | Use |
|---|---|---|
| `loanAccountExcessAmountRefund` | `loans_orc.xml` | Operator-initiated refund, maker-checker |
| `childLoanAccountExcessAmountRefund` | `group_mfi_orc.xml:581` | Per-child (replayed from `LEAR` events) |
| `getLoanAccountExcessAmountRefundDetails`, `getLoanAccountExcessAmountRefundList` | `loans_orc.xml` | Read history |
| `proactiveExcessAmountRefundStaging` | `ServiceOrchestrationXML.xml` | Auto-stage excess refund records (no maker-checker) |
| `proactiveExcessAmountRefund` | `ServiceOrchestrationXML.xml` | Process the staged auto-refunds |
| `proactiveReverseTransaction` | `ServiceOrchestrationXML.xml` | Reverse if proactive refund fails downstream |
| `inboundReverseExcessAmountRefundJob`, `runInboundReverseExcessAmountRefundJob` | `ServiceOrchestrationXML.xml` | Vendor-side refund-confirmation feed |
| `bulkFileToSGRefundMarkingJob`, `bulkSGToRefundMarkingJob` | `ServiceOrchestrationXML.xml` | Bulk mark loans as refund-eligible |

## Standard flow (operator-initiated)

### Maker-side

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `validateExcessAmountRefundProcessor` — refuse if `loan_account.refund_allowed=false`, or excess_amount=0, or refund already in flight
3. `populateExcessAmountRefundDataProcessor` — pull excess_amount, customer payment-account info
4. `createOrUpdateLoanAccountExcessAmountRefundProcessor` — INSERT into `loan_account_excess_amount_refund_details` (status=PENDING)
5. `<API id="…submitApplication">` → approval draft
6. `<API id="createOrUpdateTask">` → checker task
7. (no FREEZE state)

### Checker (APPROVE)

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. Re-validate
3. `<API id="postTransaction">` (txn_catalogue=`EXCESS_AMOUNT_REFUND`):
   ```
   DR  EXCESS_AMOUNT_PAYABLE_AC      ₹excess_amount
   CR  CUSTOMER_AC / BANK_AC         ₹excess_amount
   ```
4. `loan_account.excess_amount` → 0 (or decremented)
5. `loan_account_excess_amount_refund_details.status` → APPROVED, with txn_ref + refund_date
6. Update task → CLOSED, delete approval draft, notification

## Proactive flow (auto-batch)

When a loan closes (`loan_status=CLOSED` via auto-closure or foreclosure) AND `excess_amount>0` AND `refund_allowed=true`:

1. **Staging step** (`proactiveExcessAmountRefundStaging` — runs as part of closure or on a schedule):
   - Reads CLOSED loans with positive excess and refund_allowed
   - For each, INSERTS into `file_staging_proactive_refund` with status=PENDING
   - Source: [`ProactiveExcessAmountRefundStagingItemProcessor`](../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/refund/proactiveexcessamountrefundstaging/ProactiveExcessAmountRefundStagingItemProcessor.java)

2. **Process step** (`proactiveExcessAmountRefund`):
   - Reads `file_staging_proactive_refund` WHERE status=PENDING
   - For each, calls vendor refund (UPI/NEFT) via STP bank service
   - On success: posts the refund txn (same legs as standard) + marks staging row PROCESSED
   - On failure: marks FAILED + retried by `accountingBankServiceRetryJob`
   - Source: [`batchnew/refund/proactivereversetransaction/ProactiveRefundFileStaging.java`](../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/refund/proactivereversetransaction/ProactiveRefundFileStaging.java)

3. **Failure rollback** (`proactiveReverseTransaction`):
   - If vendor returns failure days later (vendor-side reverse-feed):
   - Inbound: `runInboundReverseExcessAmountRefundJob` → `inboundReverseExcessAmountRefundJob`
   - Reverses the proactive refund txn via `reverseTransaction`
   - Restores `loan_account.excess_amount` to its pre-refund value
   - Marks staging row REVERSED with reason

## DB writes (standard flow)

| Table | Action |
|---|---|
| `loan_account_excess_amount_refund_details` | INSERT (PENDING) → UPDATE (APPROVED) |
| `loan_account.excess_amount` | UPDATE → 0 (or decremented) |
| `transaction_master`, `transaction_partition_details`, `transaction_details` | INSERT (refund txn) |
| `account_balance` | UPDATE |
| `mfi_approval.application` + `mfi_task.task` | maker-checker |
| `loan_account_events_queue` | INSERT (`LEAR`, SHG/JLG only) |

## DB writes (proactive flow)

| Table | Action |
|---|---|
| `file_staging_proactive_refund` | INSERT (PENDING) → UPDATE (PROCESSED/FAILED/REVERSED) |
| `loan_account_excess_amount_refund_details` | INSERT (auto-approved, no maker-checker) |
| `loan_account.excess_amount` | UPDATE |
| `transaction_master`, `transaction_partition_details`, `transaction_details` | INSERT |
| (on failure) reverse txn family | INSERT mirror legs |

## SHG/JLG variant (`childLoanAccountExcessAmountRefund`)

Triggered via `LEAR` events. Per-child:

1. `populateChildLoanAccountExcessAmountRefundDataProcessor`
2. `<API id="postTransaction">` (with `is_child_account=true` → CG-prefixed GLs)
3. `createLoanAccountPaymentsDetailsProcessor`
4. `updateLoanAccountChildAccountEntityProcessor` — UPDATE child's excess_amount

## Status transitions

No `loan_account.loan_status` change for refund itself. The `loan_account_excess_amount_refund_details.status` transitions PENDING → APPROVED → PROCESSED.

## Code anchors

- **Orchestration**: `loans_orc.xml::loanAccountExcessAmountRefund`, `group_mfi_orc.xml:581`, `ServiceOrchestrationXML.xml::proactive*`
- **Code root**: [`loan/excessamountrefund/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/excessamountrefund/)
- **Group variant**: [`loan/grouploan/excessamountrefund/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/excessamountrefund/)
- **Proactive batch**: [`batchnew/refund/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/refund/) — `proactiveexcessamountrefundstaging`, `proactivereversetransaction` sub-packages
- **Tables**: `loan_account_excess_amount_refund_details`, `file_staging_proactive_refund`

## Cross-references

- [Repayment](../repayment-end-to-end.md) — where excess_amount accumulates
- [Foreclosure](../foreclosure-and-closure.md) — closure with excess triggers refund
- [Death foreclosure](death-foreclosure.md) — final step refunds excess to nominee
- [Bank-call retry pattern](#) — failed proactive refunds retry via `accountingBankServiceRetryJob`
