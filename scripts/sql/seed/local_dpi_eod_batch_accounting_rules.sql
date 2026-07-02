-- DPI EOD batch — transaction catalogue + accounting rules (local dev)
--
-- Covers the four sub_types posted by dpiAccrualBooking / dpiBilling:
--   INTEREST  DPI_NORMAL_ACCRUAL        — regular accrual booking
--   INTEREST  DPI_NPA_ACCRUAL           — NPA accrual booking
--   BILLING   DPI_NORMAL_BILLING        — regular billing
--   INTEREST  DPI_NPA_ACCRUAL_BOOKING  — NPA billing leg
--
-- No hardcoded numeric ids — catalogue matched by (type, sub_type); TAR uses DB sequence.
-- Idempotent (NOT EXISTS guards). Safe to re-run.
--
-- Run (Yugabyte local default):
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
--     -f scripts/sql/seed/local_dpi_eod_batch_accounting_rules.sql
--
-- After this, link catalogues + placeholders to your product/scheme — see:
--   scripts/dpic/sql/setup_local_dev_product_6367.sql  (product 6367 example)
--   scripts/dpic/sql/seed_accounting_rules_from_product_doc.sql  (full DPI rule set)

\set ON_ERROR_STOP on

BEGIN;

-- ── 1) transaction_catalogue (sequence id; dedupe on type + sub_type) ─────────

INSERT INTO mfi_accounting.transaction_catalogue (
  type, sub_type, type_name, sub_type_name, description,
  transaction_mode, is_reversible, is_deleted,
  created_on, created_by, updated_on, updated_by, approved_by, approved_on
)
SELECT v.type, v.sub_type, v.type_name, v.sub_type_name, v.description,
       'SYSTEM', false, false,
       NOW(), 'DPI_EOD_SEED', NOW(), 'DPI_EOD_SEED', 'DPI_EOD_SEED', NOW()
FROM (VALUES
  ('INTEREST', 'DPI_NORMAL_ACCRUAL',       'INTEREST', 'DPI NORMAL ACCRUAL',       'DPI NORMAL ACCRUAL'),
  ('INTEREST', 'DPI_NPA_ACCRUAL',          'INTEREST', 'DPI NPA ACCRUAL',          'NPA ACCRUAL'),
  ('INTEREST', 'DPI_NPA_ACCRUAL_BOOKING',  'INTEREST', 'DPI NPA ACCRUAL BOOKING',  'DPI NPA ACCRUAL BOOKING'),
  ('BILLING',  'DPI_NORMAL_BILLING',       'BILLING',  'DPI NORMAL BILLING',       'DPI NORMAL BILLING (Due For Interest On Unpaid Installment)')
) AS v(type, sub_type, type_name, sub_type_name, description)
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.transaction_catalogue tc
  WHERE tc.type = v.type
    AND tc.sub_type = v.sub_type
    AND tc.is_deleted = false
);

-- ── 2) transaction_accounting_rule (one TRANSFER leg per catalogue) ───────────

INSERT INTO mfi_accounting.transaction_accounting_rule (
  transaction_catalogue_id, sequence_number, entry_type, entry_lookup_code,
  reference_code, reference_description, display_flag, source_amount,
  product_resolution_placeholder, debit_account_placeholder, debit_narration,
  debit_part_info_1, debit_part_info_2, debit_part_info_3,
  credit_account_placeholder, credit_narration,
  credit_part_info_1, credit_part_info_2, credit_part_info_3,
  fallback_credit_placeholder, fallback_credit_narration,
  fallback_credit_part_info_1, fallback_credit_part_info_2, fallback_credit_part_info_3,
  condition_type, condition_expression,
  created_on, created_by, approved_on, approved_by, updated_on, updated_by,
  is_deleted, entry_sub_type
)
SELECT tc.id, 1, 'TRANSFER', NULL,
  'DPI_ACCR_INT_AMT', 'DPI Accrual Interest Receivable', 't', 'DPI_ACCR_INT_AMT',
  'LOAN_ACCOUNT', 'DPI_ACC_NOT_DUE', 'DPI AIR',
  NULL, NULL, NULL,
  'DPI_INT_INC', 'DPI INTEREST INCOME',
  NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL,
  'NA', NULL,
  NOW(), 'DPI_EOD_SEED', NOW(), 'DPI_EOD_SEED', NOW(), 'DPI_EOD_SEED',
  false, NULL
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'INTEREST' AND tc.sub_type = 'DPI_NORMAL_ACCRUAL' AND tc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.transaction_accounting_rule ex
    WHERE ex.transaction_catalogue_id = tc.id
      AND ex.reference_code = 'DPI_ACCR_INT_AMT'
      AND ex.debit_account_placeholder = 'DPI_ACC_NOT_DUE'
      AND ex.credit_account_placeholder = 'DPI_INT_INC'
      AND ex.is_deleted = false
  );

INSERT INTO mfi_accounting.transaction_accounting_rule (
  transaction_catalogue_id, sequence_number, entry_type, entry_lookup_code,
  reference_code, reference_description, display_flag, source_amount,
  product_resolution_placeholder, debit_account_placeholder, debit_narration,
  debit_part_info_1, debit_part_info_2, debit_part_info_3,
  credit_account_placeholder, credit_narration,
  credit_part_info_1, credit_part_info_2, credit_part_info_3,
  fallback_credit_placeholder, fallback_credit_narration,
  fallback_credit_part_info_1, fallback_credit_part_info_2, fallback_credit_part_info_3,
  condition_type, condition_expression,
  created_on, created_by, approved_on, approved_by, updated_on, updated_by,
  is_deleted, entry_sub_type
)
SELECT tc.id, 1, 'TRANSFER', NULL,
  'DPI_ACCR_INT_AMT_NPA', 'DPI Accrual Interest Receivable NPA', 't', 'DPI_ACCR_INT_AMT_NPA',
  'LOAN_ACCOUNT', 'DPI_ACC_NOT_DUE', 'DPI AIR',
  NULL, NULL, NULL,
  'DPI_INT_SUSP_AIR', 'DPI Interest Suspense AIR',
  NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL,
  'NA', NULL,
  NOW(), 'DPI_EOD_SEED', NOW(), 'DPI_EOD_SEED', NOW(), 'DPI_EOD_SEED',
  false, NULL
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'INTEREST' AND tc.sub_type = 'DPI_NPA_ACCRUAL' AND tc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.transaction_accounting_rule ex
    WHERE ex.transaction_catalogue_id = tc.id
      AND ex.reference_code = 'DPI_ACCR_INT_AMT_NPA'
      AND ex.debit_account_placeholder = 'DPI_ACC_NOT_DUE'
      AND ex.credit_account_placeholder = 'DPI_INT_SUSP_AIR'
      AND ex.is_deleted = false
  );

INSERT INTO mfi_accounting.transaction_accounting_rule (
  transaction_catalogue_id, sequence_number, entry_type, entry_lookup_code,
  reference_code, reference_description, display_flag, source_amount,
  product_resolution_placeholder, debit_account_placeholder, debit_narration,
  debit_part_info_1, debit_part_info_2, debit_part_info_3,
  credit_account_placeholder, credit_narration,
  credit_part_info_1, credit_part_info_2, credit_part_info_3,
  fallback_credit_placeholder, fallback_credit_narration,
  fallback_credit_part_info_1, fallback_credit_part_info_2, fallback_credit_part_info_3,
  condition_type, condition_expression,
  created_on, created_by, approved_on, approved_by, updated_on, updated_by,
  is_deleted, entry_sub_type
)
SELECT tc.id, 1, 'TRANSFER', NULL,
  'BILLED_DPI_INT_AMT', 'Billed DPI Interest Amount', 't', 'BILLED_DPI_INT_AMT',
  'LOAN_ACCOUNT', 'DPI_BILLED_INTEREST', 'BILLED DPI INTEREST',
  NULL, NULL, NULL,
  'DPI_ACC_NOT_DUE', 'DPI AIR',
  NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL,
  'NA', NULL,
  NOW(), 'DPI_EOD_SEED', NOW(), 'DPI_EOD_SEED', NOW(), 'DPI_EOD_SEED',
  false, NULL
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'BILLING' AND tc.sub_type = 'DPI_NORMAL_BILLING' AND tc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.transaction_accounting_rule ex
    WHERE ex.transaction_catalogue_id = tc.id
      AND ex.reference_code = 'BILLED_DPI_INT_AMT'
      AND ex.debit_account_placeholder = 'DPI_BILLED_INTEREST'
      AND ex.credit_account_placeholder = 'DPI_ACC_NOT_DUE'
      AND ex.is_deleted = false
  );

INSERT INTO mfi_accounting.transaction_accounting_rule (
  transaction_catalogue_id, sequence_number, entry_type, entry_lookup_code,
  reference_code, reference_description, display_flag, source_amount,
  product_resolution_placeholder, debit_account_placeholder, debit_narration,
  debit_part_info_1, debit_part_info_2, debit_part_info_3,
  credit_account_placeholder, credit_narration,
  credit_part_info_1, credit_part_info_2, credit_part_info_3,
  fallback_credit_placeholder, fallback_credit_narration,
  fallback_credit_part_info_1, fallback_credit_part_info_2, fallback_credit_part_info_3,
  condition_type, condition_expression,
  created_on, created_by, approved_on, approved_by, updated_on, updated_by,
  is_deleted, entry_sub_type
)
SELECT tc.id, 1, 'TRANSFER', NULL,
  'DPI_INT_SUSP_AIR_AMT', 'DPI Interest Suspense AIR Amount', 't', 'DPI_INT_SUSP_AIR_AMT',
  'LOAN_ACCOUNT', 'DPI_INT_SUSP_AIR', 'DPI Interest Suspense AIR',
  NULL, NULL, NULL,
  'DPI_INT_SUSP', 'DPI INTEREST SUSPENSE',
  NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL,
  'NA', NULL,
  NOW(), 'DPI_EOD_SEED', NOW(), 'DPI_EOD_SEED', NOW(), 'DPI_EOD_SEED',
  false, NULL
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'INTEREST' AND tc.sub_type = 'DPI_NPA_ACCRUAL_BOOKING' AND tc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.transaction_accounting_rule ex
    WHERE ex.transaction_catalogue_id = tc.id
      AND ex.reference_code = 'DPI_INT_SUSP_AIR_AMT'
      AND ex.debit_account_placeholder = 'DPI_INT_SUSP_AIR'
      AND ex.credit_account_placeholder = 'DPI_INT_SUSP'
      AND ex.is_deleted = false
  );

COMMIT;

\echo '=== DPI EOD batch rules (verify) ==='
SELECT tc.id AS cat_id, tar.id AS tar_id, tc.type, tc.sub_type,
       tar.reference_code,
       tar.debit_account_placeholder AS dr,
       tar.credit_account_placeholder AS cr
FROM mfi_accounting.transaction_catalogue tc
LEFT JOIN mfi_accounting.transaction_accounting_rule tar
  ON tar.transaction_catalogue_id = tc.id AND tar.is_deleted = false
WHERE tc.sub_type IN (
  'DPI_NORMAL_ACCRUAL', 'DPI_NPA_ACCRUAL', 'DPI_NORMAL_BILLING', 'DPI_NPA_ACCRUAL_BOOKING'
)
  AND tc.is_deleted = false
ORDER BY tc.type, tc.sub_type;
