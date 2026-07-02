-- Local replay: clear DPI accrual/billing txn refs for re-running EOD chain (avoids 134497).
--
-- Usage: psql ... -v loan_account_id=8057160 -f reset_dpi_booking_replay.sql

\set ON_ERROR_STOP on

BEGIN;

WITH dpi_txns AS (
  SELECT id FROM mfi_accounting.transaction_master
  WHERE client_reference_number LIKE :'loan_account_id' || '_DPI_ACCRUAL_%'
     OR client_reference_number LIKE :'loan_account_id' || '_DPI_BILL_%'
)
DELETE FROM mfi_accounting.transaction_partition_details
WHERE transaction_id IN (SELECT id FROM dpi_txns);

WITH dpi_txns AS (
  SELECT id FROM mfi_accounting.transaction_master
  WHERE client_reference_number LIKE :'loan_account_id' || '_DPI_ACCRUAL_%'
     OR client_reference_number LIKE :'loan_account_id' || '_DPI_BILL_%'
)
DELETE FROM mfi_accounting.transaction_metadata
WHERE transaction_id IN (SELECT id FROM dpi_txns);

WITH dpi_txns AS (
  SELECT id FROM mfi_accounting.transaction_master
  WHERE client_reference_number LIKE :'loan_account_id' || '_DPI_ACCRUAL_%'
     OR client_reference_number LIKE :'loan_account_id' || '_DPI_BILL_%'
)
DELETE FROM mfi_accounting.transaction_details
WHERE transaction_id IN (SELECT id FROM dpi_txns);

DELETE FROM mfi_accounting.transaction_master
WHERE client_reference_number LIKE :'loan_account_id' || '_DPI_ACCRUAL_%'
   OR client_reference_number LIKE :'loan_account_id' || '_DPI_BILL_%';

UPDATE mfi_accounting.dpi_accrual_details
SET accrual_posting_date = NULL,
    accrual_transaction_ref_number = NULL,
    billing_posting_date = NULL,
    billing_transaction_ref_number = NULL
WHERE loan_account_id = :'loan_account_id'
  AND is_deleted = false;

DELETE FROM mfi_accounting.batch_failure_audit
WHERE context_value = :'loan_account_id'::text;

COMMIT;

\echo '=== DPI EOD replay reset for loan' :loan_account_id '==='
