-- Align dpi_accrual_details txn ref columns with transaction_master.reference_number (varchar 64).
-- Root cause: postTransaction returns 37-char refs; accrual_transaction_ref_number was varchar(32).
\set ON_ERROR_STOP on

ALTER TABLE mfi_accounting.dpi_accrual_details
  ALTER COLUMN accrual_transaction_ref_number TYPE character varying(64),
  ALTER COLUMN billing_transaction_ref_number TYPE character varying(64);

\echo 'dpi_accrual_details txn ref columns widened to varchar(64)'
