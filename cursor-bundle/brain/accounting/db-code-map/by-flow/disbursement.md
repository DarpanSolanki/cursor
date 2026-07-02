# Disbursement → tables touched

Flow narrative: [`../../../flows/disbursement-end-to-end.md`](../../../flows/disbursement-end-to-end.md)

The `disburseLoan` Request runs through 9 stages driven by `function_sub_code` ([state machine](../../07-loan-account-lifecycle.md#3-the-disburseloan-state-machine--driven-by-function_sub_code)). Tables touched in execution order:

## Stage DEFAULT / LAN_CREATED (initial creation)

| Step | Table | Action | Processor / Source |
|---|---|---|---|
| 1 | `account` | INSERT (parent) | `CreateLoanAccountProcessor` |
| 2 | `loan_account` | INSERT | `CreateLoanAccountProcessor` (loan_status=APPROVED) |
| 3 | `loan_installment_details` | INSERT (N rows = number_of_installments) | `CreateInstallmentAndDueDetailsProcessor` |
| 4 | `loan_due_details` | INSERT (N×4 rows: PRIN/INT/PINT/FEE per installment) | `CreateInstallmentAndDueDetailsProcessor` |
| 5 | `loan_repayment_schedule_details` | INSERT (immutable schedule snapshot) | `customCallRepaymentScheduleGenerateProcessor` |
| 6 | `loan_disbursement_charge_details` | INSERT (charges deducted up-front) | `loan/charges/processor/...` |
| 7 | `loan_account_tax_details` | INSERT (tax on charges, if any) | tax processors |
| 8 | `loan_disbursement_mode_details` | INSERT (NEFT/STP details) | disbursement-mode processors |
| 9 | `loan_disbursement_transaction` | INSERT (one per disbursement attempt) | disbursement-transaction processor |
| 10 | `bank_service_call_retry` | INSERT (if bank call deferred — STP) | bank-call processors |

## Stage NEFT_STAGE_* (bank-call retry loop)

| Step | Table | Action | Processor |
|---|---|---|---|
| - | `loan_account.disbursement_status` | UPDATE | `UpdateLoanAccountStatusProcessor` (per stage transition) |
| - | `loan_disbursement_transaction` | UPDATE | bank callback handlers |
| - | `bank_service_call_retry` | UPDATE | retry job |

## Stage PARENT_SUCCESS (the GL hit)

| Step | Table | Action | Processor |
|---|---|---|---|
| 11 | `transaction_master` | INSERT (txn header) | `CreateTransactionMasterProcessor` (via `<API id="postTransaction">`) |
| 12 | `transaction_metadata` | INSERT | `CreateTransactionMetadataProcessor` |
| 13 | `transaction_partition_details` | INSERT (N legs) | `CreateTransactionPartitionDetailsProcessor` (built by `ExecuteTransactionRulesProcessor`) |
| 14 | `transaction_details` | INSERT (per affected account) | `CreateTransactionDetailsProcessor` |
| 15 | `account_balance` | UPDATE | (inside `createTransactionDetailsProcessor`) |
| 16 | `loan_account.loan_status = ACTIVE`, `disbursement_status` | UPDATE | `UpdateLoanAccountStatusProcessor` |
| 17 | `loan_account_events_queue` | INSERT (CLB event for each child, SHG/JLG only) | `CreateClmtLoanAccountEventsProcessor` |
| 18 | `audit_log` (mfi_audit) | INSERT | framework `<AuditData>` |

## Stage REJECT (failure path)

| Step | Table | Action |
|---|---|---|
| - | `loan_account.loan_status = DISB_CNCL`, `cancelled_on` | UPDATE |
| - | `loan_disbursement_cancellation_*` | various INSERTs |

## Insurance side-effects (parallel)

If insurance configured for the product:
- `loan_account_insurance_details` — INSERT
- Outbound insurance file via `outboundDisbursement<Provider>InsuranceJob`

## Read tables (during disbursement)

- `loan_product`, `product_scheme`, `product__transaction_catalogue`, `product_transaction_catalogue__placeholder__iad` — product config
- `interest_setup`, `interest_setup_slab`, `base_interest_master`, `base_interest_slab` — rate calc
- `transaction_accounting_rule`, `placeholder_master`, `internal_account_definition`, `internal_account` — GL hit derivation
- `holiday`, `working_days_master` — schedule generation
- `currency_master`

## SHG/JLG child fan-out (separate cycle, async)

Triggered by the `loan_account_events_queue` row inserted in step 17. See [shg-jlg-fanout.md](shg-jlg-fanout.md).

## Diagnostic queries

- "Is this loan stuck mid-disbursement?" → [`tables/loan_account.md`](../tables/loan_account.md) common queries
- "Bank call retry status?" → query `bank_service_call_retry`
- Runbook: [`../../../runbooks/disbursement-stuck.md`](../../../runbooks/disbursement-stuck.md)
