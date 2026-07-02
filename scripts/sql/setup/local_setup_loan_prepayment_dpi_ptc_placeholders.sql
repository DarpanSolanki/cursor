-- Local Yugabyte only: backfill DPI_* placeholders on LOAN_PREPAYMENT product transaction catalogues.
-- Prod has these; many local DB dumps omit them after DPI feature was added to transaction_accounting_rule.
-- Maps DPI placeholders to the same IAD as their BILLED_* counterparts (same pattern as BILLED_INTEREST).
--
-- Usage (from workspace root):
--   PGPASSWORD=yugabyte psql -h localhost -p 5433 -U yugabyte -d yugabyte \
--     -v ON_ERROR_STOP=1 -f scripts/sql/setup/local_setup_loan_prepayment_dpi_ptc_placeholders.sql

\set ON_ERROR_STOP on

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT src.product_transaction_catalogue_id, 'DPI_BILLED_INTEREST', src.internal_account_definition_id, false
FROM mfi_accounting.product_transaction_catalogue__placeholder__iad src
JOIN mfi_accounting.product__transaction_catalogue ptc ON ptc.id = src.product_transaction_catalogue_id
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE src.placeholder_code = 'BILLED_INTEREST'
  AND src.is_deleted = false
  AND ptc.is_deleted = false
  AND tc.type = 'LOAN_PREPAYMENT'
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = src.product_transaction_catalogue_id
      AND x.placeholder_code = 'DPI_BILLED_INTEREST'
      AND x.is_deleted = false
  );

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT src.product_transaction_catalogue_id, 'DPI_BILLED_INT_WAIVE', src.internal_account_definition_id, false
FROM mfi_accounting.product_transaction_catalogue__placeholder__iad src
JOIN mfi_accounting.product__transaction_catalogue ptc ON ptc.id = src.product_transaction_catalogue_id
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE src.placeholder_code = 'BILLED_INT_WAIVE'
  AND src.is_deleted = false
  AND ptc.is_deleted = false
  AND tc.type = 'LOAN_PREPAYMENT'
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = src.product_transaction_catalogue_id
      AND x.placeholder_code = 'DPI_BILLED_INT_WAIVE'
      AND x.is_deleted = false
  );

-- Optional audit: products still missing rule placeholders (informational only)
\echo '--- LOAN_PREPAYMENT PTC gaps (informational; product 1 must be empty) ---'
SELECT ptc.product_id, missing.ph AS missing_placeholder
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id AND tc.type = 'LOAN_PREPAYMENT'
CROSS JOIN (
  SELECT DISTINCT ph FROM (
    SELECT debit_account_placeholder AS ph FROM mfi_accounting.transaction_accounting_rule
    WHERE transaction_catalogue_id IN (SELECT id FROM mfi_accounting.transaction_catalogue WHERE type = 'LOAN_PREPAYMENT' AND is_deleted = false)
      AND is_deleted = false
    UNION SELECT credit_account_placeholder FROM mfi_accounting.transaction_accounting_rule
    WHERE transaction_catalogue_id IN (SELECT id FROM mfi_accounting.transaction_catalogue WHERE type = 'LOAN_PREPAYMENT' AND is_deleted = false)
      AND is_deleted = false
    UNION SELECT fallback_credit_placeholder FROM mfi_accounting.transaction_accounting_rule
    WHERE transaction_catalogue_id IN (SELECT id FROM mfi_accounting.transaction_catalogue WHERE type = 'LOAN_PREPAYMENT' AND is_deleted = false)
      AND is_deleted = false
    UNION SELECT product_resolution_placeholder FROM mfi_accounting.transaction_accounting_rule
    WHERE transaction_catalogue_id IN (SELECT id FROM mfi_accounting.transaction_catalogue WHERE type = 'LOAN_PREPAYMENT' AND is_deleted = false)
      AND is_deleted = false
  ) u WHERE ph IS NOT NULL AND ph <> ''
) missing
WHERE ptc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad ptcpiad
    WHERE ptcpiad.product_transaction_catalogue_id = ptc.id
      AND ptcpiad.placeholder_code = missing.ph
      AND ptcpiad.is_deleted = false
  )
ORDER BY 1, 2
LIMIT 5;
