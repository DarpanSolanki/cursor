-- Column-level DPI accrual slice integrity (local regression gate).
-- Fails when start_date resets to EMI due after a prior posted slice (SDCP-class bug).
\set ON_ERROR_STOP on

WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id
),
grace_cfg AS (
  SELECT psfd.grace_period
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.product_scheme_frequency_details psfd
    ON psfd.product_scheme_id = la.la_product_scheme_id
   AND psfd.interest_frequency = la.repayment_frequency
   AND psfd.is_deleted = false
  CROSS JOIN params p
  WHERE la.account_id = p.loan_id
  LIMIT 1
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
emi_dues AS (
  SELECT ldd.loan_installment_details_id AS installment_id,
         ldd.due_date::date AS due_day,
         ROW_NUMBER() OVER (ORDER BY ldd.due_date) AS rn
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  CROSS JOIN grace_cfg g
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.is_deleted = false
    AND ldd.component_type = 'INT'
    AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
  GROUP BY ldd.loan_installment_details_id, ldd.due_date
),
violations AS (
  SELECT id, 'start_not_before_end' AS rule
  FROM slices WHERE start_d > end_d
  UNION ALL
  -- Continuation slice must start strictly after prior sealed end (next calendar day).
  SELECT id, 'start_before_prev_end'
  FROM slices
  WHERE prev_end_d IS NOT NULL AND start_d <= prev_end_d
  UNION ALL
  -- Must not seal only on overdue-admission day (grace+1); anchors are EMI due or month-end.
  SELECT s.id, 'seal_on_overdue_admission_only'
  FROM slices s
  JOIN mfi_accounting.loan_due_details ldd
    ON ldd.loan_installment_details_id = s.installment_id
   AND ldd.is_deleted = false
   AND ldd.component_type = 'INT'
  CROSS JOIN params p
  CROSS JOIN grace_cfg g
  WHERE ldd.loan_account_id = p.loan_id
    AND s.end_d = (ldd.due_date::date + (g.grace_period + 1) * interval '1 day')::date
    AND s.end_d <> ldd.due_date::date
    AND s.end_d <> (date_trunc('month', s.end_d) + interval '1 month - 1 day')::date
  UNION ALL
  -- Duplicate first-slice stamp on same installment.
  SELECT s.id, 'duplicate_installment_start'
  FROM slices s
  WHERE EXISTS (
    SELECT 1 FROM slices s2
    WHERE s2.installment_id = s.installment_id
      AND s2.id < s.id
      AND s2.start_d = s.start_d
  )
  UNION ALL
  -- Two May slices on same installment (May duplicate regression).
  SELECT s.id, 'duplicate_may_month_slice'
  FROM slices s
  WHERE EXTRACT(MONTH FROM s.start_d) = 5
    AND EXISTS (
      SELECT 1 FROM slices s2
      WHERE s2.installment_id = s.installment_id
        AND s2.id <> s.id
        AND EXTRACT(MONTH FROM s2.start_d) = 5
        AND EXTRACT(YEAR FROM s2.start_d) = EXTRACT(YEAR FROM s.start_d)
    )
  UNION ALL
  -- No grace-overlap micro-slice (SDCP-11030): EMI1 must not split Jun15-17 tail during EMI2 grace.
  SELECT s.id, 'grace_overlap_micro_slice'
  FROM slices s
  JOIN emi_dues e1 ON e1.rn = 1
  JOIN emi_dues e2 ON e2.rn = 2
  CROSS JOIN grace_cfg g
  WHERE s.installment_id = e1.installment_id
    AND s.start_d > e2.due_day
    AND s.end_d < (e2.due_day + (g.grace_period + 1) * interval '1 day')::date
    AND EXISTS (
      SELECT 1 FROM slices s2
      WHERE s2.installment_id = s.installment_id
        AND s2.id <> s.id
        AND s2.end_d = e2.due_day
    )
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
