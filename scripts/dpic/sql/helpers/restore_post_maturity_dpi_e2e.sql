-- Undo setup_post_maturity_dpi_e2e.sql (fixture loan only).
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.loan_installment_details lid
SET is_deleted = false,
    updated_on = NOW(),
    updated_by = 'POST_MATURITY_E2E_RESTORE'
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.updated_by = 'POST_MATURITY_E2E'
  AND lid.is_deleted = true;

UPDATE mfi_accounting.loan_account la
SET maturity_date = :maturity_date_orig::timestamp,
    updated_on = NOW(),
    updated_by = 'POST_MATURITY_E2E_RESTORE'
WHERE la.account_id = :loan_account_id::bigint;

COMMIT;
