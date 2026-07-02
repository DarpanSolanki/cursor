-- Assert multi-EMI overdue: dpi_accrual_details stamps latest overdue INT installment (not earliest-only).
-- Expect rows on both EMI1 and EMI2; latest accrual row (max end_date) on EMI2 when job_time past EMI2 grace.
\set ON_ERROR_STOP on

WITH ints AS (
  SELECT ldd.loan_installment_details_id AS inst_id,
         ldd.due_date::date AS due_date,
         ROW_NUMBER() OVER (ORDER BY ldd.due_date, ldd.loan_installment_details_id) AS emi_n
  FROM mfi_accounting.loan_due_details ldd
  WHERE ldd.loan_account_id = :loan_account_id::bigint
    AND ldd.is_deleted = false
    AND ldd.component_type = 'INT'
    AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
),
emi AS (
  SELECT MAX(CASE WHEN emi_n = 1 THEN inst_id END) AS emi1_id,
         MAX(CASE WHEN emi_n = 2 THEN inst_id END) AS emi2_id,
         MAX(CASE WHEN emi_n = 1 THEN due_date END) AS emi1_due,
         MAX(CASE WHEN emi_n = 2 THEN due_date END) AS emi2_due
  FROM ints
),
rows AS (
  SELECT da.installment_id, da.end_date, da.total_accrued_amount
  FROM mfi_accounting.dpi_accrual_details da
  WHERE da.loan_account_id = :loan_account_id::bigint
    AND da.is_deleted = false
    AND da.total_accrued_amount > 0
),
stats AS (
  SELECT e.emi1_id,
         e.emi2_id,
         (SELECT COUNT(*) FROM rows r WHERE r.installment_id = e.emi1_id) AS rows_on_emi1,
         (SELECT COUNT(*) FROM rows r WHERE r.installment_id = e.emi2_id) AS rows_on_emi2,
         (SELECT r.installment_id FROM rows r ORDER BY r.end_date DESC, r.installment_id DESC LIMIT 1) AS latest_inst_id
  FROM emi e
)
SELECT emi1_id,
       emi2_id,
       rows_on_emi1,
       rows_on_emi2,
       latest_inst_id
FROM stats;
