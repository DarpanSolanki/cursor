-- Link DPI EOD catalogues + placeholder IADs for bulk perf (scheme 48 / SHGDL pool).
-- Clones the E/F/G blocks from setup_local_dev_product_6367.sql for any product+scheme.
--
-- Usage:
--   psql ... -v ON_ERROR_STOP=1 \
--     -v product_id=44 -v product_scheme_id=48 \
--     -v source_office_id=1 -v target_office_id=2 \
--     -f scripts/dpic/sql/helpers/seed_dpi_gl_for_bulk_perf.sql
--
-- Prerequisite: scripts/dpic/sql/seed_accounting_rules_from_product_doc.sql

\set ON_ERROR_STOP on

BEGIN;

INSERT INTO mfi_accounting.internal_account (
  office_id, internal_account_definition_id, code, name, description,
  balance_limit, created_on, created_by, updated_on, updated_by, is_deleted
)
SELECT :target_office_id, src.internal_account_definition_id, src.code, src.name, src.description,
       src.balance_limit, NOW(), 'DPIC_BULK_PERF', NOW(), 'DPIC_BULK_PERF', false
FROM mfi_accounting.internal_account src
WHERE src.office_id = :source_office_id
  AND src.is_deleted = false
  AND src.internal_account_definition_id IN (5, 6, 8, 12, 28, 6293)
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.internal_account tgt
    WHERE tgt.office_id = :target_office_id
      AND tgt.internal_account_definition_id = src.internal_account_definition_id
      AND tgt.is_deleted = false
  );

INSERT INTO mfi_accounting.product__transaction_catalogue
    (product_id, transaction_catalogue_id, created_on, created_by, updated_on, updated_by, is_deleted)
SELECT :product_id, tc_id, NOW(), 'DPIC_BULK_PERF', NOW(), 'DPIC_BULK_PERF', false
FROM (VALUES (1327), (1328), (1329), (1330)) AS v(tc_id)
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product__transaction_catalogue t
  WHERE t.product_id = :product_id AND t.transaction_catalogue_id = v.tc_id AND t.is_deleted = false
);

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
    (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, m.placeholder_code, m.iad_id, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN (VALUES
  (1327, 'LOAN_ACCOUNT',         28),
  (1327, 'DPI_ACC_NOT_DUE',       5),
  (1327, 'DPI_INT_INC',           6),
  (1328, 'LOAN_ACCOUNT',         28),
  (1328, 'DPI_ACC_NOT_DUE',       5),
  (1328, 'DPI_INT_SUSP_AIR',     12),
  (1329, 'LOAN_ACCOUNT',         28),
  (1329, 'DPI_INT_SUSP_AIR',     12),
  (1329, 'DPI_INT_SUSP',          8),
  (1330, 'LOAN_ACCOUNT',         28),
  (1330, 'DPI_ACC_NOT_DUE',       5),
  (1330, 'DPI_BILLED_INTEREST', 6293)
) AS m(cat_id, placeholder_code, iad_id) ON m.cat_id = ptc.transaction_catalogue_id
WHERE ptc.product_id = :product_id AND ptc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = m.placeholder_code
      AND x.is_deleted = false
  );

INSERT INTO mfi_accounting.product_scheme__transaction_accounting_rule__price_setup
    (product_scheme_id, transaction_accounting_rule_id, price_setup_code, is_deleted, updated_on, updated_by)
SELECT :product_scheme_id, tar.id, 'DPI_EOD', false, NOW(), 'DPIC_BULK_PERF'
FROM mfi_accounting.transaction_accounting_rule tar
WHERE tar.transaction_catalogue_id IN (1327, 1328, 1329, 1330)
  AND tar.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_scheme__transaction_accounting_rule__price_setup x
    WHERE x.product_scheme_id = :product_scheme_id
      AND x.transaction_accounting_rule_id = tar.id
      AND x.is_deleted = false
  );

INSERT INTO mfi_accounting.product_scheme__transaction_catalogue__price_setup
    (product_scheme_id, transaction_catalogue_id, price_setup_code, is_deleted, updated_on, updated_by)
SELECT :product_scheme_id, tc_id, 'DPI_EOD', false, NOW(), 'DPIC_BULK_PERF'
FROM (VALUES (1327), (1328), (1329), (1330)) AS v(tc_id)
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product_scheme__transaction_catalogue__price_setup x
  WHERE x.product_scheme_id = :product_scheme_id
    AND x.transaction_catalogue_id = v.tc_id
    AND x.price_setup_code = 'DPI_EOD'
    AND x.is_deleted = false
);

COMMIT;

\echo '=== seed_dpi_gl_for_bulk_perf summary ==='
SELECT 'office_iads=' || COUNT(*) FROM mfi_accounting.internal_account
WHERE office_id = :target_office_id AND internal_account_definition_id IN (5,6,8,12,28,6293) AND is_deleted = false;
SELECT 'dpi_ptc=' || COUNT(*) FROM mfi_accounting.product__transaction_catalogue
WHERE product_id = :product_id AND transaction_catalogue_id BETWEEN 1327 AND 1330 AND is_deleted = false;
SELECT 'scheme_dpi_eod=' || COUNT(*) FROM mfi_accounting.product_scheme__transaction_catalogue__price_setup
WHERE product_scheme_id = :product_scheme_id AND price_setup_code = 'DPI_EOD' AND is_deleted = false;
