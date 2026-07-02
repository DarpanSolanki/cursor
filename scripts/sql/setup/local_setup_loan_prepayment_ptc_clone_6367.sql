-- Local only: clone LOAN_PREPAYMENT PTC + placeholders from product 6267 → 6367 (DPI LAN 6004044425).
\set ON_ERROR_STOP on

WITH src_ptc AS (
  SELECT ptc.id AS src_ptc_id, ptc.transaction_catalogue_id
  FROM mfi_accounting.product__transaction_catalogue ptc
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id AND tc.type = 'LOAN_PREPAYMENT'
  WHERE ptc.product_id = 6267 AND ptc.is_deleted = false
  LIMIT 1
),
new_ptc AS (
  INSERT INTO mfi_accounting.product__transaction_catalogue
    (product_id, transaction_catalogue_id, created_on, created_by, updated_on, updated_by, is_deleted)
  SELECT 6367, src_ptc.transaction_catalogue_id, NOW(), 'LOCAL_ICF', NOW(), 'LOCAL_ICF', false
  FROM src_ptc
  WHERE NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product__transaction_catalogue x
    JOIN mfi_accounting.transaction_catalogue tc ON tc.id = x.transaction_catalogue_id AND tc.type = 'LOAN_PREPAYMENT'
    WHERE x.product_id = 6367 AND x.is_deleted = false
  )
  RETURNING id AS new_ptc_id
),
target_ptc AS (
  SELECT COALESCE(
    (SELECT new_ptc_id FROM new_ptc),
    (SELECT x.id FROM mfi_accounting.product__transaction_catalogue x
     JOIN mfi_accounting.transaction_catalogue tc ON tc.id = x.transaction_catalogue_id AND tc.type = 'LOAN_PREPAYMENT'
     WHERE x.product_id = 6367 AND x.is_deleted = false LIMIT 1)
  ) AS ptc_id
),
src_ptc2 AS (
  SELECT ptc.id AS src_ptc_id
  FROM mfi_accounting.product__transaction_catalogue ptc
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id AND tc.type = 'LOAN_PREPAYMENT'
  WHERE ptc.product_id = 6267 AND ptc.is_deleted = false
  LIMIT 1
)
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT t.ptc_id, s.placeholder_code, s.internal_account_definition_id, false
FROM target_ptc t
CROSS JOIN src_ptc2 sp
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad s
  ON s.product_transaction_catalogue_id = sp.src_ptc_id AND s.is_deleted = false
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
  WHERE x.product_transaction_catalogue_id = t.ptc_id
    AND x.placeholder_code = s.placeholder_code
    AND x.is_deleted = false
);
