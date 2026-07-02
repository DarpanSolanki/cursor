-- QA release checklist — maps to accrual posting + billing complaints (SDCP-10497 class).
-- Fails via shell when any hard gate > 0.
\set ON_ERROR_STOP on

WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id,
         :'business_date'::date AS biz
),
due_days AS (
  SELECT DISTINCT ldd.due_date::date AS d
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.is_deleted = false
    AND ldd.component_type IN ('PRIN', 'INT')
),
closed_slices AS (
  SELECT da.end_date::date AS end_d,
         da.accrual_posting_date IS NOT NULL AS posted,
         da.billing_posting_date IS NOT NULL AS billed,
         da.total_accrued_amount
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id
    AND da.is_deleted = false
    AND da.total_accrued_amount > 0
    AND da.end_date::date <= p.biz
),
posting_class AS (
  SELECT cs.*,
         (EXTRACT(DAY FROM cs.end_d) = EXTRACT(DAY FROM (
           date_trunc('month', cs.end_d) + interval '1 month - 1 day'))) AS is_month_end,
         EXISTS (SELECT 1 FROM due_days dd WHERE dd.d = cs.end_d) AS is_emi_due
  FROM closed_slices cs
),
gates AS (
  SELECT
    COUNT(*) FILTER (WHERE is_month_end AND NOT posted) AS month_end_unposted,
    COUNT(*) FILTER (WHERE is_month_end AND posted) AS month_end_posted,
    COUNT(*) FILTER (WHERE is_emi_due AND NOT is_month_end AND NOT posted) AS emi_due_unposted,
    COUNT(*) FILTER (WHERE is_emi_due AND NOT is_month_end AND posted) AS emi_due_posted,
    COUNT(*) FILTER (WHERE (is_month_end OR is_emi_due) AND NOT posted) AS any_boundary_unposted,
    COUNT(*) FILTER (WHERE posted) AS total_posted_slices,
    COUNT(*) FILTER (WHERE billed) AS total_billed_slices
  FROM posting_class
  WHERE is_month_end OR is_emi_due
),
amounts AS (
  SELECT
    COALESCE(SUM(total_accrued_amount), 0) AS accrued,
    COALESCE(SUM(total_accrued_amount) FILTER (WHERE accrual_posting_date IS NOT NULL), 0) AS posted,
    COALESCE(SUM(total_accrued_amount) FILTER (WHERE billing_posting_date IS NOT NULL), 0) AS billed
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id AND da.is_deleted = false
),
dpi_due_total AS (
  SELECT COALESCE(SUM(due_amount), 0) AS dpi_due
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.component_type = 'DPI'
    AND ldd.is_deleted = false
)
SELECT
  g.month_end_unposted,
  g.month_end_posted,
  g.emi_due_unposted,
  g.emi_due_posted,
  g.any_boundary_unposted,
  g.total_posted_slices,
  g.total_billed_slices,
  a.accrued,
  a.posted,
  a.billed,
  d.dpi_due,
  (ABS(a.billed - d.dpi_due) <= 0.001 AND a.posted >= a.billed) AS billing_full_parity
FROM gates g, amounts a, dpi_due_total d;
