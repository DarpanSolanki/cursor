-- One LAN, two unpaid EMIs (2nd of month), all other installments settled — easy DPI verify.
-- LAN 6004044425 / loan_account_id 8060160. No backup tables created.
--
-- Usage: psql ... -v loan_account_id=8060160 -v grace_days=3 -f setup_simple_two_month_overdue.sql

\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.product_scheme_frequency_details psfd
SET grace_period = :grace_days::int,
    dpi_applicable = 'YES',
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint
  AND psfd.product_scheme_id = la.la_product_scheme_id
  AND psfd.interest_frequency = la.repayment_frequency
  AND psfd.is_deleted = false;

-- Remove duplicate / fixture installments that confuse the schedule.
UPDATE mfi_accounting.loan_due_details ldd
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.serial_number IN (6, 7, 8)
  AND ldd.loan_installment_details_id = lid.id
  AND ldd.is_deleted = false;

UPDATE mfi_accounting.loan_installment_details
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
WHERE loan_account_id = :loan_account_id::bigint
  AND serial_number IN (6, 7, 8)
  AND is_deleted = false;

-- Two overdue EMIs: Apr-2 and May-2 (calendar-simple).
UPDATE mfi_accounting.loan_installment_details lid
SET installment_date = CASE lid.serial_number
        WHEN 1 THEN TIMESTAMP '2026-04-02 00:00:00'
        WHEN 2 THEN TIMESTAMP '2026-05-02 00:00:00'
      END,
    overdue_date = CASE lid.serial_number
        WHEN 1 THEN TIMESTAMP '2026-04-02 00:00:00'
        WHEN 2 THEN TIMESTAMP '2026-05-02 00:00:00'
      END,
    is_settled = false,
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.is_deleted = false
  AND lid.serial_number IN (1, 2);

UPDATE mfi_accounting.loan_installment_details lid
SET is_settled = true,
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.is_deleted = false
  AND lid.serial_number >= 3;

UPDATE mfi_accounting.loan_due_details ldd
SET due_date = lid.installment_date,
    overdue_date = lid.installment_date + ((:grace_days::int + 1) || ' days')::interval,
    paid_amount = 0,
    waived_amount = 0,
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
FROM mfi_accounting.loan_installment_details lid
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.component_type IN ('PRIN', 'INT')
  AND lid.id = ldd.loan_installment_details_id
  AND lid.loan_account_id = :loan_account_id::bigint
  AND lid.serial_number IN (1, 2)
  AND lid.is_deleted = false;

UPDATE mfi_accounting.loan_due_details ldd
SET paid_amount = ldd.due_amount,
    waived_amount = 0,
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
FROM mfi_accounting.loan_installment_details lid
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.component_type IN ('PRIN', 'INT')
  AND lid.id = ldd.loan_installment_details_id
  AND lid.loan_account_id = :loan_account_id::bigint
  AND lid.serial_number >= 3
  AND lid.is_deleted = false;

UPDATE mfi_accounting.loan_account la
SET loan_status = 'ACTIVE',
    past_due_days = 61,
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
WHERE la.account_id = :loan_account_id::bigint;

UPDATE mfi_accounting.account a
SET status = 'ACTIVE',
    closing_date = NULL,
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint
  AND a.id = la.account_id;

-- Only this loan is DPI-eligible in batch scan.
UPDATE mfi_accounting.loan_account la
SET past_due_days = 0,
    updated_on = NOW(),
    updated_by = 'DPI_SIMPLE_2MO'
WHERE la.account_id <> :loan_account_id::bigint
  AND la.past_due_days > 0
  AND la.loan_status = 'ACTIVE';

COMMIT;

\echo '=== simple 2-month overdue fixture ==='
SELECT a.account_number AS lan, la.account_id, la.past_due_days, psfd.grace_period, psfd.dpi_applicable
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency AND psfd.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;

SELECT lid.serial_number, lid.installment_date::date, lid.is_settled,
       ldd.component_type, (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) AS outstanding
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_due_details ldd
  ON ldd.loan_installment_details_id = lid.id AND ldd.is_deleted = false
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.is_deleted = false
  AND lid.serial_number <= 3
  AND ldd.component_type IN ('PRIN', 'INT')
ORDER BY lid.serial_number, ldd.component_type;

SELECT COUNT(*) AS eligible_dpi_loans
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency AND psfd.is_deleted = false
WHERE la.loan_status = 'ACTIVE'
  AND la.past_due_days > 0
  AND la.repayment_frequency = 'MONTHLY'
  AND psfd.dpi_applicable = 'YES';
