-- Local harness: product 44 (loan_product_id 70 DCF SHG) PART_PREPAYMENT PTC 463
-- missing DPI_BILLED_INTEREST → 134207 on postTransaction (TAR requires it).
-- Copy IAD from same product's LOAN_PREPAYMENT mapping (ptc 3277 / 6293).
\set ON_ERROR_STOP on
SET search_path TO mfi_accounting;

INSERT INTO product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT 463, 'DPI_BILLED_INTEREST', src.internal_account_definition_id, false
FROM product_transaction_catalogue__placeholder__iad src
WHERE src.product_transaction_catalogue_id = 3277
  AND src.placeholder_code = 'DPI_BILLED_INTEREST'
  AND COALESCE(src.is_deleted, false) = false
  AND NOT EXISTS (
    SELECT 1 FROM product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = 463
      AND x.placeholder_code = 'DPI_BILLED_INTEREST'
      AND COALESCE(x.is_deleted, false) = false
  )
LIMIT 1;

-- Fallback if 3277 missing: use IAD 6293 (standard DPI billed interest in local seeds)
INSERT INTO product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT 463, 'DPI_BILLED_INTEREST', 6293, false
WHERE NOT EXISTS (
  SELECT 1 FROM product_transaction_catalogue__placeholder__iad x
  WHERE x.product_transaction_catalogue_id = 463
    AND x.placeholder_code = 'DPI_BILLED_INTEREST'
    AND COALESCE(x.is_deleted, false) = false
)
AND EXISTS (SELECT 1 FROM internal_account_definition WHERE id = 6293);
