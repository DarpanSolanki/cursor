\set ON_ERROR_STOP on
-- Month-end slice ending 2026-06-30 must accrue > 0 when prior EMI is 1st-of-month (a8f822cf0 anchor fix).
SELECT COUNT(*) AS month_end_slices,
       COALESCE(SUM(total_accrued_amount), 0) AS month_end_accrued
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false
  AND total_accrued_amount > 0
  AND end_date::date = DATE '2026-06-30';
