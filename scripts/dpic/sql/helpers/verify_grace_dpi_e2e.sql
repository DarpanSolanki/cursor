-- Assert DPI grace gate after dpiAccrualCalculation.
-- Vars: loan_account_id, first_emi_due_date (YYYY-MM-DD), grace_days
-- Bash asserts the single flag column (psql variables cannot be used inside DO $$).
\set ON_ERROR_STOP on

\echo '=== grace E2E verify ==='

WITH cfg AS (
  SELECT :loan_account_id::bigint AS loan_id,
         :'first_emi_due_date'::date AS first_due,
         :grace_days::int AS grace
),
gate AS (
  SELECT loan_id, first_due, first_due + (grace + 1) AS gate_end_date
  FROM cfg
),
first_accrual AS (
  SELECT d.start_date::date AS start_date,
         d.end_date::date AS end_date,
         d.total_accrued_amount
  FROM mfi_accounting.dpi_accrual_details d
  CROSS JOIN cfg
  WHERE d.loan_account_id = cfg.loan_id
    AND d.is_deleted = false
    AND d.total_accrued_amount > 0
  ORDER BY d.end_date ASC
  LIMIT 1
),
checks AS (
  SELECT
    (SELECT COUNT(*) FROM mfi_accounting.dpi_accrual_details d CROSS JOIN gate g
      WHERE d.loan_account_id = g.loan_id AND d.is_deleted = false
        AND d.total_accrued_amount > 0 AND d.end_date::date <= g.gate_end_date) AS accruals_inside_grace,
    (SELECT start_date FROM first_accrual) AS first_start,
    (SELECT end_date FROM first_accrual) AS first_end,
    (SELECT total_accrued_amount FROM first_accrual) AS first_amount,
    (SELECT first_due FROM gate) AS expected_start,
    (SELECT gate_end_date FROM gate) AS gate_end
)
SELECT accruals_inside_grace,
       first_start,
       first_end,
       first_amount,
       expected_start,
       gate_end,
       (
         first_start IS NOT NULL
         AND accruals_inside_grace = 0
         AND first_start = expected_start
         AND first_end > gate_end
       ) AS grace_ok
FROM checks;
