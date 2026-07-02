\set ON_ERROR_STOP on

-- Rows closed by business_date must be GL-posted if any EMI-due or month-end day fell on or after
-- closure (exclusive end_date) through business_date. Matches DpiAccrualBookingBatchService gate
-- on businessDate (not dayBefore(end_date)).
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
bounds AS (
  SELECT p.loan_id,
         p.biz,
         LEAST(
           p.biz,
           COALESCE(
             (SELECT MIN(da.end_date::date)
              FROM mfi_accounting.dpi_accrual_details da
              WHERE da.loan_account_id = p.loan_id
                AND da.is_deleted = false
                AND da.total_accrued_amount > 0),
             p.biz
           )
         ) AS range_start
  FROM params p
),
posting_days AS (
  SELECT gs.d::date AS d
  FROM bounds b
  CROSS JOIN generate_series(b.range_start, b.biz, interval '1 day') AS gs(d)
  WHERE EXTRACT(DAY FROM gs.d::date) =
        EXTRACT(DAY FROM (date_trunc('month', gs.d::date) + interval '1 month - 1 day'))
     OR EXISTS (SELECT 1 FROM due_days dd WHERE dd.d = gs.d::date)
),
rows AS (
  SELECT da.id,
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
  CROSS JOIN params p
  WHERE EXISTS (
    SELECT 1
    FROM posting_days pd
    WHERE pd.d >= r.end_d
      AND pd.d <= p.biz
  )
)
SELECT COUNT(*) FILTER (WHERE NOT posted) AS unposted_on_posting_day,
       COUNT(*) FILTER (WHERE posted) AS posted_rows,
       COUNT(*) AS closed_rows
FROM should_have_posted;
