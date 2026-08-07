-- ===========================================================================================
-- GROUP FORECLOSURE - ENVIRONMENT INVENTORY  (TDPQA-72)
-- Reads only. Nothing is changed. Safe to run on any environment at any time.
-- ===========================================================================================
--
-- WHY YOU ARE RUNNING THIS
--   The setup script stops when an account it needs does not exist in that environment. This
--   collects everything about how that environment is actually configured, so the accounts can
--   be chosen from what is really there instead of guessed - and so the next problem, if there
--   is one, is already answered without asking you to run something again.
--
-- HOW TO RUN
--   psql -h <host> -p <port> -U <user> -d <database> -v ON_ERROR_STOP=1 \
--        -f qa_collect_tdpqa72_placeholder_inventory.sql
--
--   It writes tdpqa72_inventory.csv into the directory you run it from.
--   Rename it per environment before sending, e.g. tdpqa72_inventory_uat.csv.
--   The database name is inside the file as well, so a mix-up is recoverable.
--
--   Best run BEFORE the setup script, so the original rules are captured. If it is run after,
--   the "rule" rows are the replacement set - say which when you send the file.
--
-- WHAT IS IN THE FILE   (column "section" tells you which is which)
--   env              database, server version, when it was taken
--   schema           columns each table actually has here - catches schema drift
--   catalogue        every transaction catalogue, including deleted ones
--   product          the products, with code and status
--   loan_product     loan type / category, and whether prepayment is allowed
--   ptc              which product is wired to which catalogue, including deleted links
--   rule             every accounting rule, including the fallback account and deleted ones
--   product_map      every placeholder -> account mapping, including deleted ones
--   env_placeholder  each placeholder in use here and the account behind it, with a count
--   iad              the chart of accounts
--   dangling_map     mappings pointing at an account that is missing or deleted
--   unresolved       placeholders an active rule needs but no mapping provides
--
--   Deleted rows are included on purpose. A mapping that exists but is switched off is fixed by
--   switching it back on, not by creating anything - and that difference is invisible otherwise.
--
-- Configuration only. No customer, loan or payment data.
-- ===========================================================================================

\set ON_ERROR_STOP on

\o tdpqa72_inventory.csv

COPY (

SELECT * FROM (

  SELECT 1 AS ord, 'env' AS section,
         current_database()::text AS c1, version()::text AS c2,
         current_user::text AS c3, now()::text AS c4,
         NULL::text AS c5, NULL::text AS c6, NULL::text AS c7, NULL::text AS c8

  UNION ALL
  SELECT 2, 'schema', c.table_name, c.column_name, c.data_type,
         c.is_nullable, NULL, NULL, NULL, NULL
  FROM information_schema.columns c
  WHERE c.table_schema='mfi_accounting'
    AND c.table_name IN ('transaction_catalogue','transaction_accounting_rule',
                         'product__transaction_catalogue',
                         'product_transaction_catalogue__placeholder__iad',
                         'internal_account_definition','product','loan_product')

  UNION ALL
  SELECT 3, 'catalogue', tc.id::text, tc.type, tc.sub_type, tc.transaction_mode,
         COALESCE(tc.is_deleted,false)::text, NULL, NULL, NULL
  FROM mfi_accounting.transaction_catalogue tc

  UNION ALL
  SELECT 4, 'product', p.id::text, p.code, p.name, p.type, p.sub_type, p.status,
         COALESCE(p.is_deleted,false)::text, NULL
  FROM mfi_accounting.product p

  UNION ALL
  SELECT 5, 'loan_product', lp.product_id::text, lp.loan_type, lp.loan_category,
         COALESCE(lp.prepayment_allowed,false)::text,
         COALESCE(lp.part_prepayment_allowed,false)::text,
         COALESCE(lp.loan_restructuring_allowed,false)::text, NULL, NULL
  FROM mfi_accounting.loan_product lp

  UNION ALL
  SELECT 6, 'ptc', ptc.id::text, ptc.product_id::text, tc.type, tc.sub_type,
         COALESCE(ptc.is_deleted,false)::text, NULL, NULL, NULL
  FROM mfi_accounting.product__transaction_catalogue ptc
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id

  UNION ALL
  SELECT 7, 'rule', tc.type, tc.sub_type, tar.sequence_number::text, tar.reference_code,
         tar.debit_account_placeholder, tar.credit_account_placeholder,
         tar.fallback_credit_placeholder,
         tar.source_amount || '|deleted=' || COALESCE(tar.is_deleted,false)::text
  FROM mfi_accounting.transaction_accounting_rule tar
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tar.transaction_catalogue_id

  UNION ALL
  SELECT 8, 'product_map', sp.product_id::text, tc.type, tc.sub_type,
         m.placeholder_code, iad.code, iad.name,
         COALESCE(m.is_deleted,false)::text, COALESCE(iad.is_deleted,false)::text
  FROM mfi_accounting.product_transaction_catalogue__placeholder__iad m
  JOIN mfi_accounting.product__transaction_catalogue sp ON sp.id = m.product_transaction_catalogue_id
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = sp.transaction_catalogue_id
  LEFT JOIN mfi_accounting.internal_account_definition iad ON iad.id = m.internal_account_definition_id

  UNION ALL
  SELECT 9, 'env_placeholder', m.placeholder_code, iad.code, iad.name,
         iad.general_ledger_code, count(*)::text,
         COALESCE(m.is_deleted,false)::text, NULL, NULL
  FROM mfi_accounting.product_transaction_catalogue__placeholder__iad m
  LEFT JOIN mfi_accounting.internal_account_definition iad ON iad.id = m.internal_account_definition_id
  GROUP BY m.placeholder_code, iad.code, iad.name, iad.general_ledger_code, COALESCE(m.is_deleted,false)

  UNION ALL
  SELECT 10, 'iad', iad.id::text, iad.code, iad.name, iad.general_ledger_code,
         iad.offset_account_type, COALESCE(iad.direct_posting_allowed,false)::text,
         COALESCE(iad.is_deleted,false)::text, NULL
  FROM mfi_accounting.internal_account_definition iad

  UNION ALL
  SELECT 11, 'dangling_map', sp.product_id::text, m.placeholder_code,
         m.internal_account_definition_id::text,
         CASE WHEN iad.id IS NULL THEN 'account row missing' ELSE 'account deleted' END,
         NULL, NULL, NULL, NULL
  FROM mfi_accounting.product_transaction_catalogue__placeholder__iad m
  JOIN mfi_accounting.product__transaction_catalogue sp ON sp.id = m.product_transaction_catalogue_id
  LEFT JOIN mfi_accounting.internal_account_definition iad ON iad.id = m.internal_account_definition_id
  WHERE COALESCE(m.is_deleted,false)=false
    AND (iad.id IS NULL OR COALESCE(iad.is_deleted,false)=true)

  UNION ALL
  SELECT 12, 'unresolved', ptc.product_id::text, tc.type, tc.sub_type, ph.code,
         CASE WHEN EXISTS (
           SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad d
           WHERE d.product_transaction_catalogue_id = ptc.id AND d.placeholder_code = ph.code)
         THEN 'exists but deleted' ELSE 'no mapping at all' END,
         CASE WHEN EXISTS (
           SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad a
           WHERE a.placeholder_code = ph.code AND COALESCE(a.is_deleted,false)=false)
         THEN 'used elsewhere in this env' ELSE 'unknown to this env' END,
         NULL, NULL
  FROM mfi_accounting.product__transaction_catalogue ptc
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
  CROSS JOIN LATERAL (
    SELECT DISTINCT unnest(ARRAY[tar.debit_account_placeholder, tar.credit_account_placeholder,
                                 tar.fallback_credit_placeholder]) AS code
    FROM mfi_accounting.transaction_accounting_rule tar
    WHERE tar.transaction_catalogue_id = tc.id AND COALESCE(tar.is_deleted,false)=false) ph
  WHERE COALESCE(tc.is_deleted,false)=false AND COALESCE(ptc.is_deleted,false)=false
    AND ph.code IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad e
      WHERE e.product_transaction_catalogue_id = ptc.id AND e.placeholder_code = ph.code
        AND COALESCE(e.is_deleted,false)=false)

) x ORDER BY ord, c1, c2, c3, c4, c5

) TO STDOUT WITH CSV HEADER;

\o

\echo 'written: tdpqa72_inventory.csv  (rename per environment before sending)'
