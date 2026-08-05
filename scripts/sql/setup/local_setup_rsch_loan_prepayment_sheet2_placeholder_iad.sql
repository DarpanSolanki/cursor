-- LOCAL / QA masterdata: placeholder -> internal_account_definition maps for the RSCH_LOAN_PREPAYMENT
-- rules introduced by the product sheet (TDPQA-72). Without these the parent posting fails with 134207.
-- Source of truth is the same product's own catalogue that already resolves the placeholder, preferred
-- in this order: LOAN_PREPAYMENT (the child foreclosure catalogue) -> DEATH_FORECLOSURE ->
-- RSCH_DEATH_FORECLOSURE. Child/parent GL codes differ only by the runtime CG prefix, not by IAD, so
-- copying the child's mapping is correct for the parent.
-- Idempotent: inserts only what is missing.
\set ON_ERROR_STOP on
BEGIN;

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT tgt.ptc_id, tgt.ph, src.internal_account_definition_id, false
FROM (
  SELECT ptc.id AS ptc_id, ptc.product_id, need.ph
  FROM mfi_accounting.product__transaction_catalogue ptc
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
  CROSS JOIN (
    SELECT DISTINCT unnest(ARRAY[tar.debit_account_placeholder, tar.credit_account_placeholder]) AS ph
    FROM mfi_accounting.transaction_accounting_rule tar
    JOIN mfi_accounting.transaction_catalogue c ON c.id = tar.transaction_catalogue_id
    WHERE c.type = 'RSCH_LOAN_PREPAYMENT' AND c.sub_type = 'CASH'
      AND COALESCE(tar.is_deleted, false) = false
  ) need
  WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
    AND COALESCE(ptc.is_deleted, false) = false
    AND NOT EXISTS (
      SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad m
      WHERE m.product_transaction_catalogue_id = ptc.id
        AND m.placeholder_code = need.ph
        AND COALESCE(m.is_deleted, false) = false)
) tgt
JOIN LATERAL (
  SELECT m.internal_account_definition_id
  FROM mfi_accounting.product__transaction_catalogue sptc
  JOIN mfi_accounting.transaction_catalogue stc ON stc.id = sptc.transaction_catalogue_id
  JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad m
    ON m.product_transaction_catalogue_id = sptc.id
   AND m.placeholder_code = tgt.ph
   AND COALESCE(m.is_deleted, false) = false
  WHERE sptc.product_id = tgt.product_id
    AND COALESCE(sptc.is_deleted, false) = false
    AND stc.type IN ('LOAN_PREPAYMENT', 'DEATH_FORECLOSURE', 'RSCH_DEATH_FORECLOSURE')
  ORDER BY CASE stc.type
             WHEN 'LOAN_PREPAYMENT' THEN 1
             WHEN 'DEATH_FORECLOSURE' THEN 2
             ELSE 3
           END
  LIMIT 1
) src ON true;

COMMIT;

\echo '=== RSCH_LOAN_PREPAYMENT placeholders still unmapped (must be empty for products under test) ==='
SELECT ptc.product_id, need.ph
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
CROSS JOIN (
  SELECT DISTINCT unnest(ARRAY[tar.debit_account_placeholder, tar.credit_account_placeholder]) AS ph
  FROM mfi_accounting.transaction_accounting_rule tar
  JOIN mfi_accounting.transaction_catalogue c ON c.id = tar.transaction_catalogue_id
  WHERE c.type = 'RSCH_LOAN_PREPAYMENT' AND c.sub_type = 'CASH'
    AND COALESCE(tar.is_deleted, false) = false
) need
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(ptc.is_deleted, false) = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad m
    WHERE m.product_transaction_catalogue_id = ptc.id
      AND m.placeholder_code = need.ph
      AND COALESCE(m.is_deleted, false) = false)
ORDER BY ptc.product_id, need.ph;
