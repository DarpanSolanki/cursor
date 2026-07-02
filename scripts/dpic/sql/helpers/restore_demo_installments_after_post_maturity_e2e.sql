-- Restore installments soft-deleted by setup_post_maturity_dpi_e2e.sql (shared demo loan hygiene).
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.loan_installment_details lid
SET is_deleted = false,
    updated_on = NOW(),
    updated_by = 'POST_MATURITY_E2E_RESTORE'
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.is_deleted = true
  AND lid.updated_by = 'POST_MATURITY_E2E';

COMMIT;
