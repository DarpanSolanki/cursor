-- DPI EOD — full local accounting setup (catalogue → product → office)
--
-- Covers four EOD batch catalogues:
--   INTEREST  DPI_NORMAL_ACCRUAL
--   INTEREST  DPI_NPA_ACCRUAL
--   BILLING   DPI_NORMAL_BILLING
--   INTEREST  DPI_NPA_ACCRUAL_BOOKING
--
-- Layers (idempotent):
--   1) transaction_catalogue + transaction_accounting_rule  (\ir batch rules)
--   2) child_general_ledger for parent GLs used by DPI placeholders (JLG/SHG child loans)
--   3) internal_account per office (clone from source_office when missing)
--   4) product__transaction_catalogue + placeholder→IAD + scheme DPI_EOD price_setup
--
-- Child GL note:
--   DPI batch does not set is_child_account explicitly; postTransaction sets it from the
--   LOAN_ACCOUNT actor account (PopulateAndValidateAccountDetailsProcessor). Child member
--   loans then post to CG-prefixed GL codes — child_general_ledger rows must exist for
--   every parent GL bound to DPI placeholders.
--
-- Prerequisites: platform seed already has general_ledger + internal_account_definition
-- for DPI (IAD2203, IAD1101, IAD1102, IAD2207, IAD11911, IAD230000900) — typical QA dump.
--
-- Usage (Yugabyte local):
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
--     -v product_id=6367 \
--     -v product_scheme_id=2655 \
--     -v office_id=1 \
--     -v source_office_id=1 \
--     -f scripts/sql/seed/local_dpi_eod_full_accounting_setup.sql
--
-- Rules-only (no product link): use local_dpi_eod_batch_accounting_rules.sql instead.

\set ON_ERROR_STOP on

-- Defaults for interactive psql (override on command line)
\if :{?product_id}
\else
  \set product_id 6367
\endif
\if :{?product_scheme_id}
\else
  \set product_scheme_id 2655
\endif
\if :{?office_id}
\else
  \set office_id 1
\endif
\if :{?source_office_id}
\else
  \set source_office_id :office_id
\endif

\echo '=== DPI EOD full setup: product=' :product_id ' scheme=' :product_scheme_id ' office=' :office_id

BEGIN;

-- ── 1) Global catalogue + TAR rules ───────────────────────────────────────────
\ir local_dpi_eod_batch_accounting_rules.sql

-- ── 2) Child GLs — mirror parent GLs for all DPI placeholder IADs ─────────────
INSERT INTO mfi_accounting.child_general_ledger (
  parent_gl_id, code, name, description, external_reference_number,
  category, currency, suspense_gl, allowed_transaction_type, status,
  created_on, created_by, updated_on, updated_by, is_deleted, approved_on, approved_by
)
SELECT
  gl.id,
  'CG' || gl.code,
  gl.name,
  gl.description,
  gl.external_reference_number,
  gl.category,
  gl.currency,
  gl.suspense_gl,
  gl.allowed_transaction_type,
  gl.status,
  NOW(), 'DPI_EOD_FULL', NOW(), 'DPI_EOD_FULL', false, NOW(), 'DPI_EOD_FULL'
FROM mfi_accounting.general_ledger gl
WHERE gl.is_deleted = false
  AND gl.code IN (
    SELECT DISTINCT iad.general_ledger_code
    FROM (VALUES
      ('IAD11911'), ('IAD2203'), ('IAD1101'), ('IAD1102'), ('IAD2207'), ('IAD230000900')
    ) AS v(iad_code)
    JOIN mfi_accounting.internal_account_definition iad
      ON iad.code = v.iad_code AND iad.is_deleted = false
  )
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.child_general_ledger cgl
    WHERE cgl.parent_gl_id = gl.id AND cgl.is_deleted = false
  );

-- ── 3) Office internal_account instances (clone from source office) ───────────
INSERT INTO mfi_accounting.internal_account (
  office_id, internal_account_definition_id, code, name, description,
  balance_limit, created_on, created_by, updated_on, updated_by, is_deleted
)
SELECT :office_id, src.internal_account_definition_id,
       src.code, src.name, src.description,
       src.balance_limit, NOW(), 'DPI_EOD_FULL', NOW(), 'DPI_EOD_FULL', false
FROM mfi_accounting.internal_account src
JOIN mfi_accounting.internal_account_definition iad
  ON iad.id = src.internal_account_definition_id AND iad.is_deleted = false
WHERE src.office_id = :source_office_id
  AND src.is_deleted = false
  AND iad.code IN ('IAD11911','IAD2203','IAD1101','IAD1102','IAD2207','IAD230000900')
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.internal_account tgt
    WHERE tgt.office_id = :office_id
      AND tgt.internal_account_definition_id = src.internal_account_definition_id
      AND tgt.is_deleted = false
  );

-- ── 4) Link catalogues to product (resolve id by type + sub_type) ─────────────
INSERT INTO mfi_accounting.product__transaction_catalogue
    (product_id, transaction_catalogue_id, created_on, created_by, updated_on, updated_by, is_deleted)
SELECT :product_id, tc.id, NOW(), 'DPI_EOD_FULL', NOW(), 'DPI_EOD_FULL', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.is_deleted = false
  AND (tc.type, tc.sub_type) IN (
    ('INTEREST', 'DPI_NORMAL_ACCRUAL'),
    ('INTEREST', 'DPI_NPA_ACCRUAL'),
    ('BILLING',  'DPI_NORMAL_BILLING'),
    ('INTEREST', 'DPI_NPA_ACCRUAL_BOOKING')
  )
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product__transaction_catalogue x
    WHERE x.product_id = :product_id
      AND x.transaction_catalogue_id = tc.id
      AND x.is_deleted = false
  );

-- ── 5) Placeholder → IAD per catalogue (resolve IAD by code, not numeric id) ─
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
    (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, m.placeholder_code, iad.id, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc
  ON tc.id = ptc.transaction_catalogue_id AND tc.is_deleted = false
JOIN (VALUES
  ('INTEREST', 'DPI_NORMAL_ACCRUAL',       'LOAN_ACCOUNT',         'IAD11911'),
  ('INTEREST', 'DPI_NORMAL_ACCRUAL',       'DPI_ACC_NOT_DUE',      'IAD2203'),
  ('INTEREST', 'DPI_NORMAL_ACCRUAL',       'DPI_INT_INC',          'IAD1101'),
  ('INTEREST', 'DPI_NPA_ACCRUAL',          'LOAN_ACCOUNT',         'IAD11911'),
  ('INTEREST', 'DPI_NPA_ACCRUAL',          'DPI_ACC_NOT_DUE',      'IAD2203'),
  ('INTEREST', 'DPI_NPA_ACCRUAL',          'DPI_INT_SUSP_AIR',     'IAD2207'),
  ('INTEREST', 'DPI_NPA_ACCRUAL_BOOKING',  'LOAN_ACCOUNT',         'IAD11911'),
  ('INTEREST', 'DPI_NPA_ACCRUAL_BOOKING',  'DPI_INT_SUSP_AIR',     'IAD2207'),
  ('INTEREST', 'DPI_NPA_ACCRUAL_BOOKING',  'DPI_INT_SUSP',         'IAD1102'),
  ('BILLING',  'DPI_NORMAL_BILLING',       'LOAN_ACCOUNT',         'IAD11911'),
  ('BILLING',  'DPI_NORMAL_BILLING',       'DPI_ACC_NOT_DUE',      'IAD2203'),
  ('BILLING',  'DPI_NORMAL_BILLING',       'DPI_BILLED_INTEREST',  'IAD230000900')
) AS m(cat_type, cat_sub_type, placeholder_code, iad_code)
  ON tc.type = m.cat_type AND tc.sub_type = m.cat_sub_type
JOIN mfi_accounting.internal_account_definition iad
  ON iad.code = m.iad_code AND iad.is_deleted = false
WHERE ptc.product_id = :product_id
  AND ptc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = m.placeholder_code
      AND x.is_deleted = false
  );

-- ── 6) Scheme DPI_EOD — TAR rules + catalogue price_setup ─────────────────────
INSERT INTO mfi_accounting.product_scheme__transaction_accounting_rule__price_setup
    (product_scheme_id, transaction_accounting_rule_id, price_setup_code, is_deleted, updated_on, updated_by)
SELECT :product_scheme_id, tar.id, 'DPI_EOD', false, NOW(), 'DPI_EOD_FULL'
FROM mfi_accounting.transaction_accounting_rule tar
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tar.transaction_catalogue_id AND tc.is_deleted = false
WHERE (tc.type, tc.sub_type) IN (
    ('INTEREST', 'DPI_NORMAL_ACCRUAL'),
    ('INTEREST', 'DPI_NPA_ACCRUAL'),
    ('BILLING',  'DPI_NORMAL_BILLING'),
    ('INTEREST', 'DPI_NPA_ACCRUAL_BOOKING')
  )
  AND tar.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_scheme__transaction_accounting_rule__price_setup x
    WHERE x.product_scheme_id = :product_scheme_id
      AND x.transaction_accounting_rule_id = tar.id
      AND x.is_deleted = false
  );

INSERT INTO mfi_accounting.product_scheme__transaction_catalogue__price_setup
    (product_scheme_id, transaction_catalogue_id, price_setup_code, is_deleted, updated_on, updated_by)
SELECT :product_scheme_id, tc.id, 'DPI_EOD', false, NOW(), 'DPI_EOD_FULL'
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.is_deleted = false
  AND (tc.type, tc.sub_type) IN (
    ('INTEREST', 'DPI_NORMAL_ACCRUAL'),
    ('INTEREST', 'DPI_NPA_ACCRUAL'),
    ('BILLING',  'DPI_NORMAL_BILLING'),
    ('INTEREST', 'DPI_NPA_ACCRUAL_BOOKING')
  )
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_scheme__transaction_catalogue__price_setup x
    WHERE x.product_scheme_id = :product_scheme_id
      AND x.transaction_catalogue_id = tc.id
      AND x.price_setup_code = 'DPI_EOD'
      AND x.is_deleted = false
  );

COMMIT;

\echo '=== DPI EOD full setup — verify ==='

\echo '--- catalogues + TAR ---'
SELECT tc.id AS cat_id, tc.type, tc.sub_type,
       tar.reference_code, tar.debit_account_placeholder AS dr, tar.credit_account_placeholder AS cr
FROM mfi_accounting.transaction_catalogue tc
LEFT JOIN mfi_accounting.transaction_accounting_rule tar
  ON tar.transaction_catalogue_id = tc.id AND tar.is_deleted = false
WHERE (tc.type, tc.sub_type) IN (
  ('INTEREST','DPI_NORMAL_ACCRUAL'), ('INTEREST','DPI_NPA_ACCRUAL'),
  ('BILLING','DPI_NORMAL_BILLING'), ('INTEREST','DPI_NPA_ACCRUAL_BOOKING')
) AND tc.is_deleted = false
ORDER BY tc.type, tc.sub_type;

\echo '--- child GLs (parent → child) ---'
SELECT gl.code AS parent_gl, cgl.code AS child_gl
FROM mfi_accounting.general_ledger gl
JOIN mfi_accounting.internal_account_definition iad ON iad.general_ledger_code = gl.code AND iad.is_deleted = false
LEFT JOIN mfi_accounting.child_general_ledger cgl ON cgl.parent_gl_id = gl.id AND cgl.is_deleted = false
WHERE iad.code IN ('IAD11911','IAD2203','IAD1101','IAD1102','IAD2207','IAD230000900')
  AND gl.is_deleted = false
ORDER BY gl.code;

\echo '--- product placeholder IAD (product_id=' :product_id ') ---'
SELECT tc.sub_type, p.placeholder_code, iad.code AS iad_code, iad.general_ledger_code AS gl_code
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad p
  ON p.product_transaction_catalogue_id = ptc.id AND p.is_deleted = false
JOIN mfi_accounting.internal_account_definition iad ON iad.id = p.internal_account_definition_id
WHERE ptc.product_id = :product_id AND ptc.is_deleted = false
  AND tc.sub_type LIKE 'DPI_%'
ORDER BY tc.sub_type, p.placeholder_code;

\echo '--- office internal accounts (office_id=' :office_id ') ---'
SELECT ia.code, iad.code AS iad_code
FROM mfi_accounting.internal_account ia
JOIN mfi_accounting.internal_account_definition iad ON iad.id = ia.internal_account_definition_id
WHERE ia.office_id = :office_id
  AND iad.code IN ('IAD11911','IAD2203','IAD1101','IAD1102','IAD2207','IAD230000900')
  AND ia.is_deleted = false
ORDER BY iad.code;

\echo '--- scheme DPI_EOD (scheme_id=' :product_scheme_id ') ---'
SELECT COUNT(*) AS tar_price_setup_rows
FROM mfi_accounting.product_scheme__transaction_accounting_rule__price_setup ps
JOIN mfi_accounting.transaction_accounting_rule tar ON tar.id = ps.transaction_accounting_rule_id
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tar.transaction_catalogue_id
WHERE ps.product_scheme_id = :product_scheme_id AND ps.price_setup_code = 'DPI_EOD' AND ps.is_deleted = false
  AND tc.sub_type LIKE 'DPI_%';
