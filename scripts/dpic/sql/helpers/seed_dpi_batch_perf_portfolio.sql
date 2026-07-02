-- Local-only: seed N DPI-eligible loans for dpiAccrualCalculation perf / multi-chunk testing.
-- Uses SHGDL scheme 48 pool (1538+ ACTIVE loans with overdue INT locally). Enables dpi_applicable,
-- sets past_due_days on selected loans, zeros others so batch scans exactly target_count accounts.
--
-- Usage:
--   psql ... -v ON_ERROR_STOP=1 \
--     -v product_scheme_id=48 \
--     -v target_count=100 \
--     -v past_due_days=45 \
--     -v clear_accruals=1 \
--     -f scripts/dpic/sql/helpers/seed_dpi_batch_perf_portfolio.sql
--
-- Restore: scripts/dpic/sql/helpers/restore_dpi_batch_perf_portfolio.sql

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mfi_accounting._dpi_perf_psfd_backup (
  psfd_id        BIGINT PRIMARY KEY,
  dpi_applicable VARCHAR(8) NOT NULL,
  backed_up_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mfi_accounting._dpi_perf_loan_dpd_backup (
  account_id     BIGINT PRIMARY KEY,
  past_due_days  INT NOT NULL,
  backed_up_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TEMP TABLE _dpi_perf_selected ON COMMIT DROP AS
SELECT la.account_id
FROM mfi_accounting.loan_account la
WHERE la.la_product_scheme_id = :product_scheme_id::bigint
  AND la.loan_status = 'ACTIVE'
  AND la.is_deleted = false
  AND EXISTS (
    SELECT 1
    FROM mfi_accounting.loan_due_details ldd
    WHERE ldd.loan_account_id = la.account_id
      AND ldd.is_deleted = false
      AND ldd.component_type IN ('PRIN', 'INT')
      AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
  )
ORDER BY la.account_id
LIMIT :target_count::int;

INSERT INTO mfi_accounting._dpi_perf_psfd_backup (psfd_id, dpi_applicable)
SELECT psfd.id, psfd.dpi_applicable
FROM mfi_accounting.product_scheme_frequency_details psfd
WHERE psfd.product_scheme_id = :product_scheme_id::bigint
  AND psfd.interest_frequency = 'MONTHLY'
  AND psfd.is_deleted = false
ON CONFLICT (psfd_id) DO NOTHING;

UPDATE mfi_accounting.product_scheme_frequency_details psfd
SET dpi_applicable = 'YES'
WHERE psfd.product_scheme_id = :product_scheme_id::bigint
  AND psfd.interest_frequency = 'MONTHLY'
  AND psfd.is_deleted = false
  AND psfd.dpi_applicable <> 'YES';

INSERT INTO mfi_accounting._dpi_perf_loan_dpd_backup (account_id, past_due_days)
SELECT la.account_id, la.past_due_days
FROM mfi_accounting.loan_account la
WHERE la.loan_status = 'ACTIVE'
  AND la.is_deleted = false
  AND (
    la.account_id IN (SELECT account_id FROM _dpi_perf_selected)
    OR (
      la.la_product_scheme_id = :product_scheme_id::bigint
      AND la.past_due_days > 0
    )
    OR (
      la.past_due_days > 0
      AND EXISTS (
        SELECT 1
        FROM mfi_accounting.product_scheme_frequency_details psfd
        WHERE psfd.product_scheme_id = la.la_product_scheme_id
          AND psfd.interest_frequency = la.repayment_frequency
          AND psfd.is_deleted = false
          AND psfd.dpi_applicable = 'YES'
      )
    )
  )
ON CONFLICT (account_id) DO NOTHING;

UPDATE mfi_accounting.loan_account la
SET past_due_days = 0,
    updated_on = NOW(),
    updated_by = 'DPI_PERF_SEED'
WHERE la.loan_status = 'ACTIVE'
  AND la.is_deleted = false
  AND la.account_id NOT IN (SELECT account_id FROM _dpi_perf_selected)
  AND la.past_due_days > 0;

UPDATE mfi_accounting.loan_account la
SET past_due_days = :past_due_days::int,
    updated_on = NOW(),
    updated_by = 'DPI_PERF_SEED'
WHERE la.account_id IN (SELECT account_id FROM _dpi_perf_selected);

DO $$
BEGIN
  IF :'clear_accruals'::int = 1 THEN
    UPDATE mfi_accounting.dpi_accrual_details dad
    SET is_deleted = true
    WHERE dad.is_deleted = false
      AND dad.loan_account_id IN (SELECT account_id FROM _dpi_perf_selected);
  END IF;
END $$;

COMMIT;

\echo '=== DPI perf portfolio seeded ==='
SELECT COUNT(*) AS selected_loans FROM (
  SELECT account_id FROM mfi_accounting.loan_account la
  WHERE la.past_due_days = :past_due_days::int
    AND la.loan_status = 'ACTIVE'
    AND la.la_product_scheme_id = :product_scheme_id::bigint
) s;

SELECT COUNT(*) AS batch_eligible_loans
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency
 AND psfd.is_deleted = false
WHERE la.loan_status = 'ACTIVE'
  AND la.past_due_days > 0
  AND psfd.dpi_applicable = 'YES';

SELECT MIN(la.account_id) AS min_id, MAX(la.account_id) AS max_id, COUNT(*) AS cnt
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency
 AND psfd.is_deleted = false
WHERE la.loan_status = 'ACTIVE'
  AND la.past_due_days > 0
  AND psfd.dpi_applicable = 'YES';
