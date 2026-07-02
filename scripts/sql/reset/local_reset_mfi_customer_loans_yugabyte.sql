-- Local QA only: soft-delete and close all loan accounts for one customer (mfi_accounting).
--
-- Why:
--   - CustomerIDDedupCheckProcessor: findAllByCustomerId() ignores is_deleted; blocks on account.status ACTIVE.
--   - checkDedupeForExternalRefNumber: findLoanByExternalRefNumberAndProductId() ignores is_deleted.
--   So we set account CLOSED + is_deleted, loan_account CLOSED + is_deleted, and void external_ref (64 chars).
--
-- Usage (database name is yugabyte on local Yugabyte; schema mfi_accounting):
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte
--   \i scripts/local_reset_mfi_customer_loans_yugabyte.sql
--   (edit \set line below first)

\set customer_id 10000304

BEGIN;
SET search_path TO mfi_accounting;

UPDATE loan_account la
SET
  is_deleted = true,
  loan_status = 'CLOSED',
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset',
  external_ref_number = LEFT(
    'VOID_' || la.account_id::text || '_' || COALESCE(NULLIF(TRIM(la.external_ref_number), ''), 'NA'),
    64
  )
WHERE customer_id = :customer_id;

UPDATE account a
SET
  is_deleted = true,
  status = 'CLOSED',
  closing_date = COALESCE(closing_date, CURRENT_TIMESTAMP),
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset'
FROM loan_account la
WHERE la.account_id = a.id AND la.customer_id = :customer_id;

COMMIT;
