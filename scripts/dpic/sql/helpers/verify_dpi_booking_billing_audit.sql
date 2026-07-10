-- Booking + billing column audit (after slice_integrity passes).
-- Requires :loan_account_id and :business_date (YYYY-MM-DD).
-- Catches 2540301-class: sealed EMI/month-end slice with amount>0 but accrual_posting_date NULL.
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
slices AS (
  SELECT da.id,
         da.end_date::date AS end_d,
         da.total_accrued_amount,
         da.accrual_posting_date::date AS posted_d,
         da.billing_posting_date::date AS billed_d,
         da.accrual_transaction_ref_number AS ref
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id AND da.is_deleted = false
    AND da.total_accrued_amount > 0
),
posted_slices AS (
  SELECT * FROM slices WHERE posted_d IS NOT NULL
),
violations AS (
  -- Sealed posting anchors (month-end OR any INT/PRIN due) must be booked.
  -- Open windows ending on a non-anchor business day are not yet sealed — do not flag.
  SELECT s.id, 'sealed_unposted' AS rule
  FROM slices s
  CROSS JOIN params p
  WHERE s.end_d <= p.biz AND s.posted_d IS NULL
    AND (
      EXTRACT(DAY FROM s.end_d) = EXTRACT(DAY FROM (date_trunc('month', s.end_d) + interval '1 month - 1 day'))
      OR EXISTS (SELECT 1 FROM due_days d WHERE d.d = s.end_d)
    )
  UNION ALL
  -- After billing: EMI-seal days (or month-end once next EMI due has arrived) must be billed.
  -- Exception: month-end seal before next INT/PRIN due day may remain unbilled (billing calendar).
  SELECT s.id, 'sealed_unbilled'
  FROM slices s
  CROSS JOIN params p
  WHERE s.end_d <= p.biz
    AND s.posted_d IS NOT NULL
    AND s.billed_d IS NULL
    AND (
      EXISTS (SELECT 1 FROM due_days d WHERE d.d = s.end_d)
      OR EXISTS (SELECT 1 FROM due_days d WHERE d.d > s.end_d AND d.d <= p.biz)
    )
  UNION ALL
  SELECT ps.id, 'posted_gl_amount_mismatch'
  FROM posted_slices ps
  JOIN mfi_accounting.transaction_master tm ON tm.reference_number = ps.ref
  WHERE tm.original_amount IS DISTINCT FROM ps.total_accrued_amount
     OR tm.transaction_value_date::date IS DISTINCT FROM ps.end_d
  UNION ALL
  SELECT ps.id, 'posted_missing_transaction_master'
  FROM posted_slices ps
  WHERE ps.ref IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_master tm WHERE tm.reference_number = ps.ref)
  UNION ALL
  SELECT gl.id, 'posted_gl_legs_not_balanced'
  FROM (
    SELECT ps.id, tm.id AS tm_id
    FROM posted_slices ps
    JOIN mfi_accounting.transaction_master tm ON tm.reference_number = ps.ref
  ) gl
  JOIN mfi_accounting.transaction_details td ON td.transaction_id = gl.tm_id
  GROUP BY gl.id, gl.tm_id
  HAVING ABS(
    COALESCE(SUM(CASE WHEN td.cr_dr_indicator IN ('C', 'CREDIT') THEN td.net_amount ELSE 0 END), 0)
    - COALESCE(SUM(CASE WHEN td.cr_dr_indicator IN ('D', 'DEBIT') THEN td.net_amount ELSE 0 END), 0)
  ) > 0.01
  UNION ALL
  SELECT NULL::bigint, 'billed_accrued_vs_dpi_due_mismatch'
  FROM (
    SELECT COALESCE(SUM(total_accrued_amount), 0) AS billed_accrued
    FROM mfi_accounting.dpi_accrual_details da CROSS JOIN params p
    WHERE da.loan_account_id = p.loan_id AND da.is_deleted = false
      AND da.billing_posting_date IS NOT NULL AND da.total_accrued_amount > 0
  ) b
  CROSS JOIN (
    SELECT COALESCE(SUM(due_amount), 0) AS dpi_due
    FROM mfi_accounting.loan_due_details ldd CROSS JOIN params p
    WHERE ldd.loan_account_id = p.loan_id AND ldd.component_type = 'DPI' AND ldd.is_deleted = false
  ) d
  WHERE ABS(b.billed_accrued - d.dpi_due) > 0.001 AND b.billed_accrued > 0
)
SELECT COUNT(*) AS violation_count,
       COALESCE(string_agg(DISTINCT rule, ', ' ORDER BY rule), '') AS rules
FROM violations;
