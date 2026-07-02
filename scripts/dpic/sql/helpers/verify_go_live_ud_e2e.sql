\set ON_ERROR_STOP on

WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id,
         :'go_live_date'::date AS go_live,
         :grace_days::int AS grace,
         :'as_on'::date AS as_on
),
eligible_base AS (
  SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0) AS amount
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.is_deleted = false
    AND ldd.component_type IN ('PRIN', 'INT')
    AND ldd.due_date::date <= p.as_on
    AND (ldd.due_date::date + ((p.grace + 1) || ' days')::interval)::date >= p.go_live
    AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
),
all_overdue_base AS (
  SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0) AS amount
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.is_deleted = false
    AND ldd.component_type IN ('PRIN', 'INT')
    AND ldd.due_date::date <= p.as_on
    AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
),
latest_accrual AS (
  SELECT da.base_amount,
         da.total_accrued_amount
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id
    AND da.is_deleted = false
    AND da.total_accrued_amount > 0
  ORDER BY da.end_date DESC, da.id DESC
  LIMIT 1
)
SELECT eb.amount AS eligible_base,
       ab.amount AS all_overdue_base,
       la.base_amount AS accrual_base,
       la.total_accrued_amount AS accrual_amount,
       CASE WHEN ab.amount > eb.amount AND la.base_amount = ab.amount THEN 'FAIL_ALL_OD'
            WHEN la.base_amount IS NOT NULL AND la.base_amount <> eb.amount THEN 'FAIL_BASE_MISMATCH'
            WHEN la.base_amount IS NULL OR la.total_accrued_amount <= 0 THEN 'FAIL_NO_ACCRUAL'
            ELSE 'PASS'
       END AS verdict
FROM eligible_base eb
CROSS JOIN all_overdue_base ab
LEFT JOIN latest_accrual la ON true;
