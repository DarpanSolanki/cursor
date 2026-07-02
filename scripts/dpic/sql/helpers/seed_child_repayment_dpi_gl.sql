-- Link LOAN_REPAYMENT catalogue + DPI_BILLED_INTEREST placeholder for JLG child product 44.
\set ON_ERROR_STOP on

BEGIN;

INSERT INTO mfi_accounting.product__transaction_catalogue
    (product_id, transaction_catalogue_id, created_on, created_by, updated_on, updated_by, is_deleted)
SELECT 44, src.transaction_catalogue_id, NOW(), 'LOCAL_CHILD_DPI_TEST', NOW(), 'LOCAL_CHILD_DPI_TEST', false
FROM mfi_accounting.product__transaction_catalogue src
WHERE src.product_id = 6367 AND src.transaction_catalogue_id = 3 AND src.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product__transaction_catalogue t
    WHERE t.product_id = 44 AND t.transaction_catalogue_id = 3 AND t.is_deleted = false
  );

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
    (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'DPI_BILLED_INTEREST', 6293, false
FROM mfi_accounting.product__transaction_catalogue ptc
WHERE ptc.product_id = 44 AND ptc.transaction_catalogue_id = 3 AND ptc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'DPI_BILLED_INTEREST'
      AND x.is_deleted = false
  );

COMMIT;
