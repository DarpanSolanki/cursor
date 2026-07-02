-- QA-shaped overdue prep — keep real installment schedule (no date rewrite).
-- Use on fresh-disbursed LANs; fixture LAN should use setup_simple_two_month_overdue.sql instead.
--
-- Usage: psql ... -v loan_account_id=<id> -v grace_days=3 -f setup_natural_overdue_for_dpi.sql

\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.product_scheme_frequency_details psfd
SET grace_period = :grace_days::int,
    dpi_applicable = 'YES',
    updated_on = NOW(),
    updated_by = 'DPI_NATURAL_OVERDUE'
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint
  AND psfd.product_scheme_id = la.la_product_scheme_id
  AND psfd.interest_frequency = la.repayment_frequency
  AND psfd.is_deleted = false;

UPDATE mfi_accounting.loan_account
SET loan_status = 'ACTIVE',
    updated_on = NOW(),
    updated_by = 'DPI_NATURAL_OVERDUE'
WHERE account_id = :loan_account_id::bigint
  AND is_deleted = false;

UPDATE mfi_accounting.account
SET status = 'ACTIVE',
    updated_on = NOW(),
    updated_by = 'DPI_NATURAL_OVERDUE'
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint
  AND account.id = la.account_id
  AND account.is_deleted = false;

COMMIT;

\echo '=== natural overdue prep (schedule unchanged) ==='
SELECT la.account_id, a.account_number, la.past_due_days, psfd.grace_period, psfd.dpi_applicable
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency
 AND psfd.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;

SELECT serial_number, installment_date::date, is_settled
FROM mfi_accounting.loan_installment_details
WHERE loan_account_id = :loan_account_id::bigint AND is_deleted = false
ORDER BY serial_number
LIMIT 5;
