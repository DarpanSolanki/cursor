-- SDCP-11012: SHG parent DPI accrued must equal sum(child DPI accrued).
\set ON_ERROR_STOP on

WITH parent AS (
  SELECT account_id
  FROM mfi_accounting.loan_account
  WHERE account_id = :parent_loan_account_id::bigint
    AND has_child_accounts = true
    AND parent_loan_account_id IS NULL
),
children AS (
  SELECT la.account_id
  FROM mfi_accounting.loan_account la
  JOIN parent p ON la.parent_loan_account_id = p.account_id
  WHERE la.is_deleted = false
),
parent_total AS (
  SELECT COALESCE(SUM(d.total_accrued_amount), 0) AS amt
  FROM mfi_accounting.dpi_accrual_details d
  JOIN parent p ON p.account_id = d.loan_account_id
  WHERE d.is_deleted = false
),
child_total AS (
  SELECT COALESCE(SUM(d.total_accrued_amount), 0) AS amt
  FROM mfi_accounting.dpi_accrual_details d
  JOIN children c ON c.account_id = d.loan_account_id
  WHERE d.is_deleted = false
),
parent_outstanding AS (
  SELECT COALESCE(SUM(GREATEST(ldd.due_amount - ldd.paid_amount - ldd.waived_amount, 0)), 0) AS amt
  FROM mfi_accounting.loan_due_details ldd
  JOIN parent p ON p.account_id = ldd.loan_account_id
  WHERE ldd.component_type = 'DPI' AND ldd.is_deleted = false
),
child_outstanding AS (
  SELECT COALESCE(SUM(GREATEST(ldd.due_amount - ldd.paid_amount - ldd.waived_amount, 0)), 0) AS amt
  FROM mfi_accounting.loan_due_details ldd
  JOIN children c ON c.account_id = ldd.loan_account_id
  WHERE ldd.component_type = 'DPI' AND ldd.is_deleted = false
)
SELECT parent_total.amt AS parent_accrued,
       child_total.amt AS children_accrued_sum,
       parent_outstanding.amt AS parent_dpi_outstanding,
       child_outstanding.amt AS children_dpi_outstanding_sum,
       (parent_total.amt = child_total.amt) AS accrual_parity,
       (parent_outstanding.amt = child_outstanding.amt) AS outstanding_parity
FROM parent_total, child_total, parent_outstanding, child_outstanding;
