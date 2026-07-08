-- Local: grace_period on scheme frequency + align PRIN/INT overdue_date to due+grace+1 (LPP).
-- Note: product_scheme_frequency_details has no updated_on/updated_by columns on some envs.
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mfi_accounting._grace_e2e_psfd_backup (
  psfd_id       BIGINT PRIMARY KEY,
  grace_period  INT NOT NULL,
  backed_up_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO mfi_accounting._grace_e2e_psfd_backup (psfd_id, grace_period)
SELECT psfd.id, COALESCE(psfd.grace_period, 0)
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
    dpi_applicable = 'YES'
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint
  AND psfd.product_scheme_id = la.la_product_scheme_id
  AND psfd.interest_frequency = la.repayment_frequency
  AND psfd.is_deleted = false;

-- Calc reader requires ACTIVE + not soft-deleted (other suites may park demo LANs).
UPDATE mfi_accounting.loan_account
SET loan_status = 'ACTIVE',
    is_deleted = false,
    la_closing_date = NULL,
    updated_on = NOW(),
    updated_by = 'GRACE_DPI_E2E'
WHERE account_id = :loan_account_id::bigint;

UPDATE mfi_accounting.account
SET status = 'ACTIVE',
    is_deleted = false,
    updated_on = NOW(),
    updated_by = 'GRACE_DPI_E2E'
WHERE id = :loan_account_id::bigint;

UPDATE mfi_accounting.loan_due_details ldd
SET overdue_date = ldd.due_date + ((:grace_days::int + 1) || ' days')::interval,
    updated_on = NOW(),
    updated_by = 'GRACE_DPI_E2E'
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.component_type IN ('PRIN', 'INT')
  AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0;

UPDATE mfi_accounting.dpi_accrual_details
SET is_deleted = true
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
SELECT la.account_id, a.account_number, la.loan_status, psfd.grace_period, la.past_due_days, psfd.dpi_applicable
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
LIMIT 6;

SELECT COUNT(*) AS remaining_accrual_rows
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint AND is_deleted = false;
