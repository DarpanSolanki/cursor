-- Restore past_due_days + booking soft-deletes from quarantine_dpd_portfolio.sql.
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.loan_account la
SET past_due_days = b.past_due_days,
    updated_on = NOW(),
    updated_by = 'DEMO_DPD_RESTORE'
FROM mfi_accounting._demo_dpd_quarantine_backup b
WHERE la.account_id = b.account_id;

DELETE FROM mfi_accounting._demo_dpd_quarantine_backup;

UPDATE mfi_accounting.dpi_accrual_details da
SET is_deleted = false
FROM mfi_accounting._demo_dpi_booking_quarantine_backup b
WHERE da.id = b.accrual_id
  AND da.is_deleted = true;

DELETE FROM mfi_accounting._demo_dpi_booking_quarantine_backup;

COMMIT;

\echo '=== DPD + booking quarantine restore done ==='
