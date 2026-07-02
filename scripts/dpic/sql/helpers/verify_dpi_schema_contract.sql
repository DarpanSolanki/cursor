-- Exhaustive DPI table contract — every populated column on active rows (calc/book/bill path).
-- Exit non-zero via shell when violation_count > 0.
\set ON_ERROR_STOP on

WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id,
         :'business_date'::date AS biz
),
active AS (
  SELECT da.*
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id AND da.is_deleted = false AND da.total_accrued_amount > 0
),
accrual_viol AS (
  SELECT 'accrual_null_loan_or_installment' AS rule, COUNT(*)::bigint AS n
  FROM active WHERE loan_account_id IS NULL OR installment_id IS NULL
  UNION ALL SELECT 'accrual_null_window', COUNT(*) FROM active WHERE start_date IS NULL OR end_date IS NULL
  UNION ALL SELECT 'accrual_null_base_or_rate', COUNT(*) FROM active
    WHERE base_amount IS NULL OR dpi_annual_rate IS NULL OR days_in_year IS NULL
  UNION ALL SELECT 'accrual_null_amount_or_carry', COUNT(*) FROM active
    WHERE total_accrued_amount IS NULL OR carry_over_amount IS NULL
  UNION ALL SELECT 'accrual_start_after_end', COUNT(*) FROM active WHERE start_date::date > end_date::date
  UNION ALL SELECT 'accrual_posted_missing_ref', COUNT(*) FROM active
    WHERE accrual_posting_date IS NOT NULL AND (accrual_transaction_ref_number IS NULL OR btrim(accrual_transaction_ref_number) = '')
  UNION ALL SELECT 'accrual_posting_date_ne_end', COUNT(*) FROM active
    WHERE accrual_posting_date IS NOT NULL AND accrual_posting_date::date IS DISTINCT FROM end_date::date
  UNION ALL SELECT 'accrual_billed_missing_ref', COUNT(*) FROM active
    WHERE billing_posting_date IS NOT NULL AND (billing_transaction_ref_number IS NULL OR btrim(billing_transaction_ref_number) = '')
  UNION ALL SELECT 'accrual_billed_not_posted', COUNT(*) FROM active
    WHERE billing_posting_date IS NOT NULL AND accrual_posting_date IS NULL
  UNION ALL SELECT 'accrual_closed_unposted_boundary', COUNT(*) FROM active a
  CROSS JOIN params p
  WHERE a.end_date::date <= p.biz
    AND a.accrual_posting_date IS NULL
    AND (
      EXTRACT(DAY FROM a.end_date::date) = EXTRACT(DAY FROM (date_trunc('month', a.end_date::date) + interval '1 month - 1 day'))
      OR EXISTS (
        SELECT 1 FROM mfi_accounting.loan_due_details ldd
        WHERE ldd.loan_account_id = p.loan_id AND ldd.is_deleted = false
          AND ldd.component_type IN ('PRIN','INT') AND ldd.due_date::date = a.end_date::date
      )
    )
),
dpi_due AS (
  SELECT ldd.*
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id AND ldd.component_type = 'DPI' AND ldd.is_deleted = false
),
due_viol AS (
  SELECT 'dpi_due_null_installment' AS rule, COUNT(*)::bigint AS n FROM dpi_due WHERE loan_installment_details_id IS NULL
  UNION ALL SELECT 'dpi_due_null_dates', COUNT(*) FROM dpi_due WHERE due_date IS NULL OR overdue_date IS NULL
  UNION ALL SELECT 'dpi_due_null_amounts', COUNT(*) FROM dpi_due
    WHERE base_amount IS NULL OR due_amount IS NULL OR paid_amount IS NULL OR waived_amount IS NULL
  UNION ALL SELECT 'dpi_due_base_ne_due', COUNT(*) FROM dpi_due WHERE base_amount <> due_amount
  UNION ALL SELECT 'dpi_due_nonzero_paid_waived', COUNT(*) FROM dpi_due
    WHERE COALESCE(paid_amount, 0) <> 0 OR COALESCE(waived_amount, 0) <> 0
  UNION ALL SELECT 'dpi_due_audit_null', COUNT(*) FROM dpi_due
    WHERE created_on IS NULL OR updated_on IS NULL OR created_by IS NULL OR updated_by IS NULL
  UNION ALL SELECT 'dpi_due_installment_mismatch', COUNT(*)
  FROM dpi_due d
  JOIN mfi_accounting.loan_installment_details lid ON lid.id = d.loan_installment_details_id
  WHERE d.due_date::date <> lid.installment_date::date
),
violations AS (
  SELECT rule, n FROM accrual_viol WHERE n > 0
  UNION ALL SELECT rule, n FROM due_viol WHERE n > 0
)
SELECT COALESCE(SUM(n), 0) AS violation_count,
       COALESCE(string_agg(rule || '=' || n::text, ', ' ORDER BY rule), '') AS detail
FROM violations;

\echo '=== schema contract summary ==='
SELECT COUNT(*) AS accrual_rows,
       COUNT(*) FILTER (WHERE accrual_posting_date IS NOT NULL) AS posted_rows,
       COUNT(*) FILTER (WHERE billing_posting_date IS NOT NULL) AS billed_rows
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint AND is_deleted = false AND total_accrued_amount > 0;

SELECT COUNT(*) AS dpi_due_rows, COALESCE(SUM(due_amount), 0) AS dpi_due_total
FROM mfi_accounting.loan_due_details
WHERE loan_account_id = :loan_account_id::bigint AND component_type = 'DPI' AND is_deleted = false;
