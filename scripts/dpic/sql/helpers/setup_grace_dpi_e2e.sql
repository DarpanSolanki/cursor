-- Local dev: simulate grace_period > 0 on demo overdue loan for DPI accrual calc E2E.
-- Resets dpi_accrual_details, sets grace=3, aligns PRIN/INT overdue_date to due+grace+1 (LPP).
--
-- Usage:
--   psql ... -v ON_ERROR_STOP=1 \
--     -v loan_account_id=8057160 \
--     -v grace_days=3 \
--     -f scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mfi_accounting._grace_e2e_psfd_backup (
  psfd_id       BIGINT PRIMARY KEY,
  grace_period  INT NOT NULL,
  backed_up_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO mfi_accounting._grace_e2e_psfd_backup (psfd_id, grace_period)
SELECT psfd.id, psfd.grace_period
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency
 AND psfd.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint
ON CONFLICT (psfd_id) DO UPDATE
  SET grace_period = EXCLUDED.grace_period, backed_up_at = NOW();

UPDATE mfi_accounting.product_scheme_frequency_details psfd
SET grace_period = :grace_days::int,
    updated_on = NOW(),
    updated_by = 'GRACE_DPI_E2E'
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint
  AND psfd.product_scheme_id = la.la_product_scheme_id
  AND psfd.interest_frequency = la.repayment_frequency
  AND psfd.is_deleted = false;

UPDATE mfi_accounting.loan_due_details ldd
SET overdue_date = ldd.due_date + ((:grace_days::int + 1) || ' days')::interval,
    updated_on = NOW(),
    updated_by = 'GRACE_DPI_E2E'
FROM mfi_accounting.loan_account la
WHERE ldd.loan_account_id = la.account_id
  AND la.account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.component_type IN ('PRIN', 'INT')
  AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0;

UPDATE mfi_accounting.dpi_accrual_details
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'GRACE_DPI_E2E'
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false;

UPDATE mfi_accounting.loan_due_details
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'GRACE_DPI_E2E'
WHERE loan_account_id = :loan_account_id::bigint
  AND component_type = 'DPI'
  AND is_deleted = false;

COMMIT;

\echo '=== grace E2E setup ==='
SELECT la.account_id, a.account_number, psfd.grace_period, la.past_due_days, psfd.dpi_applicable
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency AND psfd.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;

SELECT component_type, due_date::date, overdue_date::date,
       (due_amount - paid_amount - waived_amount) AS outstanding
FROM mfi_accounting.loan_due_details
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false
  AND component_type IN ('PRIN', 'INT')
ORDER BY due_date, component_type
LIMIT 4;

SELECT COUNT(*) AS remaining_accrual_rows
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint AND is_deleted = false;
