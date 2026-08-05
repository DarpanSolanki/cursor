-- Clear batch_failure_audit for a loan account before retrying dpiAccrualBooking.
-- Usage: psql ... -v loan_account_id=8055060 -f clear_batch_failure_audit.sql

\set ON_ERROR_STOP on

DELETE FROM mfi_accounting.batch_failure_audit
WHERE context_value = :'loan_account_id'::text;

\echo 'Deleted batch_failure_audit rows for context_value=' :loan_account_id
