-- DOCUMENTED BYPASS (not for passing tests): calc-window anchor seed for
-- DpiAccrualCalculationBatchService installment lookup bug (next future EMI vs earliest overdue).
-- Prefer real dpiAccrualCalculation jobs; enable only via SEED_CALC_WINDOW=1 on run_eod*.sh.
-- Seeds zero-amount anchor row so calc window [last_end .. business_date] is valid. Remove when L1 lands.
--
-- Usage: psql ... -v loan_account_id=8055060 -v business_date_ms=1781267400000 \
--        -f scripts/dpic/sql/helpers/seed_calc_window.sql

\set ON_ERROR_STOP on

BEGIN;

-- Remove prior seed rows only (not real calc output)
UPDATE mfi_accounting.dpi_accrual_details
SET is_deleted = true
WHERE loan_account_id = :loan_account_id
  AND accrual_posting_date IS NULL
  AND billing_posting_date IS NULL
  AND total_accrued_amount = 0
  AND is_deleted = false;

WITH first_overdue AS (
  SELECT lid.id AS installment_id,
         lid.installment_date AS overdue_date,
         COALESCE(aid.effective_rate, 0) AS rate,
         COALESCE(psfd.interest_calculation_days_in_year, 'DIM_365') AS days_in_year
  FROM mfi_accounting.loan_installment_details lid
  JOIN mfi_accounting.loan_account la ON la.account_id = lid.loan_account_id
  LEFT JOIN mfi_accounting.account_interest_details aid ON aid.account_id = la.account_id
  LEFT JOIN mfi_accounting.product_scheme_frequency_details psfd
    ON psfd.product_scheme_id = la.la_product_scheme_id
   AND psfd.interest_frequency = la.repayment_frequency
   AND psfd.is_deleted = false
  WHERE lid.loan_account_id = :loan_account_id
    AND lid.is_deleted = false
    AND lid.is_settled = false
    AND lid.installment_date <= TO_TIMESTAMP(:business_date_ms::bigint / 1000.0)
  ORDER BY lid.installment_date ASC
  LIMIT 1
)
INSERT INTO mfi_accounting.dpi_accrual_details (
  loan_account_id, installment_id, base_amount,
  start_date, end_date, dpi_annual_rate, days_in_year, total_accrued_amount, is_deleted
)
SELECT
  :loan_account_id,
  fo.installment_id,
  0,
  fo.overdue_date,
  fo.overdue_date,
  fo.rate,
  CASE fo.days_in_year WHEN 'DIM_360' THEN 360 WHEN 'DIM_365' THEN 365 ELSE 365 END,
  0,
  false
FROM first_overdue fo
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.dpi_accrual_details d
  WHERE d.loan_account_id = :loan_account_id AND d.is_deleted = false
);

COMMIT;

\echo '=== calc window seed for loan' :loan_account_id '===' 
SELECT id, installment_id, start_date, end_date, total_accrued_amount, accrual_posting_date
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id AND is_deleted = false
ORDER BY id DESC LIMIT 3;
