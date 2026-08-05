-- LOCAL / QA masterdata: RSCH_LOAN_PREPAYMENT accounting rules per product sheet (TDPQA-72).
-- Parent RSCH now mirrors the child LOAN_PREPAYMENT shape: DUE_TO_FC_B funds TRMN_SUSP once
-- (TRMN_SUSP_AMT), then every settlement leg debits TRMN_SUSP.
-- Sheet display names map to the placeholder codes that exist (same substitutions Sheet15 made
-- for DEATH_FORECLOSURE): TRMN_SUSP_ACCT->TRMN_SUSP, CBC_FEE->CBC_CHARGE, PENAL_AMOUNT->PENAL,
-- {STD,NPA}_{BILLED,UNBILLED}_PRIN_WAIVE->PRIN_WAIVE_{STD,NPA}, FEES_WAIVED->FEE_WAIVED,
-- PINT_AMT_WAIVED(placeholder)->LOSSES_LPP_WAIVED.
-- Charge/GST rows are not on the sheet's rule tab but are on its parent GL tab; they keep their
-- existing credit legs and only move their debit from DUE_TO_FC_B to TRMN_SUSP.
-- Idempotent: soft-delete active rows for this catalogue, then NOT EXISTS insert.
-- After apply: flush Redis DB5 transaction_accounting_rule::*findByTransactionCatalogueId_<id> or restart accounting.
\set ON_ERROR_STOP on
BEGIN;

UPDATE mfi_accounting.transaction_accounting_rule tar
SET is_deleted = true, updated_on = NOW(), updated_by = '52'
WHERE tar.transaction_catalogue_id IN (
    SELECT tc.id FROM mfi_accounting.transaction_catalogue tc
    WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
      AND COALESCE(tc.is_deleted, false) = false)
  AND COALESCE(tar.is_deleted, false) = false;

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
SELECT tc.id, 1, 'TRANSFER', NULL, 'ADV_BLD_INT_AMT', 'ADVANCE BILLED INTEREST', true, 'ADV_BLD_INT_AMT',
  'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL,
  'BILLED_INTEREST', 'ADVANCE BILLED INTEREST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'ADV_BLD_INT_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 2, 'TRANSFER', NULL, 'ADV_UNBLD_PRIN_AMT', 'ADVANCE UNBILLED PRINCIPAL', true, 'ADV_UNBLD_PRIN_AMT',
  'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL,
  'LOAN_ACCOUNT', 'ADVANCE UNBILLED PRINCIPAL', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'ADV_UNBLD_PRIN_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 3, 'TRANSFER', NULL, 'ADV_PINT_AMT', 'ADVANCE PENAL AMOUNT', true, 'ADV_PINT_AMT',
  'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL,
  'PENAL', 'ADVANCE PENAL AMOUNT', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'ADV_PINT_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 4, 'TRANSFER', NULL, 'ADV_CBC_FEE_AMT', 'ADVANCE CBC FEE', true, 'ADV_CBC_FEE_AMT',
  'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL,
  'CBC_CHARGE', 'ADVANCE CBC FEE', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'ADV_CBC_FEE_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 5, 'TRANSFER', NULL, 'ADV_BILLED_DPI_INT_AMT', 'Billed DPI Interest Amount', true, 'ADV_BILLED_DPI_INT_AMT',
  'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL,
  'DPI_BILLED_INTEREST', 'DPI BILLED INTEREST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'ADV_BILLED_DPI_INT_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 6, 'TRANSFER', NULL, 'TRMN_SUSP_AMT', 'TERMINATION SUSPENSE ACCOUNT', true, 'TRMN_SUSP_AMT',
  'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL,
  'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'TRMN_SUSP_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 7, 'TRANSFER', NULL, 'BLD_INT_AMT', 'BILLED INTEREST', true, 'BLD_INT_AMT',
  'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'BLD_INT_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 8, 'TRANSFER', NULL, 'BLD_PRIN_AMT', 'BILLED PRINCIPAL', true, 'BLD_PRIN_AMT',
  'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'BLD_PRIN_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 9, 'TRANSFER', NULL, 'UNBLD_PRIN_AMT', 'UNBILLED PRINCIPAL', true, 'UNBLD_PRIN_AMT',
  'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'UNBLD_PRIN_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 10, 'TRANSFER', NULL, 'BILLED_DPI_INT_AMT', 'Billed DPI Interest Amount', true, 'BILLED_DPI_INT_AMT',
  'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  'DPI_BILLED_INTEREST', 'DPI BILLED INTEREST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'BILLED_DPI_INT_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 11, 'TRANSFER', NULL, 'PINT_AMT', 'PENAL AMOUNT', true, 'PINT_AMT',
  'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'PINT_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 12, 'TRANSFER', NULL, 'CBC_FEE_AMT', 'CBC FEE', true, 'CBC_FEE_AMT',
  'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  'CBC_CHARGE', 'CBC FEE', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'CBC_FEE_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 13, 'TRANSFER', NULL, 'ROUND_UP_AMT', 'ROUND UP AMOUNT', true, 'ROUND_UP_AMT',
  'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  'ROUND_OFF', 'ROUND UP AMOUNT', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'ROUND_UP_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 14, 'TRANSFER', NULL, 'EXCESS_INCOME_INT_AMT', 'EXCESS INTEREST INCOME', true, 'EXCESS_INCOME_INT_AMT',
  'LOAN_ACCOUNT', 'INT_INC', 'EXCESS INTEREST INCOME', NULL, NULL, NULL,
  'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'EXCESS_INCOME_INT_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 15, 'TRANSFER', NULL, 'EXCESS_ACCOUNT_INC_AMT', 'EXCESS AMOUNT', true, 'EXCESS_ACCOUNT_INC_AMT',
  'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL,
  'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'EXCESS_ACCOUNT_INC_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 16, 'TRANSFER', NULL, 'BLD_INT_WAIVED_AMT', 'BILLED INTEREST WAIVED', true, 'BLD_INT_WAIVED_AMT',
  'LOAN_ACCOUNT', 'BILLED_INT_WAIVE', 'BILLED INTEREST WAIVED', NULL, NULL, NULL,
  'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'BLD_INT_WAIVED_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 17, 'TRANSFER', NULL, 'STD_BLD_PRIN_WAIVED_AMT', 'STD BILLED PRINCIPAL WAIVED', true, 'STD_BLD_PRIN_WAIVED_AMT',
  'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD BILLED PRINCIPAL WAIVED', NULL, NULL, NULL,
  'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'STD_BLD_PRIN_WAIVED_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 18, 'TRANSFER', NULL, 'NPA_BLD_PRIN_WAIVED_AMT', 'NPA BILLED PRINCIPAL WAIVED', true, 'NPA_BLD_PRIN_WAIVED_AMT',
  'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA BILLED PRINCIPAL WAIVED', NULL, NULL, NULL,
  'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'NPA_BLD_PRIN_WAIVED_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 19, 'TRANSFER', NULL, 'STD_UNBLD_PRIN_WAIVED_AMT', 'STD UNBILLED PRINCIPAL WAIVED', true, 'STD_UNBLD_PRIN_WAIVED_AMT',
  'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL,
  'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'STD_UNBLD_PRIN_WAIVED_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 20, 'TRANSFER', NULL, 'NPA_UNBLD_PRIN_WAIVED_AMT', 'NPA UNBILLED PRINCIPAL WAIVED', true, 'NPA_UNBLD_PRIN_WAIVED_AMT',
  'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL,
  'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'NPA_UNBLD_PRIN_WAIVED_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 21, 'TRANSFER', NULL, 'BILLED_DPI_INT_WAIVED_AMT', 'BILLED DPI INTEREST WAIVED', true, 'BILLED_DPI_INT_WAIVED_AMT',
  'LOAN_ACCOUNT', 'DPI_BILLED_INT_WAIVE', 'DPI Billed INT Waive OFF', NULL, NULL, NULL,
  'DPI_BILLED_INTEREST', 'DPI BILLED INTEREST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'BILLED_DPI_INT_WAIVED_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 22, 'TRANSFER', NULL, 'PINT_AMT_WAIVED', 'PENAL AMOUNT WAIVED', true, 'PINT_AMT_WAIVED',
  'LOAN_ACCOUNT', 'LOSSES_LPP_WAIVED', 'PENAL AMOUNT WAIVED', NULL, NULL, NULL,
  'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'PINT_AMT_WAIVED'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 23, 'TRANSFER', NULL, 'CBC_FEE_AMT_WAIVED', 'CBC FEE WAIVED', true, 'CBC_FEE_AMT_WAIVED',
  'LOAN_ACCOUNT', 'FEE_WAIVED', 'FEES WAIVED', NULL, NULL, NULL,
  'CBC_CHARGE', 'CBC FEE WAIVED', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'CBC_FEE_AMT_WAIVED'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 24, 'TRANSFER', NULL, 'ROUND_DOWN_AMT', 'ROUND DOWN AMOUNT', true, 'ROUND_DOWN_AMT',
  'LOAN_ACCOUNT', 'ROUND_OFF', 'ROUND DOWN AMOUNT', NULL, NULL, NULL,
  'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'ROUND_DOWN_AMT'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 25, 'TRANSFER', NULL, 'FORCLSR_CHRG', 'FORECLOSURE CHARGE', true, 'FORCLSR_CHRG',
  'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  'PART_PREPAYMENT_CHARGES', 'FORECLOSURE CHARGE', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'FORCLSR_CHRG'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 26, 'TRANSFER', NULL, 'FORCLSR_CHRG_TAX', 'FORECLOSURE CHARGE TAX', true, 'FORCLSR_CHRG_TAX',
  'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL,
  'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'FORCLSR_CHRG_TAX'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 27, 'TRANSFER', NULL, 'FORCLSR_CHRG_SGST', 'FORECLOSURE CHARGE SGST', true, 'FORCLSR_CHRG_SGST',
  'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL,
  'SGST', 'SGST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'FORCLSR_CHRG_SGST'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 28, 'TRANSFER', NULL, 'FORCLSR_CHRG_CGST', 'FORECLOSURE CHARGE CGST', true, 'FORCLSR_CHRG_CGST',
  'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL,
  'CGST', 'CGST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'FORCLSR_CHRG_CGST'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 29, 'TRANSFER', NULL, 'FORCLSR_CHRG_IGST', 'FORECLOSURE CHARGE IGST', true, 'FORCLSR_CHRG_IGST',
  'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL,
  'IGST', 'IGST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'FORCLSR_CHRG_IGST'
    AND COALESCE(x.is_deleted,false) = false)
UNION ALL
SELECT tc.id, 30, 'TRANSFER', NULL, 'FORCLSR_CHRG_UTGST', 'FORECLOSURE CHARGE UTGST', true, 'FORCLSR_CHRG_UTGST',
  'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL,
  'UTGST', 'UTGST', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL,
  NOW(), '52', NOW(), '51', NOW(), '52', false
FROM mfi_accounting.transaction_catalogue tc
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tc.is_deleted, false) = false AND NOT EXISTS (SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
  WHERE x.transaction_catalogue_id = tc.id AND x.reference_code = 'FORCLSR_CHRG_UTGST'
    AND COALESCE(x.is_deleted,false) = false);

COMMIT;

\echo '=== RSCH_LOAN_PREPAYMENT accounting rules (active) ==='
SELECT tar.sequence_number AS seq, tar.reference_code, tar.source_amount,
       tar.debit_account_placeholder AS dr, tar.credit_account_placeholder AS cr, tar.entry_type
FROM mfi_accounting.transaction_accounting_rule tar
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tar.transaction_catalogue_id
WHERE tc.type = 'RSCH_LOAN_PREPAYMENT' AND tc.sub_type = 'CASH'
  AND COALESCE(tar.is_deleted, false) = false
ORDER BY tar.sequence_number;
