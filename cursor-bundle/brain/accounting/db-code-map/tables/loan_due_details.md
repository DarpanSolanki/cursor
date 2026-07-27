# `mfi_accounting.loan_due_details`

> The "what's owed right now" table — one row per (loan, installment, component). Walked by the repayment appropriation engine. The most-touched table during repayment flows.

## Purpose

Per-component, per-installment expansion of the loan repayment schedule. Each EMI generates 4+ rows (PRIN, INT, PINT, FEE) here. Repayment processes deduct against these rows in priority order; billing job creates new rows on schedule; reschedule/restructure update them.

## Schema (live, key columns)

(Run `tools/inspect-table.sh loan_due_details` for full schema.)

| Column | Meaning |
|---|---|
| `id` (PK) | bigint |
| `loan_account_id` | FK → `loan_account.account_id` |
| `installment_id` | FK → `loan_installment_details.id` |
| `component_type` | One of: `PRIN` (principal), `INT` (interest), `PINT` (penal interest), `FEE` (fee/charge). Constants in `AssetsConstants.java:42-45` |
| `due_date` | Date the component is owed |
| `due_amount` | Total owed |
| `paid_amount` | Cumulative paid (across many repayments) |
| `waived_amount` | Cumulative waived |
| `current_paid_amount` | Transient — set during a single repayment's processing, cleared next |
| `created_on`, `updated_on` | audit |

## JPA entity

[`account/loans/entity/LoanDueDetailsEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/entity/LoanDueDetailsEntity.java)

## DAO

[`account/loans/repository/LoanDueDetailsDAOService.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/repository/LoanDueDetailsDAOService.java)

## Writers

| Processor | Action | Triggered by Request |
|---|---|---|
| [`CreateInstallmentAndDueDetailsProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/processor/CreateInstallmentAndDueDetailsProcessor.java) | INSERT | `disburseLoan` (during repayment-schedule generation) |
| [`CreateCustomInstallmentAndDueDetailsProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/custom/mfi/disburse/processor/CreateCustomInstallmentAndDueDetailsProcessor.java) | INSERT | tenant-specific disbursement variants |
| [`UpdateLoanDueDetailsProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/UpdateLoanDueDetailsProcessor.java) | UPDATE `paid_amount`, `current_paid_amount` | `loanRepayment` after appropriation |
| `UpdateLoanDueDetailsForWaiverProcessor` | UPDATE `waived_amount` | `loanWaiver`, `childWaiveLoanAccountCharges` |
| `UpdateDueDetailsForPrepaymentProcessor` | UPDATE | foreclosure / prepayment |
| [`UpdateDueDetailsForDisbursementCancellationProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/processor/UpdateDueDetailsForDisbursementCancellationProcessor.java) | DELETE / UPDATE | `loanDisbursementCancellation` |
| [`UpdateCustomLoanDueDetailsProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/custom/mfi/disburse/processor/UpdateCustomLoanDueDetailsProcessor.java) | UPDATE | tenant variants |
| [`UpdateLoanDueDetailsDataProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/cancellation/processor/UpdateLoanDueDetailsDataProcessor.java) | UPDATE (group cancel) | `childLoanDisbursementCancellation` |
| [`PenalInterestAccrualBookingItemWriter`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/penal/penalaccrualbooking/PenalInterestAccrualBookingItemWriter.java) | INSERT (PINT rows) | EOD `penalInterestAccrualBooking` |
| [`ChildLoanPenalInterestBookingService`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/lpp/service/ChildLoanPenalInterestBookingService.java) | INSERT | child penal booking |
| [`CreateChildLoanPartPrepaymentInstallmentProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/partprepayment/processor/CreateChildLoanPartPrepaymentInstallmentProcessor.java) | INSERT (post-prepayment new schedule) | `childLoanPartPrepayment` |
| [`CreateRepaymentInstallmentDetailsProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/CreateRepaymentInstallmentDetailsProcessor.java) | INSERT | post-repayment schedule changes |
| [`ConsumeSIPresentationFileTasklet`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/standinginstruction/presentation/tasklet/ConsumeSIPresentationFileTasklet.java) | INSERT/UPDATE (SI presentation results) | SI batch |
| [`ConsumeEnachPresentationFileTasklet`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/enach/presentation/tasklet/ConsumeEnachPresentationFileTasklet.java) | INSERT/UPDATE | eNACH batch |
| [`ConsumeEnachRepresentationFileTasklet`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/enach/representation/tasklet/ConsumeEnachRepresentationFileTasklet.java) | INSERT/UPDATE | eNACH re-presentation batch |

## Readers

| Processor | Triggered by Request | Purpose |
|---|---|---|
| [`GetLoanDueDetailsProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/GetLoanDueDetailsProcessor.java) | `loanRepayment` | preload due rows for appropriation |
| [`RepaymentApproppriationProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java) | `loanRepayment`, `childLoanRepayment` | walks rows in liquidation order, deducts amount from each |
| `PrepaymentApproppriationProcessor` | foreclosure / prepayment | similar walk |
| Billing job reader | EOD `loanAccountBillingJob` | aggregates due rows for billing snapshots |

## Related Requests

- `disburseLoan` — initial creation
- `loanRepayment`, `childLoanRepayment`, `loanAdvanceRepayment` — primary writers
- `loanForeclosure`, `loanPrepayment`, `individualChildLoanForeclosure` — write paid_amount
- `loanAccountPartPrepayment`, `parentLoanAccountPartPrepayment`, `childLoanPartPrepayment` — restructures dues
- `loanWaiver`, `childWaiveLoanAccountCharges` — write waived_amount
- `LoanAccountRestructuring` — replaces dues
- `loanAccountReopening` — restores dues from closure backup
- `penalInterestAccrualBooking` — inserts PINT rows
- `loanDisbursementCancellation` — deletes/zeroes dues

## Related flows

- [Repayment end-to-end](../../../flows/repayment-end-to-end.md)
- [Disbursement end-to-end](../../../flows/disbursement-end-to-end.md)
- [Foreclosure & closure](../../../flows/foreclosure-and-closure.md)

## Common diagnostic queries

```sql
-- Per-component dues for a loan (in repayment-time order — the appropriation walks this)
SELECT due_date, component_type, due_amount, paid_amount, waived_amount,
       (due_amount - paid_amount - waived_amount) AS pending
  FROM mfi_accounting.loan_due_details
 WHERE loan_account_id = (SELECT account_id FROM mfi_accounting.loan_account la
                           JOIN mfi_accounting.account a ON a.id=la.account_id
                          WHERE a.account_number = ?)
 ORDER BY due_date, component_type;

-- Total outstanding per loan
SELECT loan_account_id,
       SUM(due_amount - paid_amount - waived_amount) AS outstanding
  FROM mfi_accounting.loan_due_details
 GROUP BY loan_account_id
HAVING SUM(due_amount - paid_amount - waived_amount) > 0
 ORDER BY 2 DESC LIMIT 20;
```

## Gotchas

1. **`current_paid_amount` is transient** — set during a repayment's appropriation, cleared/reset on next call. Don't rely on it outside an in-flight transaction.
2. **The 4 component types are codes, not enums** — `PRIN`/`INT`/`PINT`/`FEE`. Constants in `AssetsConstants.java:42-45`.
3. **Appropriation order is determined by `loan_product_asset_criteria`** — that table has 4 component slots + `liquidationOrder` (`LIQ_INSTL` / `LIQ_COMP` / `LIQ_INSTL_CHRG_COMP`) which the walker honours.
4. **Penal interest rows (PINT) are inserted by EOD batch**, not at disbursement. So a fresh loan has no PINT rows.
5. **Waiver doesn't delete; it adds to `waived_amount`.** A row with `paid_amount + waived_amount = due_amount` is settled.
6. **Disbursement cancellation deletes future dues** but keeps history.
