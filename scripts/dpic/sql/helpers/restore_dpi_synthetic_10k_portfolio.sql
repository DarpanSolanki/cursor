-- Remove synthetic loans created by seed_dpi_synthetic_10k_portfolio.sql
\set ON_ERROR_STOP on

BEGIN;

DELETE FROM mfi_accounting.dpi_accrual_details dad
WHERE dad.loan_account_id IN (SELECT new_account_id FROM mfi_accounting._dpi_synthetic_loan_map);

DELETE FROM mfi_accounting.loan_due_details
WHERE loan_account_id IN (SELECT new_account_id FROM mfi_accounting._dpi_synthetic_loan_map);

DELETE FROM mfi_accounting.loan_installment_details
WHERE loan_account_id IN (SELECT new_account_id FROM mfi_accounting._dpi_synthetic_loan_map);

DELETE FROM mfi_accounting.account_interest_details
WHERE account_id IN (SELECT new_account_id FROM mfi_accounting._dpi_synthetic_loan_map);

DELETE FROM mfi_accounting.loan_account
WHERE account_id IN (SELECT new_account_id FROM mfi_accounting._dpi_synthetic_loan_map);

DELETE FROM mfi_accounting.account
WHERE id IN (SELECT new_account_id FROM mfi_accounting._dpi_synthetic_loan_map);

DELETE FROM mfi_accounting._dpi_synthetic_loan_map;

COMMIT;

\echo '=== synthetic loans removed ==='
