-- Local Yugabyte: align loan_product_asset_criteria with mfi_integration branch code.
-- Code expects single column liquidation_order; older local dumps have liquidation_order_1..5 only.
--
-- Usage:
--   PGPASSWORD=yugabyte psql -h localhost -p 5433 -U yugabyte -d yugabyte \
--     -v ON_ERROR_STOP=1 -f scripts/sql/setup/local_setup_loan_product_asset_criteria_liquidation_order.sql

\set ON_ERROR_STOP on

ALTER TABLE mfi_accounting.loan_product_asset_criteria
  ADD COLUMN IF NOT EXISTS liquidation_order character varying;

UPDATE mfi_accounting.loan_product_asset_criteria
SET liquidation_order = COALESCE(
  NULLIF(TRIM(liquidation_order), ''),
  NULLIF(TRIM(liquidation_order_1), ''),
  'LIQ_COMP'
)
WHERE liquidation_order IS NULL OR TRIM(liquidation_order) = '';

SELECT COUNT(*) AS rows_missing_liquidation_order
FROM mfi_accounting.loan_product_asset_criteria
WHERE is_deleted = false AND (liquidation_order IS NULL OR TRIM(liquidation_order) = '');

-- Local DB dumps migrated sequence_3 to APP_LOGIC_DPI; mfi_integration AssetsConstants
-- APPROPPRIATION_COMPONENT_TYPE_MAP has no DPI entry → NPE in PrepaymentApproppriationProcessor.
-- Local-only: restore 4-slot INT/PRIN/PNLT/FEES ordering for foreclosure sim (not prod).
UPDATE mfi_accounting.loan_product_asset_criteria
SET sequence_3 = 'APP_LOGIC_PNLT',
    sequence_4 = 'APP_LOGIC_FEES',
    updated_on = NOW(),
    updated_by = 'LOCAL_SETUP'
WHERE is_deleted = false
  AND sequence_3 = 'APP_LOGIC_DPI';
