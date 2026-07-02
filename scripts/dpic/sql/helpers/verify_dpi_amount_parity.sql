\set ON_ERROR_STOP on
-- Accrued vs GL-posted vs billed DPI due — SDCP-10529 class (no accrued>billed gap).
WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id
),
accrual AS (
  SELECT COALESCE(SUM(da.total_accrued_amount), 0) AS total_accrued,
         COALESCE(SUM(da.total_accrued_amount) FILTER (WHERE da.accrual_posting_date IS NOT NULL), 0) AS posted_accrued,
         COALESCE(SUM(da.total_accrued_amount) FILTER (WHERE da.billing_posting_date IS NOT NULL), 0) AS billed_accrued,
         COUNT(*) FILTER (
           WHERE da.accrual_posting_date IS NOT NULL
             AND da.total_accrued_amount > 0
             AND da.accrual_transaction_ref_number IS NOT NULL
         ) AS posted_rows_with_ref
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id AND da.is_deleted = false
),
gl AS (
  SELECT COALESCE(SUM(tm.amount), 0) AS gl_posted
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  JOIN mfi_accounting.transaction_master tm
    ON tm.transaction_reference_number = da.accrual_transaction_ref_number
   AND tm.is_deleted = false
  WHERE da.loan_account_id = p.loan_id
    AND da.is_deleted = false
    AND da.accrual_posting_date IS NOT NULL
    AND da.total_accrued_amount > 0
),
dpi_due AS (
  SELECT COALESCE(SUM(ldd.due_amount), 0) AS dpi_due_total
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.is_deleted = false
    AND ldd.component_type = 'DPI'
)
SELECT a.total_accrued,
       a.posted_accrued,
       a.billed_accrued,
       g.gl_posted,
       d.dpi_due_total,
       (a.posted_accrued = g.gl_posted) AS posted_matches_gl,
       (a.billed_accrued = d.dpi_due_total) AS billed_matches_due,
       (a.posted_accrued >= a.billed_accrued) AS posted_covers_billed
FROM accrual a
CROSS JOIN gl g
CROSS JOIN dpi_due d;
