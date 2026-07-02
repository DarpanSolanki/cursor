-- Column-level DPI accrual slice integrity (local regression gate).
-- Fails when start_date resets to EMI due after a prior posted slice (SDCP-class bug).
\set ON_ERROR_STOP on

WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id
),
slices AS (
  SELECT da.id,
         da.installment_id,
         da.start_date::date AS start_d,
         da.end_date::date AS end_d,
         da.base_amount,
         da.total_accrued_amount,
         da.accrual_posting_date::date AS posted_d,
         da.billing_posting_date::date AS billed_d,
         LAG(da.end_date::date) OVER (
           PARTITION BY da.installment_id ORDER BY da.end_date, da.id
         ) AS prev_end_d
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id
    AND da.is_deleted = false
    AND da.total_accrued_amount > 0
),
violations AS (
  SELECT id, 'start_not_before_end' AS rule
  FROM slices WHERE start_d >= end_d
  UNION ALL
  SELECT id, 'start_before_prev_end'
  FROM slices
  WHERE prev_end_d IS NOT NULL AND start_d < prev_end_d
  UNION ALL
  SELECT s.id, 'posted_slice_missing_posting_date'
  FROM slices s
  WHERE s.end_d <= :'business_date'::date
    AND (
      EXTRACT(DAY FROM s.end_d) = EXTRACT(DAY FROM (
        date_trunc('month', s.end_d) + interval '1 month - 1 day'))
      OR EXISTS (
        SELECT 1 FROM mfi_accounting.loan_due_details ldd
        CROSS JOIN params p
        WHERE ldd.loan_account_id = p.loan_id
          AND ldd.is_deleted = false
          AND ldd.component_type IN ('PRIN', 'INT')
          AND ldd.due_date::date = s.end_d
      )
    )
    AND s.posted_d IS NULL
)
SELECT COUNT(*) AS violation_count,
       COALESCE(string_agg(DISTINCT rule, ', '), '') AS rules
FROM violations;

\echo '=== slice timeline ==='
SELECT installment_id, start_date::date, end_date::date, total_accrued_amount,
       accrual_posting_date::date, billing_posting_date::date
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false AND total_accrued_amount > 0
ORDER BY installment_id, end_date;
