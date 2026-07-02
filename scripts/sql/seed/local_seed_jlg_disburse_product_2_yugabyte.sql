-- Local Yugabyte seed: JLG disburse (LOS product_id=2, loan_product id=6, OTHBACCT / NEFT v1).
-- Run: psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 -f scripts/sql/seed/local_seed_jlg_disburse_product_2_yugabyte.sql
\set ON_ERROR_STOP on
SET search_path TO mfi_accounting, public;

INSERT INTO loan_product_allowed_disbursement_modes (loan_product_id, disbursement_mode)
SELECT 6, 'OTHBACCT'
WHERE NOT EXISTS (
  SELECT 1 FROM loan_product_allowed_disbursement_modes
  WHERE loan_product_id = 6 AND disbursement_mode = 'OTHBACCT'
);

-- product__transaction_catalogue.id=7 is (product_id=2, transaction_catalogue_id=1).
INSERT INTO product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT v.ptc_id, v.placeholder_code, v.iad_id, false
FROM (VALUES
  (7, 'PROC_FEE', 71),
  (7, 'STAMP_DUTY_AMT', 691),
  (7, 'CGST', 1495),
  (7, 'IGST', 1493),
  (7, 'SGST', 1494),
  (7, 'GST_PAYABLE', 1492),
  (7, 'UTGST', 1491)
) AS v(ptc_id, placeholder_code, iad_id)
WHERE NOT EXISTS (
  SELECT 1 FROM product_transaction_catalogue__placeholder__iad x
  WHERE x.product_transaction_catalogue_id = v.ptc_id
    AND x.placeholder_code = v.placeholder_code
    AND x.is_deleted = false
);

SELECT loan_product_id, disbursement_mode
FROM loan_product_allowed_disbursement_modes
WHERE loan_product_id = 6
ORDER BY disbursement_mode;

SELECT placeholder_code, internal_account_definition_id
FROM product_transaction_catalogue__placeholder__iad
WHERE product_transaction_catalogue_id = 7 AND is_deleted = false
ORDER BY placeholder_code;
