-- Local replay: ensure first two overdue INT EMIs have outstanding > 0 for multi-EMI calc E2E.
-- Run after setup_grace_dpi_e2e.sql on demo loan (8060160 / 6004044425).
--
-- Usage:
--   psql ... -v loan_account_id=8060160 -f setup_multi_emi_dpi_e2e.sql

\set ON_ERROR_STOP on

BEGIN;

WITH first_two_int AS (
  SELECT ldd.due_date
  FROM mfi_accounting.loan_due_details ldd
  WHERE ldd.loan_account_id = :loan_account_id::bigint
    AND ldd.is_deleted = false
    AND ldd.component_type = 'INT'
  ORDER BY ldd.due_date ASC
  LIMIT 2
)
UPDATE mfi_accounting.loan_due_details ldd
SET paid_amount = 0,
    waived_amount = 0,
    updated_on = NOW(),
    updated_by = 'MULTI_EMI_E2E'
FROM first_two_int ft
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.component_type IN ('INT', 'PRIN')
  AND ldd.due_date = ft.due_date;

COMMIT;

\echo '=== multi-EMI E2E due setup ==='
SELECT ldd.loan_installment_details_id,
       ldd.component_type,
       ldd.due_date::date,
       (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) AS outstanding
FROM mfi_accounting.loan_due_details ldd
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.component_type = 'INT'
  AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
ORDER BY ldd.due_date
LIMIT 4;
