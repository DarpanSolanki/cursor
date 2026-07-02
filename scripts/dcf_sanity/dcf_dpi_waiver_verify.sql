-- DPI waiver legs — death foreclosure + foreclosure simulation fixture checks.
-- Usage:
--   psql ... -v lan='6004044425' -v loan_account_id='8060160' \
--     -f scripts/dcf_sanity/dcf_dpi_waiver_verify.sql

\set ON_ERROR_STOP on
\set schema 'mfi_accounting'

\echo '=== DPI accrual on fixture loan (death FC writer inputs) ==='
SELECT COUNT(*) AS dpi_accrual_rows,
       COALESCE(SUM(dpi_amount), 0) AS total_dpi_accrued
FROM :schema.dpi_accrual_details dad
WHERE dad.loan_account_id = :'loan_account_id'::bigint
  AND dad.is_deleted = false
  AND dad.dpi_amount > 0;

\echo '=== DPI due row (billing path) ==='
SELECT ldd.component_type,
       ldd.due_amount,
       ldd.paid_amount,
       ldd.waived_amount
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.id = ldd.loan_account_id
WHERE la.account_number = :'lan'
  AND ldd.component_type = 'DPI'
  AND ldd.is_deleted = false
ORDER BY ldd.due_date DESC
LIMIT 3;

\echo '=== Death FC closure — DPI waiver GL legs (if DFC completed) ==='
SELECT tpd.reference_code,
       tpd.debit_placeholder,
       tpd.credit_placeholder,
       tpd.debit_amount,
       tpd.credit_amount
FROM :schema.transaction_partition_details tpd
JOIN :schema.transaction_details td ON td.id = tpd.transaction_id
JOIN :schema.loan_account_closure_details lacd
  ON lacd.transaction_reference_number = td.reference_number
JOIN :schema.loan_account la ON la.id = lacd.loan_account_id
WHERE la.account_number = :'lan'
  AND lacd.identifier_type = 'DEATH_FORECLOSURE'
  AND td.transaction_type = 'DEATH_FORECLOSURE'
  AND (
    tpd.debit_placeholder ILIKE '%DPI%'
    OR tpd.credit_placeholder ILIKE '%DPI%'
    OR tpd.reference_code ILIKE '%DPI%'
  )
ORDER BY tpd.reference_code;

\echo '=== Assertions (raise if DPI fixture missing) ==='
DO $$
DECLARE
  n_accrual bigint;
  n_dpi_due bigint;
BEGIN
  SELECT COUNT(*) INTO n_accrual
  FROM mfi_accounting.dpi_accrual_details
  WHERE loan_account_id = :'loan_account_id'::bigint
    AND is_deleted = false AND dpi_amount > 0;
  IF n_accrual < 1 THEN
    RAISE EXCEPTION 'DPI accrual missing for loan_account_id=% — run dpic.eod_dpi first', :'loan_account_id';
  END IF;

  SELECT COUNT(*) INTO n_dpi_due
  FROM mfi_accounting.loan_due_details ldd
  JOIN mfi_accounting.loan_account la ON la.id = ldd.loan_account_id
  WHERE la.account_number = :'lan'
    AND ldd.component_type = 'DPI'
    AND ldd.is_deleted = false;
  IF n_dpi_due < 1 THEN
    RAISE EXCEPTION 'DPI loan_due_details missing for lan=% — billing not run', :'lan';
  END IF;
END $$;

\echo 'PASS: DPI waiver fixture prerequisites OK'
