-- Restore installments / PRIN+INT dues soft-deleted by two_emi / post-maturity / local DPI suites.
-- Local harness only — shared grace-chain LAN must start each case with a full schedule.
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.loan_installment_details
SET is_deleted = false,
    updated_on = NOW(),
    updated_by = 'DPI_CASE_ISOLATE'
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = true;

UPDATE mfi_accounting.loan_due_details
SET is_deleted = false,
    updated_on = NOW(),
    updated_by = 'DPI_CASE_ISOLATE'
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = true
  AND component_type IN ('PRIN', 'INT');

COMMIT;

SELECT COUNT(*) FILTER (WHERE is_deleted = false) AS live_installments,
       COUNT(*) FILTER (WHERE is_deleted = true) AS hidden_installments
FROM mfi_accounting.loan_installment_details
WHERE loan_account_id = :loan_account_id::bigint;
