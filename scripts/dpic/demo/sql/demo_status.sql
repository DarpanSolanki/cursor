\set ON_ERROR_STOP on

\echo '=== Loan ==='
SELECT la.account_id, a.account_number, la.loan_status, la.past_due_days,
       la.disbursement_date::date AS disbursement_date
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.account_id = :loan_account_id;

\echo ''
\echo '=== EMI schedule (next 4) ==='
SELECT id, installment_date::date, installment_amount, is_settled
FROM mfi_accounting.loan_installment_details
WHERE loan_account_id = :loan_account_id AND is_deleted = false
ORDER BY installment_date
LIMIT 4;

\echo ''
\echo '=== DPI accrual (calc vs posted) ==='
SELECT
  COUNT(*) FILTER (WHERE accrual_posting_date IS NULL)     AS unposted_rows,
  COUNT(*) FILTER (WHERE accrual_posting_date IS NOT NULL) AS posted_rows,
  COALESCE(SUM(total_accrued_amount) FILTER (WHERE accrual_posting_date IS NULL), 0)     AS unposted_amt,
  COALESCE(SUM(total_accrued_amount) FILTER (WHERE accrual_posting_date IS NOT NULL), 0) AS posted_amt,
  COUNT(DISTINCT accrual_transaction_ref_number)
    FILTER (WHERE accrual_transaction_ref_number IS NOT NULL) AS distinct_accrual_gl_txns
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id AND is_deleted = false;

\echo ''
\echo '=== DPI customer dues ==='
SELECT component_type, due_date::date, due_amount, paid_amount,
       (due_amount - paid_amount - waived_amount) AS outstanding
FROM mfi_accounting.loan_due_details
WHERE loan_account_id = :loan_account_id
  AND component_type = 'DPI'
  AND is_deleted = false
ORDER BY due_date;
