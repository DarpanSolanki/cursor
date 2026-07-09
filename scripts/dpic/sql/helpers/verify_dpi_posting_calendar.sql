\set ON_ERROR_STOP on

-- Rows sealed on a posting anchor (this EMI's INT due or month-end) must be GL-posted by business_date.
-- In-flight slices ending on another EMI's due day are not posting anchors (interest/DPI parity).
WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id,
         :'business_date'::date AS biz
),
rows AS (
  SELECT da.id,
         da.installment_id,
         da.end_date::date AS end_d,
         da.accrual_posting_date IS NOT NULL AS posted
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id
    AND da.is_deleted = false
    AND da.total_accrued_amount > 0
    AND da.end_date::date <= p.biz
),
should_have_posted AS (
  SELECT r.id,
         r.posted
  FROM rows r
  WHERE EXTRACT(DAY FROM r.end_d) = EXTRACT(DAY FROM (
          date_trunc('month', r.end_d) + interval '1 month - 1 day'))
     OR EXISTS (
          SELECT 1
          FROM mfi_accounting.loan_due_details ldd
          WHERE ldd.loan_installment_details_id = r.installment_id
            AND ldd.is_deleted = false
            AND ldd.component_type = 'INT'
            AND ldd.due_date::date = r.end_d
        )
)
SELECT COUNT(*) FILTER (WHERE NOT posted) AS unposted_on_posting_day,
       COUNT(*) FILTER (WHERE posted) AS posted_rows,
       COUNT(*) AS closed_rows
FROM should_have_posted;
