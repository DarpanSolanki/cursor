-- Safe loanRepayment amount for DPI harness (avoids ValidateLoanRepaymentData 134243 advance-EMI guard).
-- Vars: :loan_account_id, :anchor_date (YYYY-MM-DD), :repay_cap (numeric, default 2000 in caller)
\set ON_ERROR_STOP on
WITH open_dues AS (
  SELECT component_type,
         (due_amount - paid_amount - COALESCE(waived_amount, 0)) AS open_amt
  FROM mfi_accounting.loan_due_details
  WHERE loan_account_id = :loan_account_id::bigint
    AND COALESCE(is_deleted, false) = false
    AND due_date::date <= :'anchor_date'::date
    AND (due_amount - paid_amount - COALESCE(waived_amount, 0)) > 0
),
totals AS (
  SELECT COALESCE(SUM(open_amt), 0) AS total_open,
         COALESCE(SUM(open_amt) FILTER (WHERE component_type = 'DPI'), 0) AS dpi_open
  FROM open_dues
)
SELECT GREATEST(
         LEAST(total_open, :'repay_cap'::numeric),
         LEAST(total_open, GREATEST(dpi_open, 1))
       )::numeric(20, 0)::text
FROM totals;
