-- Post-maturity catch-up: late billing run bills passed anchors, not future period.
\set ON_ERROR_STOP on

WITH la AS (
  SELECT account_id, maturity_date::date AS maturity_day
  FROM mfi_accounting.loan_account
  WHERE account_id = :loan_account_id::bigint
),
next_emi AS (
  SELECT COUNT(*) AS cnt
  FROM mfi_accounting.loan_installment_details n
  JOIN la ON la.account_id = n.loan_account_id
  WHERE n.is_deleted = false
    AND n.is_part_prepayment_entry = false
    AND n.installment_date::date > la.maturity_day
),
accrual AS (
  SELECT COUNT(*) FILTER (WHERE accrual_posting_date IS NOT NULL AND total_accrued_amount > 0) AS posted_rows,
         COUNT(*) FILTER (WHERE billing_posting_date IS NOT NULL AND total_accrued_amount > 0) AS billed_rows,
         COUNT(*) FILTER (
           WHERE accrual_posting_date IS NOT NULL
             AND billing_posting_date IS NULL
             AND total_accrued_amount > 0
         ) AS unbilled_posted_rows,
         COALESCE(SUM(total_accrued_amount) FILTER (WHERE billing_posting_date IS NOT NULL), 0) AS billed_amount,
         COALESCE(SUM(total_accrued_amount) FILTER (
           WHERE accrual_posting_date IS NOT NULL
             AND billing_posting_date IS NULL
             AND total_accrued_amount > 0
         ), 0) AS unbilled_amount
  FROM mfi_accounting.dpi_accrual_details
  WHERE loan_account_id = :loan_account_id::bigint
    AND is_deleted = false
),
dpi_due AS (
  SELECT COUNT(*) AS due_rows,
         MAX(due_date::date) AS due_day,
         COALESCE(SUM(due_amount), 0) AS due_amount
  FROM mfi_accounting.loan_due_details
  WHERE loan_account_id = :loan_account_id::bigint
    AND component_type = 'DPI'
    AND is_deleted = false
)
SELECT next_emi.cnt AS next_emi_count,
       accrual.posted_rows,
       accrual.billed_rows,
       accrual.unbilled_posted_rows,
       accrual.billed_amount,
       accrual.unbilled_amount,
       dpi_due.due_rows,
       dpi_due.due_day,
       dpi_due.due_amount,
       (next_emi.cnt = 0) AS no_next_emi,
       (dpi_due.due_rows > 0) AS has_dpi_due,
       (dpi_due.due_day = :'expected_due_anchor_date'::date) AS due_on_passed_anchor,
       (accrual.billed_rows > 0 AND accrual.unbilled_posted_rows > 0) AS partial_catchup,
       (accrual.billed_amount > 0 AND dpi_due.due_amount > 0) AS amounts_positive
FROM next_emi
CROSS JOIN accrual
CROSS JOIN dpi_due;
