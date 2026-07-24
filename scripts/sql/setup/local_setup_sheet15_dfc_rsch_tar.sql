-- LOCAL ONLY (127.0.0.1:5433) — Sheet15 DFC/RSCH transaction_accounting_rule sync from QA4
-- Soft-deletes pre-Sheet15 TAR for catalogues 22/428; inserts QA4 Sheet15 rules.
-- Also ensures IAD 6793 (FEE_WAIVED) + Sheet15 waiver placeholder maps for products 1/44/45.
-- Idempotent soft-delete + NOT EXISTS insert guards.
-- After apply: flush Redis DB5 keys transaction_accounting_rule::*findByTransactionCatalogueId_{22,428} (or restart accounting).
\set ON_ERROR_STOP on
BEGIN;

-- 1) Soft-delete pre-Sheet15 TAR for DFC + RSCH
UPDATE mfi_accounting.transaction_accounting_rule tar
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = '52'
FROM mfi_accounting.transaction_catalogue tc
WHERE tar.transaction_catalogue_id = tc.id
  AND tc.type IN ('DEATH_FORECLOSURE', 'RSCH_DEATH_FORECLOSURE')
  AND COALESCE(tar.is_deleted, false) = false;

-- 2) Insert Sheet15 TAR (catalogue ids resolved by type on local)
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
SELECT tc.id, 1, 'TRANSFER', NULL, 'ADV_BLD_INT_AMT', 'ADVANCE BILLED INTEREST', true, 'ADV_BLD_INT_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'BILLED_INTEREST', 'ADVANCE BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 1     AND x.reference_code = 'ADV_BLD_INT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 2, 'TRANSFER', NULL, 'ADV_UNBLD_PRIN_AMT', 'ADVANCE UNBILLED PRINCIPAL', true, 'ADV_UNBLD_PRIN_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'ADVANCE UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 2     AND x.reference_code = 'ADV_UNBLD_PRIN_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 3, 'TRANSFER', NULL, 'ADV_PINT_AMT', 'ADVANCE PENAL AMOUNT', true, 'ADV_PINT_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'PENAL', 'ADVANCE PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 3     AND x.reference_code = 'ADV_PINT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 4, 'TRANSFER', NULL, 'ADV_CBC_FEE_AMT', 'ADVANCE CBC FEE', true, 'ADV_CBC_FEE_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'CBC_CHARGE', 'ADVANCE CBC FEE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 4     AND x.reference_code = 'ADV_CBC_FEE_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 5, 'TRANSFER', NULL, 'BLD_INT_AMT', 'BILLED INTEREST', true, 'BLD_INT_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 5     AND x.reference_code = 'BLD_INT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 6, 'TRANSFER', NULL, 'BLD_PRIN_AMT', 'BILLED PRINCIPAL', true, 'BLD_PRIN_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 6     AND x.reference_code = 'BLD_PRIN_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 7, 'TRANSFER', NULL, 'UNBLD_PRIN_AMT', 'UNBILLED PRINCIPAL', true, 'UNBLD_PRIN_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 7     AND x.reference_code = 'UNBLD_PRIN_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 8, 'TRANSFER', NULL, 'PINT_AMT', 'PENAL AMOUNT', true, 'PINT_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 8     AND x.reference_code = 'PINT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 9, 'TRANSFER', NULL, 'CBC_FEE_AMT', 'CBC FEE', true, 'CBC_FEE_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'CBC_CHARGE', 'CBC FEE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 9     AND x.reference_code = 'CBC_FEE_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 10, 'TRANSFER', NULL, 'ROUND_UP_AMT', 'ROUND UP AMOUNT', true, 'ROUND_UP_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'ROUND_OFF', 'ROUND UP AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 10     AND x.reference_code = 'ROUND_UP_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 11, 'TRANSFER', NULL, 'EXCESS_INCOME_INT_AMT', 'EXCESS INTEREST INCOME', true, 'EXCESS_INCOME_INT_AMT', 'LOAN_ACCOUNT', 'INT_INC', 'EXCESS INTEREST INCOME', NULL, NULL, NULL, 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 11     AND x.reference_code = 'EXCESS_INCOME_INT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 12, 'TRANSFER', NULL, 'EXCESS_ACCOUNT_INC_AMT', 'EXCESS AMOUNT', true, 'EXCESS_ACCOUNT_INC_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 12     AND x.reference_code = 'EXCESS_ACCOUNT_INC_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 13, 'TRANSFER', NULL, 'BLD_INT_WAIVED_AMT', 'BILLED INTEREST WAIVED', true, 'BLD_INT_WAIVED_AMT', 'LOAN_ACCOUNT', 'BILLED_INT_WAIVE', 'BILLED INTEREST WAIVED', NULL, NULL, NULL, 'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 13     AND x.reference_code = 'BLD_INT_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 14, 'TRANSFER', NULL, 'STD_BLD_PRIN_WAIVED_AMT', 'STD BILLED PRINCIPAL WAIVED', true, 'STD_BLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD BILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 14     AND x.reference_code = 'STD_BLD_PRIN_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 15, 'TRANSFER', NULL, 'NPA_BLD_PRIN_WAIVED_AMT', 'NPA BILLED PRINCIPAL WAIVED', true, 'NPA_BLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA BILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 15     AND x.reference_code = 'NPA_BLD_PRIN_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 16, 'TRANSFER', NULL, 'STD_UNBLD_PRIN_WAIVED_AMT', 'STD UNBILLED PRINCIPAL WAIVED', true, 'STD_UNBLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 16     AND x.reference_code = 'STD_UNBLD_PRIN_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 17, 'TRANSFER', NULL, 'NPA_UNBLD_PRIN_WAIVED_AMT', 'NPA UNBILLED PRINCIPAL WAIVED', true, 'NPA_UNBLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 17     AND x.reference_code = 'NPA_UNBLD_PRIN_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 18, 'TRANSFER', NULL, 'PINT_AMT_WAIVED', 'PENAL AMOUNT WAIVED', true, 'PINT_AMT_WAIVED', 'LOAN_ACCOUNT', 'LOSSES_LPP_WAIVED', 'PENAL AMOUNT WAIVED', NULL, NULL, NULL, 'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 18     AND x.reference_code = 'PINT_AMT_WAIVED'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 19, 'TRANSFER', NULL, 'CBC_FEE_AMT_WAIVED', 'CBC FEE WAIVED', true, 'CBC_FEE_AMT_WAIVED', 'LOAN_ACCOUNT', 'FEE_WAIVED', 'FEES WAIVED', NULL, NULL, NULL, 'CBC_CHARGE', 'CBC FEE WAIVED', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 19     AND x.reference_code = 'CBC_FEE_AMT_WAIVED'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 20, 'TRANSFER', NULL, 'ROUND_DOWN_AMT', 'ROUND DOWN AMOUNT', true, 'ROUND_DOWN_AMT', 'LOAN_ACCOUNT', 'ROUND_OFF', 'ROUND DOWN AMOUNT', NULL, NULL, NULL, 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 20     AND x.reference_code = 'ROUND_DOWN_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 21, 'TRANSFER', NULL, 'EXCESS_PINT_AMT', 'EXCESS PENAL AMOUNT', true, 'EXCESS_PINT_AMT', 'LOAN_ACCOUNT', 'PENAL', 'EXCESS PENAL AMOUNT', NULL, NULL, NULL, 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 21     AND x.reference_code = 'EXCESS_PINT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 22, 'TRANSFER', NULL, 'EXCESS_CBC_FEE_AMT', 'EXCESS CBC FEE', true, 'EXCESS_CBC_FEE_AMT', 'LOAN_ACCOUNT', 'CBC_CHARGE', 'EXCESS CBC FEE', NULL, NULL, NULL, 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 22     AND x.reference_code = 'EXCESS_CBC_FEE_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 1, 'TRANSFER', NULL, 'ADV_BLD_INT_AMT', 'ADVANCE BILLED INTEREST', true, 'ADV_BLD_INT_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'BILLED_INTEREST', 'ADVANCE BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 1     AND x.reference_code = 'ADV_BLD_INT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 2, 'TRANSFER', NULL, 'ADV_UNBLD_PRIN_AMT', 'ADVANCE UNBILLED PRINCIPAL', true, 'ADV_UNBLD_PRIN_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'ADVANCE UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 2     AND x.reference_code = 'ADV_UNBLD_PRIN_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 3, 'TRANSFER', NULL, 'ADV_PINT_AMT', 'ADVANCE PENAL AMOUNT', true, 'ADV_PINT_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'PENAL', 'ADVANCE PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 3     AND x.reference_code = 'ADV_PINT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 4, 'TRANSFER', NULL, 'ADV_CBC_FEE_AMT', 'ADVANCE CBC FEE', true, 'ADV_CBC_FEE_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'CBC_CHARGE', 'ADVANCE CBC FEE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 4     AND x.reference_code = 'ADV_CBC_FEE_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 5, 'TRANSFER', NULL, 'BLD_INT_AMT', 'BILLED INTEREST', true, 'BLD_INT_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 5     AND x.reference_code = 'BLD_INT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 6, 'TRANSFER', NULL, 'BLD_PRIN_AMT', 'BILLED PRINCIPAL', true, 'BLD_PRIN_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 6     AND x.reference_code = 'BLD_PRIN_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 7, 'TRANSFER', NULL, 'UNBLD_PRIN_AMT', 'UNBILLED PRINCIPAL', true, 'UNBLD_PRIN_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 7     AND x.reference_code = 'UNBLD_PRIN_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 8, 'TRANSFER', NULL, 'PINT_AMT', 'PENAL AMOUNT', true, 'PINT_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 8     AND x.reference_code = 'PINT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 9, 'TRANSFER', NULL, 'CBC_FEE_AMT', 'CBC FEE', true, 'CBC_FEE_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'CBC_CHARGE', 'CBC FEE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 9     AND x.reference_code = 'CBC_FEE_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 10, 'TRANSFER', NULL, 'ROUND_UP_AMT', 'ROUND UP AMOUNT', true, 'ROUND_UP_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'ROUND_OFF', 'ROUND UP AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 10     AND x.reference_code = 'ROUND_UP_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 11, 'TRANSFER', NULL, 'EXCESS_INCOME_INT_AMT', 'EXCESS INTEREST INCOME', true, 'EXCESS_INCOME_INT_AMT', 'LOAN_ACCOUNT', 'INT_INC', 'EXCESS INTEREST INCOME', NULL, NULL, NULL, 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 11     AND x.reference_code = 'EXCESS_INCOME_INT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 12, 'TRANSFER', NULL, 'EXCESS_ACCOUNT_INC_AMT', 'EXCESS AMOUNT', true, 'EXCESS_ACCOUNT_INC_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 12     AND x.reference_code = 'EXCESS_ACCOUNT_INC_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 13, 'TRANSFER', NULL, 'BLD_INT_WAIVED_AMT', 'BILLED INTEREST WAIVED', true, 'BLD_INT_WAIVED_AMT', 'LOAN_ACCOUNT', 'BILLED_INT_WAIVE', 'BILLED INTEREST WAIVED', NULL, NULL, NULL, 'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 13     AND x.reference_code = 'BLD_INT_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 14, 'TRANSFER', NULL, 'STD_BLD_PRIN_WAIVED_AMT', 'STD BILLED PRINCIPAL WAIVED', true, 'STD_BLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD BILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 14     AND x.reference_code = 'STD_BLD_PRIN_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 15, 'TRANSFER', NULL, 'NPA_BLD_PRIN_WAIVED_AMT', 'NPA BILLED PRINCIPAL WAIVED', true, 'NPA_BLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA BILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 15     AND x.reference_code = 'NPA_BLD_PRIN_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 16, 'TRANSFER', NULL, 'STD_UNBLD_PRIN_WAIVED_AMT', 'STD UNBILLED PRINCIPAL WAIVED', true, 'STD_UNBLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 16     AND x.reference_code = 'STD_UNBLD_PRIN_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 17, 'TRANSFER', NULL, 'NPA_UNBLD_PRIN_WAIVED_AMT', 'NPA UNBILLED PRINCIPAL WAIVED', true, 'NPA_UNBLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 17     AND x.reference_code = 'NPA_UNBLD_PRIN_WAIVED_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 18, 'TRANSFER', NULL, 'PINT_AMT_WAIVED', 'PENAL AMOUNT WAIVED', true, 'PINT_AMT_WAIVED', 'LOAN_ACCOUNT', 'LOSSES_LPP_WAIVED', 'PENAL AMOUNT WAIVED', NULL, NULL, NULL, 'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 18     AND x.reference_code = 'PINT_AMT_WAIVED'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 19, 'TRANSFER', NULL, 'CBC_FEE_AMT_WAIVED', 'CBC FEE WAIVED', true, 'CBC_FEE_AMT_WAIVED', 'LOAN_ACCOUNT', 'FEE_WAIVED', 'FEES WAIVED', NULL, NULL, NULL, 'CBC_CHARGE', 'CBC FEE WAIVED', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 19     AND x.reference_code = 'CBC_FEE_AMT_WAIVED'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 20, 'TRANSFER', NULL, 'ROUND_DOWN_AMT', 'ROUND DOWN AMOUNT', true, 'ROUND_DOWN_AMT', 'LOAN_ACCOUNT', 'ROUND_OFF', 'ROUND DOWN AMOUNT', NULL, NULL, NULL, 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 20     AND x.reference_code = 'ROUND_DOWN_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 21, 'TRANSFER', NULL, 'EXCESS_PINT_AMT', 'EXCESS PENAL AMOUNT', true, 'EXCESS_PINT_AMT', 'LOAN_ACCOUNT', 'PENAL', 'EXCESS PENAL AMOUNT', NULL, NULL, NULL, 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 21     AND x.reference_code = 'EXCESS_PINT_AMT'     AND COALESCE(x.is_deleted,false)=false)
UNION ALL
SELECT tc.id, 22, 'TRANSFER', NULL, 'EXCESS_CBC_FEE_AMT', 'EXCESS CBC FEE', true, 'EXCESS_CBC_FEE_AMT', 'LOAN_ACCOUNT', 'CBC_CHARGE', 'EXCESS CBC FEE', NULL, NULL, NULL, 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), '52', NOW(), '51', NOW(), '52', false FROM mfi_accounting.transaction_catalogue tc WHERE tc.type = 'RSCH_DEATH_FORECLOSURE' AND NOT EXISTS (  SELECT 1 FROM mfi_accounting.transaction_accounting_rule x   WHERE x.transaction_catalogue_id = tc.id     AND x.sequence_number = 22     AND x.reference_code = 'EXCESS_CBC_FEE_AMT'     AND COALESCE(x.is_deleted,false)=false);

-- 3) Ensure FEE_WAIVED IAD 6793 (from QA4)
INSERT INTO mfi_accounting.internal_account_definition (
  id, name, description, general_ledger_code, offset_account_type,
  direct_posting_allowed, code, created_on, created_by, updated_on, updated_by, is_deleted
)
SELECT 6793, 'CBC Fees waive', 'Fees waived', '2210', 'OFF_ACT_TYP_BOT',
       true, 'IAD2210', NOW(), '51', NOW(), '51', false
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.internal_account_definition WHERE id = 6793
);

-- 4) Sheet15 waiver placeholder → IAD maps for products 1/44/45 (QA4 parity)
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'BILLED_INT_WAIVE', 4593, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 1
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'BILLED_INT_WAIVE'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'FEE_WAIVED', 6793, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 1
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'FEE_WAIVED'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_NPA', 5394, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 1
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_NPA'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_STD', 5393, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 1
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_STD'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'BILLED_INT_WAIVE', 4593, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 44
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'BILLED_INT_WAIVE'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'FEE_WAIVED', 6793, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 44
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'FEE_WAIVED'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_NPA', 4493, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 44
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_NPA'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_STD', 4294, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 44
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_STD'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'BILLED_INT_WAIVE', 4593, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 45
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'BILLED_INT_WAIVE'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'FEE_WAIVED', 6793, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 45
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'FEE_WAIVED'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_NPA', 4493, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 45
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_NPA'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_STD', 4294, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 45
  AND tc.type = 'DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_STD'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'BILLED_INT_WAIVE', 4593, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 1
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'BILLED_INT_WAIVE'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'FEE_WAIVED', 6793, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 1
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'FEE_WAIVED'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_NPA', 5394, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 1
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_NPA'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_STD', 5393, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 1
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_STD'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'BILLED_INT_WAIVE', 4593, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 44
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'BILLED_INT_WAIVE'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'FEE_WAIVED', 6793, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 44
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'FEE_WAIVED'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_NPA', 4493, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 44
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_NPA'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_STD', 4294, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 44
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_STD'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'BILLED_INT_WAIVE', 4593, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 45
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'BILLED_INT_WAIVE'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'FEE_WAIVED', 6793, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 45
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'FEE_WAIVED'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_NPA', 4493, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 45
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_NPA'
      AND COALESCE(x.is_deleted,false)=false
  );
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PRIN_WAIVE_STD', 4294, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = 45
  AND tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND COALESCE(ptc.is_deleted,false)=false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = 'PRIN_WAIVE_STD'
      AND COALESCE(x.is_deleted,false)=false
  );

-- 5) Proof
SELECT 'AFTER' AS phase, tc.type, COUNT(*) AS rule_cnt,
       string_agg(tar.reference_code, ',' ORDER BY tar.sequence_number) AS codes
FROM mfi_accounting.transaction_accounting_rule tar
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tar.transaction_catalogue_id
WHERE tc.type IN ('DEATH_FORECLOSURE','RSCH_DEATH_FORECLOSURE') AND COALESCE(tar.is_deleted,false)=false
GROUP BY tc.type ORDER BY 2;
SELECT tc.type, ptc.product_id, iad.placeholder_code, iad.internal_account_definition_id
FROM mfi_accounting.product_transaction_catalogue__placeholder__iad iad
JOIN mfi_accounting.product__transaction_catalogue ptc ON ptc.id = iad.product_transaction_catalogue_id
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE tc.type IN ('DEATH_FORECLOSURE','RSCH_DEATH_FORECLOSURE')
  AND ptc.product_id IN (1,44,45)
  AND iad.placeholder_code IN ('BILLED_INT_WAIVE','FEE_WAIVED','PRIN_WAIVE_NPA','PRIN_WAIVE_STD')
  AND COALESCE(iad.is_deleted,false)=false
ORDER BY 1,2,3;
COMMIT;

-- 3b) Internal account for FEE_WAIVED IAD 6793 (office 1)
INSERT INTO mfi_accounting.internal_account (
  id, office_id, internal_account_definition_id, code, name, description, balance_limit,
  created_on, created_by, updated_on, updated_by, is_deleted
)
SELECT 6793, 1, 6793, '2210', 'CBC Fees waive', 'Fees waived', 9999999999,
       NOW(), '51', NOW(), '51', false
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.internal_account WHERE internal_account_definition_id=6793 AND office_id=1 AND COALESCE(is_deleted,false)=false
);
