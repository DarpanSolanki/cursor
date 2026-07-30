-- LOCAL / QA masterdata: RSCH_LOAN_PREPAYMENT billed-interest settlement (TDPQA-72)
-- RSCH INT_AMT credits INT_REC (AIR). After child FC force-bill, parent inherited interest must
-- settle on BILLED_INTEREST via BLD_INT_AMT (same shape as RSCH_DEATH_FORECLOSURE).
-- Idempotent NOT EXISTS guards. After apply: flush Redis TAR cache or restart accounting.
\set ON_ERROR_STOP on
BEGIN;

INSERT INTO mfi_accounting.transaction_accounting_rule (
  transaction_catalogue_id, sequence_number, entry_type, entry_lookup_code,
  reference_code, reference_description, display_flag, source_amount,
  product_resolution_placeholder, debit_account_placeholder, debit_narration,
  debit_part_info_1, debit_part_info_2, debit_part_info_3,
  credit_account_placeholder, credit_narration,
  credit_part_info_1, credit_part_info_2, credit_part_info_3,
  fallback_credit_placeholder, fallback_credit_narration,
  fallback_credit_part_info_1, fallback_credit_part_info_2, fallback_credit_part_info_3,
  condition_type, condition_expression, entry_sub_type,
  created_on, created_by, approved_on, approved_by, updated_on, updated_by, is_deleted
)
SELECT tc.id, 24, 'TRANSFER', NULL, 'BLD_INT_AMT', 'BILLED INTEREST', true, 'BLD_INT_AMT',
  'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL,
  'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
    WHERE x.transaction_catalogue_id = tc.id
      AND x.reference_code = 'BLD_INT_AMT'
      AND COALESCE(x.is_deleted, false) = false
  )
UNION ALL
SELECT tc.id, 25, 'TRANSFER', NULL, 'ADV_BLD_INT_AMT', 'ADVANCE BILLED INTEREST', true, 'ADV_BLD_INT_AMT',
  'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL,
  'BILLED_INTEREST', 'ADVANCE BILLED INTEREST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
    WHERE x.transaction_catalogue_id = tc.id
      AND x.reference_code = 'ADV_BLD_INT_AMT'
      AND COALESCE(x.is_deleted, false) = false
  );

COMMIT;

\echo '=== RSCH_LOAN_PREPAYMENT BLD_INT_AMT / ADV_BLD_INT_AMT ==='
SELECT tc.type, tar.sequence_number, tar.reference_code,
       tar.debit_account_placeholder, tar.credit_account_placeholder
FROM mfi_accounting.transaction_accounting_rule tar
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tar.transaction_catalogue_id
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT'
  AND tar.reference_code IN ('BLD_INT_AMT', 'ADV_BLD_INT_AMT')
  AND COALESCE(tar.is_deleted, false) = false
ORDER BY tar.sequence_number;
