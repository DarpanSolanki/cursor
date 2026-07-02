-- Wipe all DPI accrual rows, DPI dues, DPI GL txns, and batch failure audit (local dev only).
\set ON_ERROR_STOP on

BEGIN;

-- Restore portfolio / fixture state before dropping backup tables (when present).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'mfi_accounting' AND tablename = '_demo_dpd_quarantine_backup') THEN
    UPDATE mfi_accounting.loan_account la
    SET past_due_days = b.past_due_days,
        updated_on = NOW(),
        updated_by = 'LOCAL_DPI_PURGE_RESTORE'
    FROM mfi_accounting._demo_dpd_quarantine_backup b
    WHERE la.account_id = b.account_id;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'mfi_accounting' AND tablename = '_grace_e2e_psfd_backup') THEN
    UPDATE mfi_accounting.product_scheme_frequency_details psfd
    SET grace_period = b.grace_period,
        updated_on = NOW(),
        updated_by = 'LOCAL_DPI_PURGE_RESTORE'
    FROM mfi_accounting._grace_e2e_psfd_backup b
    WHERE psfd.id = b.psfd_id;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'mfi_accounting' AND tablename = '_dpi_emi_first_backup') THEN
    UPDATE mfi_accounting.loan_installment_details lid
    SET installment_date = b.installment_date,
        overdue_date = b.overdue_date,
        updated_on = NOW(),
        updated_by = 'LOCAL_DPI_PURGE_RESTORE'
    FROM mfi_accounting._dpi_emi_first_backup b
    WHERE b.entity_kind = 'installment'
      AND b.entity_id = lid.id;

    UPDATE mfi_accounting.loan_due_details ldd
    SET due_date = b.due_date,
        updated_on = NOW(),
        updated_by = 'LOCAL_DPI_PURGE_RESTORE'
    FROM mfi_accounting._dpi_emi_first_backup b
    WHERE b.entity_kind = 'due'
      AND b.entity_id = ldd.id;
  END IF;
END $$;

-- Collect DPI txn ids before wiping accrual refs.
CREATE TEMP TABLE _dpi_txn_purge_ids ON COMMIT DROP AS
SELECT DISTINCT tm.id
FROM mfi_accounting.transaction_master tm
WHERE tm.client_reference_number LIKE '%\_DPI\_%' ESCAPE '\'
   OR tm.client_reference_number LIKE '%DPI\_ACCRUAL%' ESCAPE '\'
   OR tm.client_reference_number LIKE '%DPI\_BILL%' ESCAPE '\'
   OR tm.reference_number IN (
     SELECT accrual_transaction_ref_number
     FROM mfi_accounting.dpi_accrual_details
     WHERE accrual_transaction_ref_number IS NOT NULL
   )
   OR tm.reference_number IN (
     SELECT billing_transaction_ref_number
     FROM mfi_accounting.dpi_accrual_details
     WHERE billing_transaction_ref_number IS NOT NULL
   )
   OR tm.reference_number IN (
     SELECT transaction_reference_number
     FROM mfi_accounting.loan_due_details
     WHERE component_type = 'DPI'
       AND transaction_reference_number IS NOT NULL
   );

DELETE FROM mfi_accounting.loan_due_details__loan_account_payments_details lapd
WHERE lapd.due_details_id IN (
  SELECT id FROM mfi_accounting.loan_due_details WHERE component_type = 'DPI'
);

DELETE FROM mfi_accounting.loan_due_details WHERE component_type = 'DPI';

DELETE FROM mfi_accounting.transaction_partition_details
WHERE transaction_id IN (SELECT id FROM _dpi_txn_purge_ids);

DELETE FROM mfi_accounting.transaction_metadata
WHERE transaction_id IN (SELECT id FROM _dpi_txn_purge_ids);

DELETE FROM mfi_accounting.transaction_details
WHERE transaction_id IN (SELECT id FROM _dpi_txn_purge_ids);

DELETE FROM mfi_accounting.transaction_master
WHERE id IN (SELECT id FROM _dpi_txn_purge_ids);

TRUNCATE mfi_accounting.dpi_accrual_details;

DELETE FROM mfi_accounting.batch_failure_audit
WHERE context_key IN ('loan_account_id', 'account_id')
  AND context_value ~ '^[0-9]+$';

COMMIT;

\echo '=== purge_local_dpi_all done ==='
SELECT COUNT(*) AS dpi_accrual_rows FROM mfi_accounting.dpi_accrual_details;
SELECT COUNT(*) AS dpi_due_rows
FROM mfi_accounting.loan_due_details
WHERE component_type = 'DPI' AND is_deleted = false;
