-- Local Yugabyte: DPI placeholders on DEATH_FORECLOSURE + RSCH_DEATH_FORECLOSURE catalogues.
-- Symptom: postTransaction 134207 — placeholder DPI_BILLED_INTEREST on catalogue 22 (product 44 JLG).
-- Idempotent; safe to re-run before deathForeclosureInsuranceJob e2e.
\set ON_ERROR_STOP on

\echo '--- DPI placeholders on DCF catalogues (all products) ---'
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, v.ph, v.iad, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
CROSS JOIN (VALUES
  ('DPI_BILLED_INTEREST', 6293),
  ('DPI_BILLED_INT_WAIVE', 4593)
) AS v(ph, iad)
WHERE ptc.is_deleted = false
  AND tc.type IN ('DEATH_FORECLOSURE', 'RSCH_DEATH_FORECLOSURE')
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = v.ph
      AND x.is_deleted = false
  );

SELECT tc.type, ptc.product_id, p.placeholder_code, p.internal_account_definition_id
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad p
  ON p.product_transaction_catalogue_id = ptc.id AND p.is_deleted = false
WHERE tc.type IN ('DEATH_FORECLOSURE', 'RSCH_DEATH_FORECLOSURE')
  AND p.placeholder_code LIKE 'DPI%'
ORDER BY tc.type, ptc.product_id, p.placeholder_code;
