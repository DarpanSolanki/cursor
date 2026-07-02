-- Hard-delete all DPI accrual rows for a loan (local replay — avoids duplicate-looking soft-deleted history).
\set ON_ERROR_STOP on
DELETE FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint;

SELECT COUNT(*) AS remaining FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint;
