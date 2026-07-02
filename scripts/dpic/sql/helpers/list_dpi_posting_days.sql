\set ON_ERROR_STOP on

-- EMI due dates (PRIN/INT) and month-ends between go_live and end_date (inclusive).
WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id,
         :'go_live_date'::date AS go_live,
         :'end_date'::date AS end_d
),
due_days AS (
  SELECT DISTINCT ldd.due_date::date AS d
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.is_deleted = false
    AND ldd.component_type IN ('PRIN', 'INT')
    AND ldd.due_date::date BETWEEN p.go_live AND p.end_d
),
month_ends AS (
  SELECT gs.d::date AS d
  FROM params p
  CROSS JOIN generate_series(p.go_live, p.end_d, interval '1 day') AS gs(d)
  WHERE EXTRACT(DAY FROM gs.d::date) =
        EXTRACT(DAY FROM (date_trunc('month', gs.d::date) + interval '1 month - 1 day'))
)
SELECT d FROM (
  SELECT d FROM due_days
  UNION
  SELECT d FROM month_ends
) u
ORDER BY d;
