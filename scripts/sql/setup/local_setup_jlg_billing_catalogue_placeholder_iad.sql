-- Local setup — JLG (product_id=2) BILLING/NORMAL_BILLING catalogue + placeholder→IAD map.
--
-- Why: a freshly disbursed JLG loan runs interestAccrualCalculation and
-- interestAccrualPosting fine, then loanAccountBillingJob FAILS on the first due
-- date with 134207 ("Product Transaction Catalogue, Placeholder and Internal
-- Account Definition configuration missing") because product 2 has no
-- product__transaction_catalogue row for transaction_catalogue_id=7
-- (BILLING/NORMAL_BILLING). Products 1 and 44 have it; product 2 does not.
--
-- IAD ids are copied from the golden reference product (product_id=1) for the
-- same transaction_catalogue_id — never invented. See
-- .cursor/rules/accounting-134207-placeholder-iad.md.
--
-- Local only (127.0.0.1:5433). Idempotent. Run via:
--   bash scripts/bin/db-local-write.sh --file scripts/sql/setup/local_setup_jlg_billing_catalogue_placeholder_iad.sql

SET search_path TO mfi_accounting;

\set target_product_id 2
\set golden_product_id 1
\set billing_catalogue_id 7

-- 1) product ↔ BILLING catalogue link
INSERT INTO product__transaction_catalogue
  (product_id, transaction_catalogue_id, created_on, created_by, updated_on, updated_by, is_deleted)
SELECT :target_product_id, :billing_catalogue_id, NOW(), 'LOCAL_SETUP', NOW(), 'LOCAL_SETUP', false
WHERE NOT EXISTS (
  SELECT 1 FROM product__transaction_catalogue
  WHERE product_id = :target_product_id
    AND transaction_catalogue_id = :billing_catalogue_id
    AND is_deleted = false
);

-- 2) placeholder → internal account definition, copied from the golden product
INSERT INTO product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT tgt.id, g.placeholder_code, g.internal_account_definition_id, false
FROM product__transaction_catalogue tgt
JOIN product__transaction_catalogue gold
  ON gold.product_id = :golden_product_id
 AND gold.transaction_catalogue_id = :billing_catalogue_id
 AND gold.is_deleted = false
JOIN product_transaction_catalogue__placeholder__iad g
  ON g.product_transaction_catalogue_id = gold.id
 AND g.is_deleted = false
WHERE tgt.product_id = :target_product_id
  AND tgt.transaction_catalogue_id = :billing_catalogue_id
  AND tgt.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = tgt.id
      AND x.placeholder_code = g.placeholder_code
      AND x.is_deleted = false
  );

-- 3) verify: every placeholder the BILLING rules reference must now resolve
SELECT tgt.product_id,
       x.placeholder_code,
       x.internal_account_definition_id
FROM product__transaction_catalogue tgt
JOIN product_transaction_catalogue__placeholder__iad x
  ON x.product_transaction_catalogue_id = tgt.id AND x.is_deleted = false
WHERE tgt.product_id = :target_product_id
  AND tgt.transaction_catalogue_id = :billing_catalogue_id
  AND tgt.is_deleted = false
ORDER BY x.placeholder_code;
