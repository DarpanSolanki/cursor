-- When demo EOD runs on a future business anchor but loanRepayment requires repayment_time = today,
-- shift schedule + dues + DPI accrual dates back so the first unpaid EMI is ~35 days before today.
--
-- Usage: psql ... -v loan_account_id=8059260 -f shift_demo_schedule_for_repay_today.sql

\set ON_ERROR_STOP on

BEGIN;

WITH bounds AS (
  SELECT
    MIN(lid.installment_date::date) AS first_emi,
    (CURRENT_DATE - 35)::date AS target_first_emi
  FROM mfi_accounting.loan_installment_details lid
  WHERE lid.loan_account_id = :'loan_account_id'::bigint
    AND lid.is_deleted = false
    AND lid.is_settled = false
),
shift AS (
  SELECT (first_emi - target_first_emi) AS days
  FROM bounds
  WHERE first_emi IS NOT NULL AND first_emi > CURRENT_DATE
)
UPDATE mfi_accounting.loan_installment_details lid
SET installment_date = lid.installment_date - (s.days || ' days')::interval,
    overdue_date = lid.overdue_date - (s.days || ' days')::interval
FROM shift s
WHERE lid.loan_account_id = :'loan_account_id'::bigint
  AND lid.is_deleted = false
  AND s.days > 0;

WITH bounds AS (
  SELECT
    MIN(lid.installment_date::date) AS first_emi,
    (CURRENT_DATE - 35)::date AS target_first_emi
  FROM mfi_accounting.loan_installment_details lid
  WHERE lid.loan_account_id = :'loan_account_id'::bigint
    AND lid.is_deleted = false
    AND lid.is_settled = false
),
shift AS (
  SELECT (first_emi - target_first_emi) AS days
  FROM bounds
  WHERE first_emi IS NOT NULL
)
UPDATE mfi_accounting.loan_due_details ldd
SET due_date = ldd.due_date - (s.days || ' days')::interval,
    overdue_date = ldd.overdue_date - (s.days || ' days')::interval
FROM shift s
WHERE ldd.loan_account_id = :'loan_account_id'::bigint
  AND ldd.is_deleted = false
  AND s.days > 0;

WITH bounds AS (
  SELECT
    MIN(lid.installment_date::date) AS first_emi,
    (CURRENT_DATE - 35)::date AS target_first_emi
  FROM mfi_accounting.loan_installment_details lid
  WHERE lid.loan_account_id = :'loan_account_id'::bigint
    AND lid.is_deleted = false
    AND lid.is_settled = false
),
shift AS (
  SELECT (first_emi - target_first_emi) AS days
  FROM bounds
  WHERE first_emi IS NOT NULL
)
UPDATE mfi_accounting.dpi_accrual_details d
SET start_date = d.start_date - (s.days || ' days')::interval,
    end_date = d.end_date - (s.days || ' days')::interval
FROM shift s
WHERE d.loan_account_id = :'loan_account_id'::bigint
  AND d.is_deleted = false
  AND s.days > 0;

COMMIT;

\echo '=== schedule shifted for repay-today (loan' :loan_account_id ') ==='
SELECT serial_number, installment_date::date, overdue_date::date
FROM mfi_accounting.loan_installment_details
WHERE loan_account_id = :'loan_account_id'::bigint AND is_deleted = false
ORDER BY serial_number LIMIT 3;
