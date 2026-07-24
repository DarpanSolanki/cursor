-- Local Yugabyte only: backfill DPI_* placeholders on RSCH_LOAN_PREPAYMENT (+ LOAN_PART-PREPAYMENT)
-- for products that already have LOAN_PREPAYMENT DPI/BILLED_INTEREST mappings.
-- Needed for Vikram Sim B parentLoanAccountPartPrepayment (posts RSCH_LOAN_PREPAYMENT).
-- Symptom: Error while fetching InternalAccountDefinition … placeholder: DPI_BILLED_INTEREST
--
-- Usage:
--   PGPASSWORD=yugabyte psql -h localhost -p 5433 -U yugabyte -d yugabyte \
--     -v ON_ERROR_STOP=1 -f scripts/sql/setup/local_setup_rsch_loan_prepayment_dpi_ptc_placeholders.sql

\set ON_ERROR_STOP on

-- Prefer same-product LOAN_PREPAYMENT DPI_BILLED_INTEREST IAD; else BILLED_INTEREST.
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT rsch_ptc.id, 'DPI_BILLED_INTEREST', COALESCE(dpi.iad, billed.iad), false
FROM mfi_accounting.product__transaction_catalogue rsch_ptc
JOIN mfi_accounting.transaction_catalogue rsch_tc
  ON rsch_tc.id = rsch_ptc.transaction_catalogue_id
 AND rsch_tc.type = 'RSCH_LOAN_PREPAYMENT'
 AND rsch_ptc.is_deleted = false
LEFT JOIN LATERAL (
  SELECT iad.internal_account_definition_id AS iad
  FROM mfi_accounting.product__transaction_catalogue lp_ptc
  JOIN mfi_accounting.transaction_catalogue lp_tc ON lp_tc.id = lp_ptc.transaction_catalogue_id
  JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad iad
    ON iad.product_transaction_catalogue_id = lp_ptc.id AND iad.is_deleted = false
  WHERE lp_ptc.product_id = rsch_ptc.product_id AND lp_ptc.is_deleted = false
    AND lp_tc.type = 'LOAN_PREPAYMENT' AND iad.placeholder_code = 'DPI_BILLED_INTEREST'
  LIMIT 1
) dpi ON true
LEFT JOIN LATERAL (
  SELECT iad.internal_account_definition_id AS iad
  FROM mfi_accounting.product__transaction_catalogue lp_ptc
  JOIN mfi_accounting.transaction_catalogue lp_tc ON lp_tc.id = lp_ptc.transaction_catalogue_id
  JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad iad
    ON iad.product_transaction_catalogue_id = lp_ptc.id AND iad.is_deleted = false
  WHERE lp_ptc.product_id = rsch_ptc.product_id AND lp_ptc.is_deleted = false
    AND lp_tc.type = 'LOAN_PREPAYMENT' AND iad.placeholder_code = 'BILLED_INTEREST'
  LIMIT 1
) billed ON true
WHERE COALESCE(dpi.iad, billed.iad) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = rsch_ptc.id
      AND x.placeholder_code = 'DPI_BILLED_INTEREST' AND x.is_deleted = false
  );

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT rsch_ptc.id, 'DPI_BILLED_INT_WAIVE', COALESCE(dpi.iad, waive.iad), false
FROM mfi_accounting.product__transaction_catalogue rsch_ptc
JOIN mfi_accounting.transaction_catalogue rsch_tc
  ON rsch_tc.id = rsch_ptc.transaction_catalogue_id
 AND rsch_tc.type = 'RSCH_LOAN_PREPAYMENT'
 AND rsch_ptc.is_deleted = false
LEFT JOIN LATERAL (
  SELECT iad.internal_account_definition_id AS iad
  FROM mfi_accounting.product__transaction_catalogue lp_ptc
  JOIN mfi_accounting.transaction_catalogue lp_tc ON lp_tc.id = lp_ptc.transaction_catalogue_id
  JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad iad
    ON iad.product_transaction_catalogue_id = lp_ptc.id AND iad.is_deleted = false
  WHERE lp_ptc.product_id = rsch_ptc.product_id AND lp_ptc.is_deleted = false
    AND lp_tc.type = 'LOAN_PREPAYMENT' AND iad.placeholder_code = 'DPI_BILLED_INT_WAIVE'
  LIMIT 1
) dpi ON true
LEFT JOIN LATERAL (
  SELECT iad.internal_account_definition_id AS iad
  FROM mfi_accounting.product__transaction_catalogue lp_ptc
  JOIN mfi_accounting.transaction_catalogue lp_tc ON lp_tc.id = lp_ptc.transaction_catalogue_id
  JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad iad
    ON iad.product_transaction_catalogue_id = lp_ptc.id AND iad.is_deleted = false
  WHERE lp_ptc.product_id = rsch_ptc.product_id AND lp_ptc.is_deleted = false
    AND lp_tc.type = 'LOAN_PREPAYMENT' AND iad.placeholder_code = 'BILLED_INT_WAIVE'
  LIMIT 1
) waive ON true
WHERE COALESCE(dpi.iad, waive.iad) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = rsch_ptc.id
      AND x.placeholder_code = 'DPI_BILLED_INT_WAIVE' AND x.is_deleted = false
  );

-- Any other rule placeholders missing on RSCH: copy IAD from same-product LOAN_PREPAYMENT
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT rsch_ptc.id, needed.ph, lp_iad.internal_account_definition_id, false
FROM mfi_accounting.product__transaction_catalogue rsch_ptc
JOIN mfi_accounting.transaction_catalogue rsch_tc
  ON rsch_tc.id = rsch_ptc.transaction_catalogue_id
 AND rsch_tc.type = 'RSCH_LOAN_PREPAYMENT'
 AND rsch_ptc.is_deleted = false
JOIN LATERAL (
  SELECT DISTINCT ph FROM (
    SELECT debit_account_placeholder AS ph FROM mfi_accounting.transaction_accounting_rule
    WHERE transaction_catalogue_id = rsch_tc.id AND is_deleted = false
    UNION SELECT credit_account_placeholder FROM mfi_accounting.transaction_accounting_rule
    WHERE transaction_catalogue_id = rsch_tc.id AND is_deleted = false
    UNION SELECT fallback_credit_placeholder FROM mfi_accounting.transaction_accounting_rule
    WHERE transaction_catalogue_id = rsch_tc.id AND is_deleted = false
    UNION SELECT product_resolution_placeholder FROM mfi_accounting.transaction_accounting_rule
    WHERE transaction_catalogue_id = rsch_tc.id AND is_deleted = false
  ) u WHERE ph IS NOT NULL AND ph <> ''
) needed ON true
JOIN mfi_accounting.product__transaction_catalogue lp_ptc
  ON lp_ptc.product_id = rsch_ptc.product_id AND lp_ptc.is_deleted = false
JOIN mfi_accounting.transaction_catalogue lp_tc
  ON lp_tc.id = lp_ptc.transaction_catalogue_id AND lp_tc.type = 'LOAN_PREPAYMENT'
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad lp_iad
  ON lp_iad.product_transaction_catalogue_id = lp_ptc.id
 AND lp_iad.placeholder_code = needed.ph
 AND lp_iad.is_deleted = false
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
  WHERE x.product_transaction_catalogue_id = rsch_ptc.id
    AND x.placeholder_code = needed.ph AND x.is_deleted = false
);

\echo '=== product 44 RSCH_LOAN_PREPAYMENT DPI placeholders ==='
SELECT iad.placeholder_code, iad.internal_account_definition_id
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad iad
  ON iad.product_transaction_catalogue_id = ptc.id AND iad.is_deleted = false
WHERE ptc.product_id = 44 AND ptc.is_deleted = false AND tc.type = 'RSCH_LOAN_PREPAYMENT'
  AND iad.placeholder_code ILIKE 'DPI%'
ORDER BY 1;
