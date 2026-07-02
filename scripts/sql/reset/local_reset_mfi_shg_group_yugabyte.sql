-- Local QA: reset all loan accounts for an SHG/JLG parent + member customers in one transaction.
-- DB: yugabyte, schema: mfi_accounting (see local_reset_mfi_customer_loans_yugabyte.sql).
--
-- loan_account PK is account_id (JOINED inheritance); do not use la.id.
--
-- Parent: loan_details.customer_id | Members: member_details[].customer_id
-- psql -h localhost -p 5433 -U yugabyte -d yugabyte -f scripts/local_reset_mfi_shg_group_yugabyte.sql

BEGIN;
SET search_path TO mfi_accounting;

WITH target_customers AS (
  SELECT unnest(ARRAY[
    913078::bigint,
    493047::bigint,
    493147::bigint
  ]) AS customer_id
)
UPDATE loan_account la
SET
  is_deleted = true,
  loan_status = 'CLOSED',
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset_shg',
  external_ref_number = LEFT(
    'VOID_' || la.account_id::text || '_' || COALESCE(NULLIF(TRIM(la.external_ref_number), ''), 'NA'),
    64
  )
FROM target_customers t
WHERE la.customer_id = t.customer_id;

WITH target_customers AS (
  SELECT unnest(ARRAY[
    913078::bigint,
    493047::bigint,
    493147::bigint
  ]) AS customer_id
)
UPDATE account a
SET
  is_deleted = true,
  status = 'CLOSED',
  closing_date = COALESCE(closing_date, CURRENT_TIMESTAMP),
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset_shg'
FROM loan_account la
INNER JOIN target_customers t ON t.customer_id = la.customer_id
WHERE la.account_id = a.id;

COMMIT;
