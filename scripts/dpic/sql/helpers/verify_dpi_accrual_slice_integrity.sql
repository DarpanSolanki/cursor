-- Column-level DPI accrual slice integrity (local regression gate).
-- Canonical slice/start/end rules — column audit reuses via run_dpi_column_audit.sh.
\set ON_ERROR_STOP on

WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id,
         :'business_date'::date AS biz
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
         da.loan_account_id,
         da.installment_id,
         da.start_date::date AS start_d,
         da.end_date::date AS end_d,
         da.total_accrued_amount,
         da.accrual_posting_date::date AS posted_d,
         da.billing_posting_date::date AS billed_d,
         LAG(da.end_date::date) OVER (
           PARTITION BY da.installment_id ORDER BY da.end_date, da.id
         ) AS prev_end_d,
         ROW_NUMBER() OVER (
           PARTITION BY da.installment_id ORDER BY da.end_date, da.id
         ) AS slice_rn
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id
    AND da.is_deleted = false
    AND da.total_accrued_amount > 0
),
due_days AS (
  SELECT DISTINCT ldd.due_date::date AS d
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.is_deleted = false
    AND ldd.component_type IN ('PRIN', 'INT')
),
emi_dues AS (
  SELECT ldd.loan_installment_details_id AS installment_id,
         ldd.due_date::date AS due_day,
         COALESCE(ldd.overdue_date::date,
           (ldd.due_date::date + ((SELECT grace_period FROM grace_cfg) + 1) * interval '1 day')::date
         ) AS admission_overdue_day,
         ROW_NUMBER() OVER (ORDER BY ldd.due_date) AS rn
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.is_deleted = false
    AND ldd.component_type = 'INT'
    AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
  GROUP BY ldd.loan_installment_details_id, ldd.due_date, ldd.overdue_date
),
first_emi AS (
  SELECT installment_id, due_day, admission_overdue_day FROM emi_dues WHERE rn = 1
),
violations AS (
  SELECT id, 'start_not_before_end' AS rule FROM slices WHERE start_d > end_d
  UNION ALL
  SELECT id, 'start_before_prev_end' FROM slices
  WHERE prev_end_d IS NOT NULL AND start_d < prev_end_d
  UNION ALL
  SELECT id, 'gap_between_slices' FROM slices
  WHERE prev_end_d IS NOT NULL AND start_d > prev_end_d + 1
  UNION ALL
  SELECT s.id, 'seal_on_overdue_admission_only'
  FROM slices s
  JOIN mfi_accounting.loan_due_details ldd
    ON ldd.loan_installment_details_id = s.installment_id
   AND ldd.is_deleted = false AND ldd.component_type = 'INT'
  CROSS JOIN params p CROSS JOIN grace_cfg g
  WHERE ldd.loan_account_id = p.loan_id
    AND s.end_d = COALESCE(ldd.overdue_date::date,
         (ldd.due_date::date + (g.grace_period + 1) * interval '1 day')::date)
    AND s.end_d <> ldd.due_date::date
    AND s.end_d <> (date_trunc('month', s.end_d) + interval '1 month - 1 day')::date
  UNION ALL
  SELECT s.id, 'duplicate_installment_start' FROM slices s
  WHERE EXISTS (
    SELECT 1 FROM slices s2
    WHERE s2.installment_id = s.installment_id AND s2.id < s.id AND s2.start_d = s.start_d
  )
  UNION ALL
  SELECT s.id, 'first_slice_not_on_emi_due'
  FROM slices s JOIN first_emi fe ON fe.installment_id = s.installment_id
  WHERE s.slice_rn = 1 AND s.start_d <> fe.due_day
  UNION ALL
  -- Sealed (month-end OR any INT/PRIN due) must be posted — mirrors booking any-EMI-due anchor.
  SELECT s.id, 'posted_slice_missing_posting_date' FROM slices s CROSS JOIN params p
  WHERE s.end_d <= p.biz
    AND s.posted_d IS NULL
    AND (
      EXTRACT(DAY FROM s.end_d) = EXTRACT(DAY FROM (date_trunc('month', s.end_d) + interval '1 month - 1 day'))
      OR EXISTS (SELECT 1 FROM due_days dd WHERE dd.d = s.end_d)
    )
  UNION ALL
  SELECT s.id, 'end_not_month_end_or_due' FROM slices s CROSS JOIN params p
  WHERE s.end_d <= p.biz AND s.posted_d IS NOT NULL
    AND NOT (EXTRACT(DAY FROM s.end_d) = EXTRACT(DAY FROM (date_trunc('month', s.end_d) + interval '1 month - 1 day'))
             OR EXISTS (SELECT 1 FROM due_days dd WHERE dd.d = s.end_d))
  UNION ALL
  SELECT s.id, 'posting_date_not_seal_anchor' FROM slices s
  WHERE s.posted_d IS NOT NULL AND s.posted_d <> s.end_d
  UNION ALL
  SELECT s.id, 'loan_account_mismatch' FROM slices s CROSS JOIN params p
  WHERE s.loan_account_id <> p.loan_id
)
SELECT COUNT(*) AS violation_count,
       COALESCE(string_agg(DISTINCT rule, ', ' ORDER BY rule), '') AS rules
FROM violations;

\echo '=== slice timeline ==='
SELECT installment_id, start_date::date, end_date::date, total_accrued_amount,
       accrual_posting_date::date, billing_posting_date::date
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false AND total_accrued_amount > 0
ORDER BY installment_id, end_date;
