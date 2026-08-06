-- QA4 ONLY — RSCH_LOAN_PREPAYMENT accounting setup (TDPQA-72)
-- Plain statements with fixed ids taken from mfi_qa4. Do NOT run on any other environment.
-- Group foreclosure of a member posts RSCH_LOAN_PREPAYMENT. QA4 still has the old shape, so the
-- group legs post against the wrong heads. This replaces catalogue 429 with the fixed shape and
-- adds the placeholder to internal account maps those rules need (missing ones fail with 134207).
-- RUN ONCE. Step 1 is safe to repeat, but step 3 is a plain INSERT with no duplicate guard,
-- so running the file twice would add the maps twice. It is wrapped in a transaction: check the
-- count at the end reads 27 before you COMMIT. To abort, type ROLLBACK instead of COMMIT.
-- After running: restart accounting so the rule cache reloads.
--
-- Verified against mfi_qa4 before writing: all 11 product-catalogue ids and all 24 account ids
-- exist, and none of the 118 maps below are already present.
-- TDPQA-240 needs nothing here; that fix is code only.

BEGIN;

-- 1) remove the old rules
UPDATE mfi_accounting.transaction_accounting_rule
SET is_deleted = true, updated_on = NOW(), updated_by = 'TDPQA72'
WHERE transaction_catalogue_id = 429
  AND COALESCE(is_deleted, false) = false;

-- 2) the fixed rules (27)
INSERT INTO mfi_accounting.transaction_accounting_rule (
  transaction_catalogue_id, sequence_number, entry_type, entry_lookup_code, reference_code,
  reference_description, display_flag, source_amount, product_resolution_placeholder,
  debit_account_placeholder, debit_narration, debit_part_info_1, debit_part_info_2, debit_part_info_3,
  credit_account_placeholder, credit_narration, credit_part_info_1, credit_part_info_2, credit_part_info_3,
  fallback_credit_placeholder, fallback_credit_narration, fallback_credit_part_info_1,
  fallback_credit_part_info_2, fallback_credit_part_info_3, condition_type, condition_expression,
  entry_sub_type, created_on, created_by, approved_on, approved_by, updated_on, updated_by, is_deleted)
VALUES
  (429, 1, 'TRANSFER', NULL, 'ADV_BLD_INT_AMT', 'ADVANCE BILLED INTEREST', 'true', 'ADV_BLD_INT_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'BILLED_INTEREST', 'ADVANCE BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 2, 'TRANSFER', NULL, 'ADV_UNBLD_PRIN_AMT', 'ADVANCE UNBILLED PRINCIPAL', 'true', 'ADV_UNBLD_PRIN_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'ADVANCE UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 3, 'TRANSFER', NULL, 'ADV_PINT_AMT', 'ADVANCE PENAL AMOUNT', 'true', 'ADV_PINT_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'PENAL', 'ADVANCE PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 4, 'TRANSFER', NULL, 'ADV_CBC_FEE_AMT', 'ADVANCE CBC FEE', 'true', 'ADV_CBC_FEE_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'CBC_CHARGE', 'ADVANCE CBC FEE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 6, 'TRANSFER', NULL, 'TRMN_SUSP_AMT', 'TERMINATION SUSPENSE ACCOUNT', 'true', 'TRMN_SUSP_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 7, 'TRANSFER', NULL, 'BLD_INT_AMT', 'BILLED INTEREST', 'true', 'BLD_INT_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 8, 'TRANSFER', NULL, 'BLD_PRIN_AMT', 'BILLED PRINCIPAL', 'true', 'BLD_PRIN_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 9, 'TRANSFER', NULL, 'UNBLD_PRIN_AMT', 'UNBILLED PRINCIPAL', 'true', 'UNBLD_PRIN_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 11, 'TRANSFER', NULL, 'PINT_AMT', 'PENAL AMOUNT', 'true', 'PINT_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 12, 'TRANSFER', NULL, 'CBC_FEE_AMT', 'CBC FEE', 'true', 'CBC_FEE_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'CBC_CHARGE', 'CBC FEE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 13, 'TRANSFER', NULL, 'ROUND_UP_AMT', 'ROUND UP AMOUNT', 'true', 'ROUND_UP_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'ROUND_OFF', 'ROUND UP AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 14, 'TRANSFER', NULL, 'EXCESS_INCOME_INT_AMT', 'EXCESS INTEREST INCOME', 'true', 'EXCESS_INCOME_INT_AMT', 'LOAN_ACCOUNT', 'INT_INC', 'EXCESS INTEREST INCOME', NULL, NULL, NULL, 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 15, 'TRANSFER', NULL, 'EXCESS_ACCOUNT_INC_AMT', 'EXCESS AMOUNT', 'true', 'EXCESS_ACCOUNT_INC_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 16, 'TRANSFER', NULL, 'BLD_INT_WAIVED_AMT', 'BILLED INTEREST WAIVED', 'true', 'BLD_INT_WAIVED_AMT', 'LOAN_ACCOUNT', 'BILLED_INT_WAIVE', 'BILLED INTEREST WAIVED', NULL, NULL, NULL, 'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 17, 'TRANSFER', NULL, 'STD_BLD_PRIN_WAIVED_AMT', 'STD BILLED PRINCIPAL WAIVED', 'true', 'STD_BLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD BILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 18, 'TRANSFER', NULL, 'NPA_BLD_PRIN_WAIVED_AMT', 'NPA BILLED PRINCIPAL WAIVED', 'true', 'NPA_BLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA BILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 19, 'TRANSFER', NULL, 'STD_UNBLD_PRIN_WAIVED_AMT', 'STD UNBILLED PRINCIPAL WAIVED', 'true', 'STD_UNBLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 20, 'TRANSFER', NULL, 'NPA_UNBLD_PRIN_WAIVED_AMT', 'NPA UNBILLED PRINCIPAL WAIVED', 'true', 'NPA_UNBLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 22, 'TRANSFER', NULL, 'PINT_AMT_WAIVED', 'PENAL AMOUNT WAIVED', 'true', 'PINT_AMT_WAIVED', 'LOAN_ACCOUNT', 'LOSSES_LPP_WAIVED', 'PENAL AMOUNT WAIVED', NULL, NULL, NULL, 'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 23, 'TRANSFER', NULL, 'CBC_FEE_AMT_WAIVED', 'CBC FEE WAIVED', 'true', 'CBC_FEE_AMT_WAIVED', 'LOAN_ACCOUNT', 'FEE_WAIVED', 'FEES WAIVED', NULL, NULL, NULL, 'CBC_CHARGE', 'CBC FEE WAIVED', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 24, 'TRANSFER', NULL, 'ROUND_DOWN_AMT', 'ROUND DOWN AMOUNT', 'true', 'ROUND_DOWN_AMT', 'LOAN_ACCOUNT', 'ROUND_OFF', 'ROUND DOWN AMOUNT', NULL, NULL, NULL, 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 25, 'TRANSFER', NULL, 'FORCLSR_CHRG', 'FORECLOSURE CHARGE', 'true', 'FORCLSR_CHRG', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'PART_PREPAYMENT_CHARGES', 'FORECLOSURE CHARGE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 26, 'TRANSFER', NULL, 'FORCLSR_CHRG_TAX', 'FORECLOSURE CHARGE TAX', 'true', 'FORCLSR_CHRG_TAX', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 27, 'TRANSFER', NULL, 'FORCLSR_CHRG_SGST', 'FORECLOSURE CHARGE SGST', 'true', 'FORCLSR_CHRG_SGST', 'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, 'SGST', 'SGST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 28, 'TRANSFER', NULL, 'FORCLSR_CHRG_CGST', 'FORECLOSURE CHARGE CGST', 'true', 'FORCLSR_CHRG_CGST', 'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, 'CGST', 'CGST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 29, 'TRANSFER', NULL, 'FORCLSR_CHRG_IGST', 'FORECLOSURE CHARGE IGST', 'true', 'FORCLSR_CHRG_IGST', 'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, 'IGST', 'IGST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false),
  (429, 30, 'TRANSFER', NULL, 'FORCLSR_CHRG_UTGST', 'FORECLOSURE CHARGE UTGST', 'true', 'FORCLSR_CHRG_UTGST', 'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, 'UTGST', 'UTGST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL, NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false);

-- 3) placeholder to internal account maps (118)
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
VALUES
  (3476, 'FEE_WAIVED', 6793, false),
  (3476, 'INT_INC', 35, false),
  (3476, 'LOSSES_LPP_WAIVED', 53, false),
  (3678, 'BILLED_INTEREST', 36, false),
  (3678, 'BILLED_INT_WAIVE', 4593, false),
  (3678, 'BILLED_PRINCIPAL', 31, false),
  (3678, 'CBC_CHARGE', 1591, false),
  (3678, 'FEE_WAIVED', 6793, false),
  (3678, 'INT_INC', 35, false),
  (3678, 'LOSSES_LPP_WAIVED', 53, false),
  (3678, 'PENAL', 26, false),
  (3678, 'PRIN_WAIVE_NPA', 5394, false),
  (3678, 'PRIN_WAIVE_STD', 5393, false),
  (3678, 'ROUND_OFF', 63, false),
  (3778, 'BILLED_INTEREST', 10, false),
  (3778, 'BILLED_INT_WAIVE', 4593, false),
  (3778, 'BILLED_PRINCIPAL', 11, false),
  (3778, 'CBC_CHARGE', 1591, false),
  (3778, 'FEE_WAIVED', 6793, false),
  (3778, 'INT_INC', 35, false),
  (3778, 'LOSSES_LPP_WAIVED', 45, false),
  (3778, 'PENAL', 60, false),
  (3778, 'PRIN_WAIVE_NPA', 4493, false),
  (3778, 'PRIN_WAIVE_STD', 4294, false),
  (3778, 'ROUND_OFF', 63, false),
  (3896, 'CGST', 1495, false),
  (3896, 'FEE_WAIVED', 6793, false),
  (3896, 'GST_PAYABLE', 1492, false),
  (3896, 'IGST', 1493, false),
  (3896, 'INT_INC', 35, false),
  (3896, 'LOSSES_LPP_WAIVED', 45, false),
  (3896, 'PART_PREPAYMENT_CHARGES', 27, false),
  (3896, 'SGST', 1494, false),
  (3896, 'UTGST', 1491, false),
  (3996, 'BILLED_INTEREST', 36, false),
  (3996, 'BILLED_INT_WAIVE', 4593, false),
  (3996, 'BILLED_PRINCIPAL', 31, false),
  (3996, 'CBC_CHARGE', 1591, false),
  (3996, 'FEE_WAIVED', 6793, false),
  (3996, 'INT_INC', 35, false),
  (3996, 'LOSSES_LPP_WAIVED', 53, false),
  (3996, 'PENAL', 26, false),
  (3996, 'PRIN_WAIVE_NPA', 5394, false),
  (3996, 'PRIN_WAIVE_STD', 5393, false),
  (3996, 'ROUND_OFF', 63, false),
  (3996, 'TRMN_SUSP', 3093, false),
  (4296, 'BILLED_INTEREST', 10, false),
  (4296, 'BILLED_INT_WAIVE', 4593, false),
  (4296, 'BILLED_PRINCIPAL', 11, false),
  (4296, 'CBC_CHARGE', 1591, false),
  (4296, 'FEE_WAIVED', 6793, false),
  (4296, 'INT_INC', 35, false),
  (4296, 'LOSSES_LPP_WAIVED', 45, false),
  (4296, 'PENAL', 60, false),
  (4296, 'PRIN_WAIVE_NPA', 4493, false),
  (4296, 'PRIN_WAIVE_STD', 4294, false),
  (4296, 'ROUND_OFF', 63, false),
  (4296, 'TRMN_SUSP', 3093, false),
  (4396, 'BILLED_INTEREST', 36, false),
  (4396, 'BILLED_INT_WAIVE', 4593, false),
  (4396, 'BILLED_PRINCIPAL', 31, false),
  (4396, 'CBC_CHARGE', 1591, false),
  (4396, 'FEE_WAIVED', 6793, false),
  (4396, 'INT_INC', 35, false),
  (4396, 'LOSSES_LPP_WAIVED', 53, false),
  (4396, 'PENAL', 26, false),
  (4396, 'PRIN_WAIVE_NPA', 5394, false),
  (4396, 'PRIN_WAIVE_STD', 5393, false),
  (4396, 'ROUND_OFF', 63, false),
  (4396, 'TRMN_SUSP', 3093, false),
  (4496, 'BILLED_INTEREST', 10, false),
  (4496, 'BILLED_INT_WAIVE', 4593, false),
  (4496, 'BILLED_PRINCIPAL', 11, false),
  (4496, 'CBC_CHARGE', 1591, false),
  (4496, 'FEE_WAIVED', 6793, false),
  (4496, 'INT_INC', 35, false),
  (4496, 'LOSSES_LPP_WAIVED', 45, false),
  (4496, 'PENAL', 60, false),
  (4496, 'PRIN_WAIVE_NPA', 4493, false),
  (4496, 'PRIN_WAIVE_STD', 4294, false),
  (4496, 'ROUND_OFF', 63, false),
  (4496, 'TRMN_SUSP', 3093, false),
  (4596, 'BILLED_INTEREST', 36, false),
  (4596, 'BILLED_INT_WAIVE', 4593, false),
  (4596, 'BILLED_PRINCIPAL', 31, false),
  (4596, 'CBC_CHARGE', 1591, false),
  (4596, 'FEE_WAIVED', 6793, false),
  (4596, 'INT_INC', 35, false),
  (4596, 'LOSSES_LPP_WAIVED', 53, false),
  (4596, 'PENAL', 26, false),
  (4596, 'PRIN_WAIVE_NPA', 4493, false),
  (4596, 'PRIN_WAIVE_STD', 4294, false),
  (4596, 'ROUND_OFF', 63, false),
  (4596, 'TRMN_SUSP', 3093, false),
  (4696, 'BILLED_INTEREST', 10, false),
  (4696, 'BILLED_INT_WAIVE', 4593, false),
  (4696, 'BILLED_PRINCIPAL', 11, false),
  (4696, 'CBC_CHARGE', 1591, false),
  (4696, 'FEE_WAIVED', 6793, false),
  (4696, 'INT_INC', 35, false),
  (4696, 'LOSSES_LPP_WAIVED', 45, false),
  (4696, 'PENAL', 60, false),
  (4696, 'PRIN_WAIVE_NPA', 4493, false),
  (4696, 'PRIN_WAIVE_STD', 4294, false),
  (4696, 'ROUND_OFF', 63, false),
  (4696, 'TRMN_SUSP', 3093, false),
  (4896, 'BILLED_INTEREST', 36, false),
  (4896, 'BILLED_INT_WAIVE', 4593, false),
  (4896, 'BILLED_PRINCIPAL', 31, false),
  (4896, 'CBC_CHARGE', 1591, false),
  (4896, 'FEE_WAIVED', 6793, false),
  (4896, 'INT_INC', 35, false),
  (4896, 'LOSSES_LPP_WAIVED', 53, false),
  (4896, 'PENAL', 26, false),
  (4896, 'PRIN_WAIVE_NPA', 4493, false),
  (4896, 'PRIN_WAIVE_STD', 4294, false),
  (4896, 'ROUND_OFF', 63, false),
  (4896, 'TRMN_SUSP', 3093, false);

-- 4) check: expect 27
SELECT COUNT(*) AS active_rules
FROM mfi_accounting.transaction_accounting_rule
WHERE transaction_catalogue_id = 429 AND COALESCE(is_deleted, false) = false;

COMMIT;
