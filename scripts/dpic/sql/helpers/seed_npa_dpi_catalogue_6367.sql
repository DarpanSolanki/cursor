-- Link REGULAR_TO_NPA / NPA_TO_REGULAR DPI catalogues (1331, 1332) for product 6367.
-- Idempotent — safe before loanAccountAssetCriteriaJob NPA DPI movement E2E.
\set ON_ERROR_STOP on

BEGIN;

INSERT INTO mfi_accounting.product__transaction_catalogue
    (product_id, transaction_catalogue_id, created_on, created_by, updated_on, updated_by, is_deleted)
SELECT 6367, tc_id, NOW(), 'LOCAL_NPA_DPI_TEST', NOW(), 'LOCAL_NPA_DPI_TEST', false
FROM (VALUES (1331), (1332)) AS v(tc_id)
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product__transaction_catalogue t
  WHERE t.product_id = 6367 AND t.transaction_catalogue_id = v.tc_id AND t.is_deleted = false
);

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
    (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, m.placeholder_code, m.iad_id, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN (VALUES
  (1331, 'LOAN_ACCOUNT',         28),
  (1331, 'DPI_INT_INC',           6),
  (1331, 'DPI_INT_SUSP',          8),
  (1331, 'DPI_INT_SUSP_AIR',     12),
  (1332, 'LOAN_ACCOUNT',         28),
  (1332, 'DPI_INT_INC',           6),
  (1332, 'DPI_INT_SUSP',          8),
  (1332, 'DPI_INT_SUSP_AIR',     12)
) AS m(cat_id, placeholder_code, iad_id) ON m.cat_id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 6367 AND ptc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = m.placeholder_code
      AND x.is_deleted = false
  );

COMMIT;
