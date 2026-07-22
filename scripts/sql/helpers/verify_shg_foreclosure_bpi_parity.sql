-- SDCP-11058 / SHG foreclosure BPI parity (any N children)
-- Assert: parent APPROVED bpi_amount == SUM(child APPROVED bpi_amount)
-- Usage: psql ... -v parent_lan="'6009717926'" -f verify_shg_foreclosure_bpi_parity.sql

WITH parent AS (
  SELECT p.account_id, a.account_number
  FROM mfi_accounting.loan_account p
  JOIN mfi_accounting.account a ON a.id = p.account_id
  WHERE a.account_number = :parent_lan AND p.is_deleted = false
),
kids AS (
  SELECT c.account_id, ca.account_number
  FROM mfi_accounting.loan_account c
  JOIN mfi_accounting.account ca ON ca.id = c.account_id
  JOIN parent ON c.parent_loan_account_id = parent.account_id
  WHERE c.is_deleted = false
),
pb AS (
  SELECT pd.bpi_amount::numeric AS bpi, pd.receipt_number
  FROM mfi_accounting.prepayment_details pd
  JOIN parent ON pd.loan_account_id = parent.account_id
  WHERE pd.is_deleted = false AND pd.prepayment_status = 'APPROVED'
  ORDER BY pd.id DESC
  LIMIT 1
),
cb AS (
  SELECT COALESCE(SUM(pd.bpi_amount::numeric), 0) AS bpi_sum, COUNT(*) AS n_children
  FROM mfi_accounting.prepayment_details pd
  JOIN kids k ON k.account_id = pd.loan_account_id
  WHERE pd.is_deleted = false AND pd.prepayment_status = 'APPROVED'
)
SELECT
  (SELECT account_number FROM parent) AS parent_lan,
  (SELECT bpi FROM pb) AS parent_bpi,
  (SELECT bpi_sum FROM cb) AS children_bpi_sum,
  (SELECT n_children FROM cb) AS n_children,
  ((SELECT bpi FROM pb) = (SELECT bpi_sum FROM cb)) AS bpi_parity;
