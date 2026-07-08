-- Two unpaid EMIs only (for DPI billing next-EMI gate) + grace + DPI enabled.
-- Use with run_dpi_two_emi_full_chain.sh on LAN 6004041325 / 8057160.
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.product_scheme_frequency_details psfd
SET grace_period = :grace_days::int,
    dpi_applicable = 'YES'
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint
  AND psfd.product_scheme_id = la.la_product_scheme_id
  AND psfd.interest_frequency = la.repayment_frequency
  AND psfd.is_deleted = false;

UPDATE mfi_accounting.loan_account
SET loan_status = 'ACTIVE',
    is_deleted = false,
    la_closing_date = NULL,
    past_due_days = 90,
    updated_on = NOW(),
    updated_by = 'DPI_2EMI_FULL'
WHERE account_id = :loan_account_id::bigint;

UPDATE mfi_accounting.account
SET status = 'ACTIVE',
    is_deleted = false,
    updated_on = NOW(),
    updated_by = 'DPI_2EMI_FULL'
WHERE id = :loan_account_id::bigint;

-- Keep exactly two live EMIs (May-14 / Jun-14) — hide serial >= 3 so billing waits only for EMI2.
UPDATE mfi_accounting.loan_due_details ldd
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'DPI_2EMI_FULL'
FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.serial_number >= 3
  AND ldd.loan_installment_details_id = lid.id
  AND ldd.is_deleted = false;

UPDATE mfi_accounting.loan_installment_details
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'DPI_2EMI_FULL'
WHERE loan_account_id = :loan_account_id::bigint
  AND serial_number >= 3
  AND is_deleted = false;

UPDATE mfi_accounting.loan_installment_details lid
SET installment_date = CASE lid.serial_number
        WHEN 1 THEN TIMESTAMP '2026-05-14 00:00:00'
        WHEN 2 THEN TIMESTAMP '2026-06-14 00:00:00'
      END,
    overdue_date = CASE lid.serial_number
        WHEN 1 THEN TIMESTAMP '2026-05-14 00:00:00'
        WHEN 2 THEN TIMESTAMP '2026-06-14 00:00:00'
      END,
    is_settled = false,
    updated_on = NOW(),
    updated_by = 'DPI_2EMI_FULL'
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.is_deleted = false
  AND lid.serial_number IN (1, 2);

UPDATE mfi_accounting.loan_due_details ldd
SET due_date = lid.installment_date,
    overdue_date = lid.installment_date + ((:grace_days::int + 1) || ' days')::interval,
    paid_amount = 0,
    waived_amount = 0,
    updated_on = NOW(),
    updated_by = 'DPI_2EMI_FULL'
FROM mfi_accounting.loan_installment_details lid
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.component_type IN ('PRIN', 'INT')
  AND lid.id = ldd.loan_installment_details_id
  AND lid.loan_account_id = :loan_account_id::bigint
  AND lid.serial_number IN (1, 2)
  AND lid.is_deleted = false;

UPDATE mfi_accounting.dpi_accrual_details
SET is_deleted = true
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false;

UPDATE mfi_accounting.loan_due_details
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'DPI_2EMI_FULL'
WHERE loan_account_id = :loan_account_id::bigint
  AND component_type = 'DPI'
  AND is_deleted = false;

-- Only this loan in DPI batch scan.
UPDATE mfi_accounting.loan_account la
SET past_due_days = 0,
    updated_on = NOW(),
    updated_by = 'DPI_2EMI_FULL'
WHERE la.account_id <> :loan_account_id::bigint
  AND la.past_due_days > 0
  AND la.loan_status = 'ACTIVE';

COMMIT;

\echo '=== two-EMI full-chain fixture ==='
SELECT lid.serial_number, lid.installment_date::date, lid.is_deleted,
       ldd.component_type, (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) AS outstanding
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_due_details ldd
  ON ldd.loan_installment_details_id = lid.id AND ldd.is_deleted = false
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.serial_number <= 2
  AND ldd.component_type IN ('PRIN', 'INT')
ORDER BY lid.serial_number, ldd.component_type;
