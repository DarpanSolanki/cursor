-- UD §5.4 billing assertions: one aggregated bill per anchor installment; due_date = NEXT EMI.
-- Usage: psql ... -v loan_account_id=5934060 -v anchor_installment_id=5937436 -f verify_dpi_billing_ud.sql
\set ON_ERROR_STOP on

WITH anchor AS (
  SELECT :anchor_installment_id::bigint AS installment_id,
         lid.installment_date AS overdue_emi_date
  FROM mfi_accounting.loan_installment_details lid
  WHERE lid.id = :anchor_installment_id::bigint
    AND lid.loan_account_id = :loan_account_id::bigint
),
next_emi AS (
  SELECT n.id AS next_installment_id, n.installment_date AS next_emi_date
  FROM anchor a
  JOIN mfi_accounting.loan_installment_details n
    ON n.loan_account_id = :loan_account_id::bigint
   AND n.is_deleted = false
   AND n.is_part_prepayment_entry = false
   AND n.installment_date > a.overdue_emi_date
  ORDER BY n.installment_date ASC
  LIMIT 1
),
accrual AS (
  SELECT COUNT(*) FILTER (WHERE billing_posting_date IS NOT NULL AND total_accrued_amount > 0) AS billed_rows,
         COUNT(DISTINCT billing_transaction_ref_number)
           FILTER (WHERE billing_transaction_ref_number IS NOT NULL) AS billing_txn_count,
         COUNT(DISTINCT DATE(billing_posting_date))
           FILTER (WHERE billing_posting_date IS NOT NULL) AS billing_posting_days,
         COALESCE(SUM(total_accrued_amount) FILTER (WHERE billing_posting_date IS NOT NULL), 0) AS billed_amount
  FROM mfi_accounting.dpi_accrual_details
  WHERE loan_account_id = :loan_account_id::bigint
    AND installment_id = :anchor_installment_id::bigint
    AND is_deleted = false
),
dpi_due AS (
  SELECT COUNT(*) AS due_rows,
         MAX(ldd.due_date) AS due_date,
         MAX(ldd.loan_installment_details_id) AS due_installment_id,
         COALESCE(SUM(ldd.due_amount), 0) AS due_amount
  FROM mfi_accounting.loan_due_details ldd
  CROSS JOIN next_emi ne
  WHERE ldd.loan_account_id = :loan_account_id::bigint
    AND ldd.component_type = 'DPI'
    AND ldd.is_deleted = false
    AND ldd.loan_installment_details_id = ne.next_installment_id
),
txn AS (
  SELECT tm.transaction_value_date, tm.reference_number
  FROM mfi_accounting.transaction_master tm
  JOIN accrual a ON a.billing_txn_count = 1
  WHERE tm.reference_number = (
    SELECT DISTINCT billing_transaction_ref_number
    FROM mfi_accounting.dpi_accrual_details
    WHERE loan_account_id = :loan_account_id::bigint
      AND installment_id = :anchor_installment_id::bigint
      AND billing_transaction_ref_number IS NOT NULL
    LIMIT 1
  )
)
SELECT accrual.billed_rows,
       accrual.billing_txn_count,
       accrual.billing_posting_days,
       accrual.billed_amount,
       dpi_due.due_rows,
       dpi_due.due_date,
       dpi_due.due_installment_id,
       dpi_due.due_amount,
       next_emi.next_emi_date,
       next_emi.next_installment_id,
       txn.transaction_value_date,
       (dpi_due.due_installment_id = next_emi.next_installment_id) AS due_on_next_emi,
       (DATE(txn.transaction_value_date) = next_emi.next_emi_date) AS value_date_on_next_emi,
       (accrual.billing_txn_count <= 1 AND accrual.billing_posting_days <= 1) AS aggregated_billing
FROM accrual
CROSS JOIN dpi_due
LEFT JOIN next_emi ON true
LEFT JOIN txn ON true;
