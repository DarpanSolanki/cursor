-- Assert: during EMI2 grace, DPI on EMI1 continues (per-installment grace / LPP parity).
-- Fixture: loan with grac=3, EMI1 due first_emi_due_date, EMI2 = first+1 month.
-- Job time must fall in EMI2 due..EMI2_overdue-1 (e.g. EMI1=2026-05-14, EMI2=2026-06-14,
-- EMI2 overdue=2026-06-18 → run as-of 2026-06-17).
\set ON_ERROR_STOP on

WITH dues AS (
  SELECT DISTINCT ON (ldd.loan_installment_details_id)
         ldd.loan_installment_details_id AS installment_id,
         ldd.due_date::date AS due_day,
         (ldd.due_date::date + ((:grace_days::int + 1) || ' days')::interval)::date AS overdue_day
  FROM mfi_accounting.loan_due_details ldd
  WHERE ldd.loan_account_id = :loan_account_id::bigint
    AND ldd.is_deleted = false
    AND ldd.component_type = 'INT'
    AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
  ORDER BY ldd.loan_installment_details_id, ldd.due_date
),
ordered AS (
  SELECT installment_id, due_day, overdue_day,
         ROW_NUMBER() OVER (ORDER BY due_day) AS rn
  FROM dues
),
emi1 AS (SELECT * FROM ordered WHERE rn = 1),
emi2 AS (SELECT * FROM ordered WHERE rn = 2),
overlap AS (
  SELECT COUNT(*) AS rows_in_emi2_grace,
         COALESCE(SUM(d.total_accrued_amount), 0) AS amt_in_emi2_grace,
         COUNT(*) FILTER (
           WHERE d.installment_id = (SELECT installment_id FROM emi1)
             AND d.total_accrued_amount > 0
         ) AS emi1_rows_in_overlap,
         COUNT(*) FILTER (
           WHERE d.installment_id = (SELECT installment_id FROM emi2)
         ) AS emi2_rows_in_overlap
  FROM mfi_accounting.dpi_accrual_details d
  JOIN emi2 e2 ON true
  WHERE d.loan_account_id = :loan_account_id::bigint
    AND d.is_deleted = false
    AND d.total_accrued_amount > 0
    AND d.end_date::date > e2.due_day
    AND d.end_date::date < e2.overdue_day
)
SELECT (SELECT installment_id FROM emi1) AS emi1_id,
       (SELECT due_day FROM emi1) AS emi1_due,
       (SELECT overdue_day FROM emi1) AS emi1_overdue,
       (SELECT installment_id FROM emi2) AS emi2_id,
       (SELECT due_day FROM emi2) AS emi2_due,
       (SELECT overdue_day FROM emi2) AS emi2_overdue,
       o.rows_in_emi2_grace,
       o.amt_in_emi2_grace,
       o.emi1_rows_in_overlap,
       o.emi2_rows_in_overlap,
       (o.emi1_rows_in_overlap > 0 AND o.amt_in_emi2_grace > 0 AND o.emi2_rows_in_overlap = 0) AS overlap_ok
FROM overlap o;
