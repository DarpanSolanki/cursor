# Data Model (core concepts; code-verified relationships)

This page captures the **core accounting money-flow** data model and the relationship/join logic that the code relies on.

Notes:
- Relationships below are verified mainly via repository query logic and the processors/writers that populate these entities.
- FK directions are not re-validated in this session; rely on repository joins to understand how data is connected in practice.

## 1) Loan lifecycle + disbursement state

### `loan_account` (Loan core + disbursement status field)
- Entity: `in.novopay.accounting.account.loans.entity.LoanAccountEntity` (`@Table(name="loan_account")`)
- Key money-state fields (code uses): `loanStatus`/`loan_status`, `disbursementStatus`/`disbursement_status`, external references

### Disbursement state & tracking tables
- `loan_disbursement_mode_details`
  - Entity: `LoanDisbursementModeDetailsEntity`
  - Join key (repository): `loan_disbursement_mode_details.loan_account_id = ?1`
- `loan_disbursement_transaction`
  - Entity: `LoanDisbursementTransactionEntity`
  - Join key (repository): `loan_disbursement_transaction.loan_account_id = ?1`
- `loan_disbursement_charge_details`
  - Entity: `LoanDisbursementChargeDetailsEntity`
  - Join key (repository): `loan_disbursement_charge_details.loan_account_id = ?1`

## 2) Repayment schedule, dues, and components

### Schedule headers + installment schedule rows
- `loan_repayment_schedule_details`
  - Entity: `LoanRepaymentScheduleDetailsEntity`
  - Repository join: `loan_repayment_schedule_details.loan_account_id = ?1`
- `loan_installment_details`
  - Entity: `LoanInstallmentDetailsEntity`
  - Repository join: `loan_installment_details.loan_account_id = ?1`

### `loan_due_details` (component-wise due/principal/interest/penal/fees)
- Entity: `LoanDueDetailsEntity` (`@Table(name="loan_due_details")`)
- Join logic (schedule dues view):
  - `loan_installment_details lid` JOIN `loan_due_details ldd` ON `lid.id = ldd.loan_installment_details_id`
  - Filter: `lid.loan_account_id = ?1`, and both sides apply `is_deleted=false`
- Component split semantics (code depends on these fields):
  - `due_amount`, `paid_amount`, `waived_amount`
  - outstanding logic relies on `due - paid - waived`

### How dues are created (schedule -> installment -> due)
- `CreateRepaymentScheduleDetailsProcessor` writes `loan_repayment_schedule_details`
- `CreateInstallmentAndDueDetailsProcessor` writes:
  - `loan_installment_details`
  - then `loan_due_details` by using the saved installment IDs

## 3) Repayment payment transaction rows + allocation links

### `loan_account_payments_details` (the repayment “payment transaction detail” table)
- Entity: `LoanAccountPaymentsDetailsEntity` (`@Table(name="loan_account_payments_details")`)
- Created by: `CreateLoanAccountPaymentsDetailsProcessor`
- Stored in `ExecutionContext`:
  - `executionContext.put("loan_account_payments_details_id", <id>)`

### `loan_due_details__loan_account_payments_details` (allocation link: due -> payment detail)
- Entity: `LoanDueDetailsLoanAccountPaymentsDetailsEntity`
- Written by: `CreateLoanDueDetailsLoanAccountPaymentsDetailsProcessor`
  - It allocates `paidAmount`, `waivedAmount`, and `waiverDetailsId` per due detail
- Query join logic (repository):
  - `loan_account_payments_details lapd`
  - JOIN `loan_due_details__loan_account_payments_details lddlapd` ON `lapd.id = lddlapd.loan_account_payments_details_id`
  - JOIN `loan_due_details ldd` ON `ldd.id = lddlapd.due_details_id`
  - Filter: `lapd.transaction_reference_number = ?1`

## 4) Due-details -> repayment “transaction id” mapping

### `loan_due_details__repayment_transaction`
- Entity: `LoanDueDetailsRepaymentTransactionEntity`
- Repo: `LoanDueDetailsRepaymentTransactionRepository`
- Code wiring:
  - Created by `CreateRepaymentInstallmentDetailsProcessor`
  - It reads repayment “transaction id” from `executionContext["loan_account_payments_details_id"]`
  - Writes into link entity:
    - `loanDueDetailsId = loan_due_details.id`
    - `loanRepaymentTransactionId = loan_account_payments_details.id`
    - `paidAmount = loanDueDetailsEntity.currentPaidAmount`
    - `waivedAmount = 0` (at this creation stage)

## 5) Ledger / transaction engine tables (money -> GL lines)

### `transaction_master`
- Entity: `TransactionMasterEntity` (`@Table(name="transaction_master")`)
- It is the header that ties to:
  - partitions
  - details
  - transaction catalogue

### `transaction_partition_details` (component-level partitions; GL-coded legs)
- Entity: `TransactionPartitionDetailsEntity` (`@Table(name="transaction_partition_details")`)
- Repository evidence (joins and GL mapping):
  - For transaction reference based views:
    - `transaction_master tm` JOIN partitions ON `tpd.transaction_id = tm.id`
  - GL mapping done in code via joins:
    - `LEFT JOIN general_ledger gl ON gl.code = tpd.gl_code`
    - `LEFT JOIN child_general_ledger cgl ON cgl.code = tpd.gl_code`

### `transaction_details` (account-level postings)
- Entity: `TransactionDetailsEntity` (`@Table(name="transaction_details")`)
- Repository join logic:
  - `transaction_details.transactionId = transaction_master.id`

## 6) GL/internal account mapping

### `general_ledger` + `child_general_ledger`
- Entities:
  - `GeneralLedgerEntity` (`@Table(name="general_ledger")`)
  - `ChildGeneralLedgerEntity` (`@Table(name="child_general_ledger")`)
- Transaction partition repository uses code joins on `code`.

### `internal_account_definition` + `internal_account`
- `internal_account_definition`
  - Entity: `InternalAccountDefinitionEntity`
  - Used to map “internal account definitions” -> `general_ledger.code` via repository queries
- `internal_account`
  - Entity: `InternalAccountEntity`
  - Typically resolved by (office, internal account definition code)

### Product transaction catalogue placeholder mapping -> internal account definition
- Repository evidence:
  - `ProductTransactionCatalogueRepository.findInternalAccountDefinitionAndGLCodeByProductIdAndTransactionCatalogueId(...)`
  - Joins:
    - transaction catalogue -> placeholder mapping -> internal_account_definition -> GL code

## 7) Client/bank call audit log (CRR)

### `client_request_response_log`
- Entity: `ClientRequestResponseLogEntity` (`@Table(name="client_request_response_log")`)
- Relationship-by-lookup keys (repository evidence):
  - by `(loan_account_number, transaction_type list, partner)` with ORDER BY system_date DESC LIMIT 1
  - by `(client_reference_number, transaction_type, partner)` similarly
- Used by:
  - bank call retry eligibility
  - reversal logic (reverseTransaction tries to find original CRR rows)

## 8) Batch / staging / derived tables used by money computations

### Billing staging
- `loan_account_billing_details`
  - Entity: `LoanAccountBillingDetailsEntity`
  - Code uses existence checks keyed by `loan_installment_details_id`

### Accrual staging
- `interest_accrual_details`
  - Entity: `InterestAccrualDetailsEntity`
- `penal_interest_accrual_details`
  - Entity: `PenalInterestAccrualDetailsEntity`

### Trial balance
- `trial_balance`
  - Entity: `TrialBalanceEntity`
- `trial_balance_run_history`
  - Entity: `TrialBalanceRunHistoryEntity`
- `opening_balance`
  - Entity: `OpeningBalanceEntity`

## Confidence
- High for the core table categories and the repository join patterns described above (based on code-backed repository/processor evidence).


