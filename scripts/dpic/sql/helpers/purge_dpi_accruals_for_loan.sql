-- Soft-delete all DPI accrual rows for a loan (test reset).
\set ON_ERROR_STOP on
UPDATE mfi_accounting.dpi_accrual_details
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'DPI_TEST_PURGE'
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false;

SELECT COUNT(*) AS remaining_active
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false;
