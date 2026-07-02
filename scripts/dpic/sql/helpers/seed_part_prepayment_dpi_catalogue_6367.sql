-- Link LOAN_PART-PREPAYMENT (catalogue 10) for product 6367 — copy placeholders from cat 11.
-- Idempotent — safe before loanAccountPartPrepayment TRIAL write E2E.
\set ON_ERROR_STOP on

BEGIN;

INSERT INTO mfi_accounting.product__transaction_catalogue
    (product_id, transaction_catalogue_id, created_on, created_by, updated_on, updated_by, is_deleted)
SELECT 6367, 10, NOW(), 'LOCAL_PART_PREP_DPI_TEST', NOW(), 'LOCAL_PART_PREP_DPI_TEST', false
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product__transaction_catalogue t
  WHERE t.product_id = 6367 AND t.transaction_catalogue_id = 10 AND t.is_deleted = false
);

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
    (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc10.id, src.placeholder_code, src.internal_account_definition_id, false
FROM mfi_accounting.product__transaction_catalogue ptc10
JOIN mfi_accounting.product__transaction_catalogue ptc11
  ON ptc11.product_id = 6367 AND ptc11.transaction_catalogue_id = 11 AND ptc11.is_deleted = false
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad src
  ON src.product_transaction_catalogue_id = ptc11.id AND src.is_deleted = false
WHERE ptc10.product_id = 6367 AND ptc10.transaction_catalogue_id = 10 AND ptc10.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc10.id
      AND x.placeholder_code = src.placeholder_code
      AND x.is_deleted = false
  );

COMMIT;
