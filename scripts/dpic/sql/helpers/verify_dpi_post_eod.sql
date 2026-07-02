-- Post-EOD DPI assertions for local regression (loan 8060160 fixture).
\set ON_ERROR_STOP on

WITH acc AS (
  SELECT COUNT(*) FILTER (WHERE total_accrued_amount > 0) AS accrual_rows,
         COUNT(DISTINCT installment_id) FILTER (WHERE total_accrued_amount > 0) AS distinct_installments,
         COUNT(*) FILTER (WHERE accrual_posting_date IS NOT NULL AND total_accrued_amount > 0) AS booked_rows,
         COUNT(*) FILTER (WHERE billing_posting_date IS NOT NULL AND total_accrued_amount > 0) AS billed_rows,
         COALESCE(SUM(total_accrued_amount) FILTER (WHERE NOT is_deleted), 0) AS total_accrued
  FROM mfi_accounting.dpi_accrual_details
  WHERE loan_account_id = :loan_account_id::bigint AND is_deleted = false
),
dpi_due AS (
  SELECT COUNT(*) AS dpi_due_rows,
         COALESCE(SUM(due_amount - paid_amount - waived_amount), 0) AS dpi_outstanding
  FROM mfi_accounting.loan_due_details
  WHERE loan_account_id = :loan_account_id::bigint
    AND is_deleted = false
    AND component_type = 'DPI'
    AND (due_amount - paid_amount - waived_amount) > 0
),
latest_acc AS (
  SELECT da.installment_id
  FROM mfi_accounting.dpi_accrual_details da
  WHERE da.loan_account_id = :loan_account_id::bigint
    AND da.is_deleted = false
    AND da.total_accrued_amount > 0
  ORDER BY da.end_date DESC, da.id DESC
  LIMIT 1
)
SELECT acc.accrual_rows,
       acc.distinct_installments,
       acc.booked_rows,
       acc.billed_rows,
       acc.total_accrued,
       dpi_due.dpi_due_rows,
       dpi_due.dpi_outstanding,
       latest_acc.installment_id AS latest_accrual_installment_id
FROM acc, dpi_due, latest_acc;
