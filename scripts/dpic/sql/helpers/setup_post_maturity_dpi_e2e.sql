-- Truncate schedule to post-maturity shape: last EMI = maturity, no future installments.
-- Marks soft-deleted rows with updated_by = POST_MATURITY_E2E for restore_post_maturity_dpi_e2e.sql.
--
-- Usage:
--   psql ... -v loan_account_id=8060160 -v maturity_date='2026-05-02' -f setup_post_maturity_dpi_e2e.sql

\set ON_ERROR_STOP on

BEGIN;

WITH target AS (
  SELECT lid.id AS installment_id,
         lid.installment_date::date AS installment_day
  FROM mfi_accounting.loan_installment_details lid
  WHERE lid.loan_account_id = :loan_account_id::bigint
    AND lid.is_deleted = false
    AND lid.is_part_prepayment_entry = false
    AND lid.installment_date::date = :'maturity_date'::date
  ORDER BY lid.installment_date
  LIMIT 1
)
SELECT installment_id, installment_day FROM target \gset

\if :{?installment_id}
\else
\echo 'FAIL: no installment on maturity_date' :maturity_date
\quit 1
\endif

UPDATE mfi_accounting.loan_installment_details lid
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'POST_MATURITY_E2E'
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.is_deleted = false
  AND lid.installment_date::date > :'maturity_date'::date;

UPDATE mfi_accounting.loan_account la
SET maturity_date = :'maturity_date'::timestamp,
    updated_on = NOW(),
    updated_by = 'POST_MATURITY_E2E'
WHERE la.account_id = :loan_account_id::bigint;

UPDATE mfi_accounting.loan_due_details ldd
SET paid_amount = 0,
    waived_amount = 0,
    updated_on = NOW(),
    updated_by = 'POST_MATURITY_E2E'
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.component_type IN ('PRIN', 'INT')
  AND ldd.loan_installment_details_id = :installment_id::bigint;

UPDATE mfi_accounting.loan_installment_details lid
SET is_settled = false,
    updated_on = NOW(),
    updated_by = 'POST_MATURITY_E2E'
WHERE lid.id = :installment_id::bigint
  AND lid.loan_account_id = :loan_account_id::bigint
  AND lid.is_deleted = false;

COMMIT;

\echo '=== post-maturity E2E setup ==='
SELECT la.maturity_date::date,
       (SELECT COUNT(*) FROM mfi_accounting.loan_installment_details n
        WHERE n.loan_account_id = la.account_id AND n.is_deleted = false) AS active_emis,
       (SELECT MAX(installment_date)::date FROM mfi_accounting.loan_installment_details n
        WHERE n.loan_account_id = la.account_id AND n.is_deleted = false) AS last_emi
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint;
