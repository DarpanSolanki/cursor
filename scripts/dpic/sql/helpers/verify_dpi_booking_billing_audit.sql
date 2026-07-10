-- Booking + billing column audit (after slice_integrity passes).
\set ON_ERROR_STOP on

WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id
),
posted_slices AS (
  SELECT da.id, da.end_date::date AS end_d, da.total_accrued_amount,
         da.accrual_transaction_ref_number AS ref,
         da.billing_posting_date IS NOT NULL AS billed
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id AND da.is_deleted = false
    AND da.accrual_posting_date IS NOT NULL AND da.total_accrued_amount > 0
),
violations AS (
  SELECT ps.id, 'posted_gl_amount_mismatch' AS rule
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
