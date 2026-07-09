-- SDCP-11012 local: prepare SHG parent + children for dpiAccrualCalculation parity verify.
-- Clears DPI accrual/LDD rows for the family; leaves PRIN/INT schedule intact.
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.product_scheme_frequency_details psfd
SET dpi_applicable = 'YES'
FROM mfi_accounting.loan_account la
WHERE la.account_id = :parent_loan_account_id::bigint
  AND psfd.product_scheme_id = la.la_product_scheme_id
  AND psfd.interest_frequency = la.repayment_frequency
  AND psfd.is_deleted = false
  AND psfd.dpi_applicable <> 'YES';

UPDATE mfi_accounting.loan_account
SET loan_status = 'ACTIVE',
    is_deleted = false,
    la_closing_date = NULL,
    updated_on = NOW(),
    updated_by = 'SHG_DPI_PARITY_E2E'
WHERE account_id = :parent_loan_account_id::bigint
   OR parent_loan_account_id = :parent_loan_account_id::bigint;

UPDATE mfi_accounting.account a
SET status = 'ACTIVE',
    is_deleted = false,
    updated_on = NOW(),
    updated_by = 'SHG_DPI_PARITY_E2E'
FROM mfi_accounting.loan_account la
WHERE a.id = la.account_id
  AND (la.account_id = :parent_loan_account_id::bigint
       OR la.parent_loan_account_id = :parent_loan_account_id::bigint);

UPDATE mfi_accounting.dpi_accrual_details d
SET is_deleted = true
FROM mfi_accounting.loan_account la
WHERE d.loan_account_id = la.account_id
  AND d.is_deleted = false
  AND (la.account_id = :parent_loan_account_id::bigint
       OR la.parent_loan_account_id = :parent_loan_account_id::bigint);

UPDATE mfi_accounting.loan_due_details ldd
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'SHG_DPI_PARITY_E2E'
FROM mfi_accounting.loan_account la
WHERE ldd.loan_account_id = la.account_id
  AND ldd.component_type = 'DPI'
  AND ldd.is_deleted = false
  AND (la.account_id = :parent_loan_account_id::bigint
       OR la.parent_loan_account_id = :parent_loan_account_id::bigint);

COMMIT;

\echo '=== SHG DPI parity family ==='
SELECT la.account_id, a.account_number, la.parent_loan_account_id, la.past_due_days, psfd.dpi_applicable
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency
 AND psfd.is_deleted = false
WHERE la.account_id = :parent_loan_account_id::bigint
   OR la.parent_loan_account_id = :parent_loan_account_id::bigint
ORDER BY la.account_id;
