-- Full DPI pipeline column audit — every table touched by calc / booking / billing.
-- Exit non-zero via shell when violation_count > 0.
\set ON_ERROR_STOP on

WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id,
         :'business_date'::date AS biz
),
active_slices AS (
  SELECT da.*
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id AND da.is_deleted = false
),
-- 1) No duplicate (installment, start, end) among active rows
dup_slices AS (
  SELECT installment_id, start_date::date, end_date::date
  FROM active_slices
  WHERE total_accrued_amount > 0
  GROUP BY installment_id, start_date::date, end_date::date
  HAVING COUNT(*) > 1
),
-- 2) Sequential slices per installment: start[i] must equal end[i-1] (inclusive boundary model)
ordered AS (
  SELECT installment_id,
         start_date::date AS start_d,
         end_date::date AS end_d,
         LAG(end_date::date) OVER (PARTITION BY installment_id ORDER BY end_date, id) AS prev_end
  FROM active_slices
  WHERE total_accrued_amount > 0
),
bad_sequence AS (
  SELECT * FROM ordered
  WHERE prev_end IS NOT NULL AND start_d <> prev_end
),
-- 3) end_date must be month-end or EMI due day when amount > 0 and closed
due_days AS (
  SELECT DISTINCT ldd.due_date::date AS d
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id AND ldd.is_deleted = false
    AND ldd.component_type IN ('PRIN', 'INT')
),
bad_end_boundary AS (
  SELECT o.installment_id, o.end_d
  FROM ordered o
  CROSS JOIN params p
  WHERE o.end_d <= p.biz
    AND NOT (
      EXTRACT(DAY FROM o.end_d) = EXTRACT(DAY FROM (date_trunc('month', o.end_d) + interval '1 month - 1 day'))
      OR EXISTS (SELECT 1 FROM due_days dd WHERE dd.d = o.end_d)
    )
),
-- 4) Posted slice must have accrual_posting_date + ref; GL amount + value_date = end_date
posted AS (
  SELECT da.id, da.end_date::date AS end_d, da.total_accrued_amount,
         da.accrual_transaction_ref_number AS ref
  FROM active_slices da
  WHERE da.accrual_posting_date IS NOT NULL AND da.total_accrued_amount > 0
),
gl_mismatch AS (
  SELECT p.id
  FROM posted p
  LEFT JOIN mfi_accounting.transaction_master tm ON tm.reference_number = p.ref
  WHERE p.ref IS NULL
     OR tm.id IS NULL
     OR tm.original_amount <> p.total_accrued_amount
     OR tm.value_date::date <> p.end_d
),
-- 5) Billed rows: billing_posting_date set; DPI due exists; sum per installment matches
billed_slices AS (
  SELECT installment_id, COALESCE(SUM(total_accrued_amount), 0) AS billed_accrued
  FROM active_slices
  WHERE billing_posting_date IS NOT NULL AND total_accrued_amount > 0
  GROUP BY installment_id
),
dpi_due AS (
  SELECT ldd.loan_installment_details_id AS inst_id,
         ldd.due_date::date AS due_d,
         ldd.due_amount,
         ldd.component_type
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id AND ldd.is_deleted = false AND ldd.component_type = 'DPI'
),
billing_due_mismatch AS (
  SELECT b.installment_id
  FROM billed_slices b
  LEFT JOIN dpi_due d ON d.inst_id = b.installment_id
  GROUP BY b.installment_id, b.billed_accrued
  HAVING ABS(b.billed_accrued - COALESCE(SUM(d.due_amount), 0)) > 0.001
),
-- 6) Unposted closed boundary slices
unposted_closed AS (
  SELECT da.id
  FROM active_slices da
  CROSS JOIN params p
  WHERE da.total_accrued_amount > 0
    AND da.end_date::date <= p.biz
    AND da.accrual_posting_date IS NULL
    AND (
      EXTRACT(DAY FROM da.end_date::date) = EXTRACT(DAY FROM (
        date_trunc('month', da.end_date::date) + interval '1 month - 1 day'))
      OR EXISTS (
        SELECT 1 FROM due_days dd WHERE dd.d = da.end_date::date
      )
    )
),
violations AS (
  SELECT 'duplicate_slice_key' AS rule, COUNT(*)::bigint AS n FROM dup_slices
  UNION ALL SELECT 'start_not_chain_to_prev_end', COUNT(*) FROM bad_sequence
  UNION ALL SELECT 'end_not_month_end_or_emi', COUNT(*) FROM bad_end_boundary
  UNION ALL SELECT 'posted_gl_mismatch', COUNT(*) FROM gl_mismatch
  UNION ALL SELECT 'billed_vs_dpi_due_mismatch', COUNT(*) FROM billing_due_mismatch
  UNION ALL SELECT 'unposted_closed_boundary', COUNT(*) FROM unposted_closed
)
SELECT COALESCE(SUM(n), 0) AS violation_count,
       COALESCE(string_agg(rule || '=' || n::text, ', ' ORDER BY rule), '') AS detail
FROM violations WHERE n > 0;

\echo '=== active slice count (expect one row per accrual WINDOW not per EMI) ==='
SELECT COUNT(*) AS active_slices,
       COUNT(DISTINCT installment_id) AS installments
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint AND is_deleted = false AND total_accrued_amount > 0;

\echo '=== soft-deleted rows (old runs — ignore or hard-purge) ==='
SELECT COUNT(*) AS soft_deleted_slices
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint AND is_deleted = true;

\echo '=== dpi_accrual_details (active) ==='
SELECT id, installment_id, start_date::date, end_date::date, base_amount, total_accrued_amount,
       dpi_annual_rate, days_in_year, carry_over_amount,
       accrual_posting_date::date, accrual_transaction_ref_number,
       billing_posting_date::date, billing_transaction_ref_number
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint AND is_deleted = false AND total_accrued_amount > 0
ORDER BY installment_id, end_date;

\echo '=== transaction_master (DPI accrual refs) ==='
SELECT tm.reference_number, tm.original_amount, tm.value_date::date, tm.client_reference_number
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = da.accrual_transaction_ref_number
WHERE da.loan_account_id = :loan_account_id::bigint AND da.is_deleted = false
  AND da.accrual_posting_date IS NOT NULL
ORDER BY tm.value_date;

\echo '=== loan_due_details DPI ==='
SELECT id, loan_installment_details_id, due_date::date, due_amount, paid_amount, waived_amount, base_amount
FROM mfi_accounting.loan_due_details
WHERE loan_account_id = :loan_account_id::bigint AND component_type = 'DPI' AND is_deleted = false
ORDER BY due_date;
