-- Local: soft-delete unposted accruals left after dpiAccrualCalculation perf runs (scheme 48 pool).
\set ON_ERROR_STOP on
BEGIN;
UPDATE mfi_accounting.dpi_accrual_details dad
SET is_deleted = true
WHERE dad.is_deleted = false
  AND dad.accrual_posting_date IS NULL
  AND dad.loan_account_id IN (
    SELECT la.account_id FROM mfi_accounting.loan_account la
    WHERE la.la_product_scheme_id = :product_scheme_id::bigint
      AND la.account_id <> COALESCE(NULLIF(:'preserve_loan_account_id', '')::bigint, -1)
  );
COMMIT;
SELECT COUNT(*) AS unposted_remaining
FROM mfi_accounting.dpi_accrual_details
WHERE is_deleted = false AND accrual_posting_date IS NULL;
