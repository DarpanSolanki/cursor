-- Post loanRepayment DPI assertions for demo loan fixture.
-- psql vars: loan_account_id (bigint), min_dpi_paid (numeric, default 0)
\set min_dpi_paid 0
SELECT
  (SELECT count(*)::bigint
   FROM mfi_accounting.loan_due_details
   WHERE loan_account_id = :loan_account_id::bigint
     AND component_type = 'DPI'
     AND is_deleted = false
     AND (due_amount - paid_amount - COALESCE(waived_amount, 0)) > 0) AS dpi_due_open,
  (SELECT COALESCE(max(dpi_amount), 0)
   FROM mfi_accounting.loan_account_payments_details
   WHERE loan_account_id = :loan_account_id::bigint
     AND transaction_reference_number NOT LIKE 'R\_%') AS max_dpi_paid_on_payment,
  (SELECT COALESCE(sum(due_amount - paid_amount - COALESCE(waived_amount, 0)), 0)
   FROM mfi_accounting.loan_due_details
   WHERE loan_account_id = :loan_account_id::bigint
     AND component_type = 'DPI'
     AND is_deleted = false) AS dpi_total_outstanding;
