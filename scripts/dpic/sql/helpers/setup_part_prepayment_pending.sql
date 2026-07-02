-- Seed one PENDING part-prepayment row for local DPI read API tests.
\set ON_ERROR_STOP on

BEGIN;

DELETE FROM mfi_accounting.loan_account_part_prepayment_details
WHERE loan_account_id = :loan_account_id::bigint
  AND status = 'PENDING';

INSERT INTO mfi_accounting.loan_account_part_prepayment_details (
  loan_account_id,
  rescheduling_effective_date,
  part_prepayment_impact,
  broken_period_interest_handling,
  bpi_amount,
  due_amount,
  overdue_amount,
  overdue_fee_charges,
  charges,
  net_amount,
  gross_amount,
  status,
  instrument_type,
  created_on,
  created_by,
  updated_on,
  updated_by
) VALUES (
  :loan_account_id::bigint,
  DATE_TRUNC('day', TO_TIMESTAMP(:rescheduling_effective_ms::bigint / 1000.0)),
  'REDUCE_TENOR',
  'NO',
  0,
  0,
  0,
  0,
  0,
  10000,
  10000,
  'PENDING',
  'CASH',
  NOW(),
  'LOCAL_DPI_TEST',
  NOW(),
  'LOCAL_DPI_TEST'
);

COMMIT;

\echo '=== part prepayment PENDING row ==='
SELECT id, loan_account_id, status, rescheduling_effective_date
FROM mfi_accounting.loan_account_part_prepayment_details
WHERE loan_account_id = :loan_account_id::bigint AND status = 'PENDING'
ORDER BY id DESC LIMIT 1;
