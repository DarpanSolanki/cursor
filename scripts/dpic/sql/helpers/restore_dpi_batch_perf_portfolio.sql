-- Restore local state after seed_dpi_batch_perf_portfolio.sql.
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.product_scheme_frequency_details psfd
SET dpi_applicable = b.dpi_applicable
FROM mfi_accounting._dpi_perf_psfd_backup b
WHERE psfd.id = b.psfd_id;

UPDATE mfi_accounting.loan_account la
SET past_due_days = b.past_due_days,
    updated_on = NOW(),
    updated_by = 'DPI_PERF_RESTORE'
FROM mfi_accounting._dpi_perf_loan_dpd_backup b
WHERE la.account_id = b.account_id;

DELETE FROM mfi_accounting._dpi_perf_psfd_backup;
DELETE FROM mfi_accounting._dpi_perf_loan_dpd_backup;

COMMIT;

\echo '=== DPI perf portfolio restored ==='
SELECT COUNT(*) AS batch_eligible_loans
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency
 AND psfd.is_deleted = false
WHERE la.loan_status = 'ACTIVE'
  AND la.past_due_days > 0
  AND psfd.dpi_applicable = 'YES';
