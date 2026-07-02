-- Assert billing events: one GL txn per billing day, due rows match billed aggregate per day.
\set ON_ERROR_STOP on

WITH params AS (
  SELECT :loan_account_id::bigint AS loan_id
),
billing_events AS (
  SELECT billing_posting_date::date AS bill_d,
         billing_transaction_ref_number AS ref,
         SUM(total_accrued_amount) AS billed_amt
  FROM mfi_accounting.dpi_accrual_details da
  CROSS JOIN params p
  WHERE da.loan_account_id = p.loan_id
    AND da.is_deleted = false
    AND da.billing_posting_date IS NOT NULL
    AND da.total_accrued_amount > 0
  GROUP BY billing_posting_date::date, billing_transaction_ref_number
),
dup_ref_per_day AS (
  SELECT bill_d
  FROM billing_events
  GROUP BY bill_d
  HAVING COUNT(DISTINCT ref) > 1
),
due_by_day AS (
  SELECT due_date::date AS due_d, SUM(due_amount) AS due_amt
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN params p
  WHERE ldd.loan_account_id = p.loan_id
    AND ldd.component_type = 'DPI'
    AND ldd.is_deleted = false
  GROUP BY due_date::date
),
billed_by_day AS (
  SELECT bill_d, SUM(billed_amt) AS billed_amt, COUNT(DISTINCT ref) AS txn_count
  FROM billing_events
  GROUP BY bill_d
),
mismatch AS (
  SELECT b.bill_d
  FROM billed_by_day b
  LEFT JOIN due_by_day d ON d.due_d = b.bill_d
  WHERE d.due_d IS NULL OR ABS(b.billed_amt - d.due_amt) > 0.001
)
SELECT
  (SELECT COUNT(*) FROM dup_ref_per_day) AS dup_ref_days,
  (SELECT COUNT(*) FROM mismatch) AS billed_due_mismatch_days,
  (SELECT COUNT(DISTINCT bill_d) FROM billing_events) AS billing_event_days,
  (SELECT COUNT(*) FROM due_by_day) AS dpi_due_days;
