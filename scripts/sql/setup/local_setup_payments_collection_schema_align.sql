-- Local Yugabyte: align mfi_payments.collection* with payments branch entity (CollectionsEntity).
-- Missing columns cause cancelCollections SELECT * to fail (approved_by not in ResultSet).
--
-- Usage:
--   PGPASSWORD=yugabyte psql -h localhost -p 5433 -U yugabyte -d yugabyte \
--     -v ON_ERROR_STOP=1 -f scripts/sql/setup/local_setup_payments_collection_schema_align.sql

\set ON_ERROR_STOP on

ALTER TABLE mfi_payments.collection
  ADD COLUMN IF NOT EXISTS collection_label character varying,
  ADD COLUMN IF NOT EXISTS business_date date,
  ADD COLUMN IF NOT EXISTS value_date date,
  ADD COLUMN IF NOT EXISTS approved_by character varying,
  ADD COLUMN IF NOT EXISTS approved_on timestamp without time zone;

ALTER TABLE mfi_payments.collection_history
  ADD COLUMN IF NOT EXISTS collection_label character varying,
  ADD COLUMN IF NOT EXISTS business_date date,
  ADD COLUMN IF NOT EXISTS value_date date,
  ADD COLUMN IF NOT EXISTS approved_by character varying,
  ADD COLUMN IF NOT EXISTS approved_on timestamp without time zone;

SELECT 'collection' AS tbl, column_name
FROM information_schema.columns
WHERE table_schema = 'mfi_payments' AND table_name = 'collection'
  AND column_name IN ('approved_by', 'approved_on', 'collection_label', 'business_date', 'value_date')
ORDER BY column_name;
