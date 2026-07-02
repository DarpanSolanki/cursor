-- Restore past_due_days zeroed by quarantine_dpd_portfolio.sql (optional after demo).
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.loan_account la
SET past_due_days = b.past_due_days,
    updated_on = NOW(),
    updated_by = 'DEMO_DPD_RESTORE'
FROM mfi_accounting._demo_dpd_quarantine_backup b
WHERE la.account_id = b.account_id;

DELETE FROM mfi_accounting._demo_dpd_quarantine_backup;

COMMIT;

\echo '=== DPD restore done ==='
