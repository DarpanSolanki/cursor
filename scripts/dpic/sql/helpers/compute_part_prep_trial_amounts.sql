-- Overdue totals for loanAccountPartPrepayment TRIAL payload (fixture loan).
-- psql vars: loan_account_id (bigint)
\set ON_ERROR_STOP on

SELECT COALESCE(SUM(
         GREATEST(ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount, 0), 0)
       ), 0)::text AS overdue_amount,
       COALESCE(SUM(
         CASE WHEN ldd.component_type = 'DPI' THEN
           GREATEST(ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount, 0), 0)
         ELSE 0 END
       ), 0)::text AS dpi_overdue_open
FROM mfi_accounting.loan_due_details ldd
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.overdue_date IS NOT NULL
  AND ldd.overdue_date <= CURRENT_TIMESTAMP;
