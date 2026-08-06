-- QA masterdata seed — RSCH_LOAN_PREPAYMENT accounting setup (TDPQA-72)
--
-- WHY: on a group loan, when a member forecloses, the group posts RSCH_LOAN_PREPAYMENT.
-- QA4 still carries the pre-TDPQA-72 shape (TRMN_AMT/PRIN_AMT/INT_AMT/POS legs debiting
-- DUE_TO_FC_B). The fixed shape funds termination suspense once (TRMN_SUSP_AMT) and then
-- debits every settlement leg from TRMN_SUSP, which is what makes the group settlement agree
-- with the member settlement. Without this the parent legs post against the wrong heads.
--
-- WHAT IT DOES
--   1. soft-deletes the active RSCH_LOAN_PREPAYMENT/CASH rules
--   2. inserts the 27 fixed rules (verified against local, DPI legs excluded - see below)
--   3. backfills the placeholder -> internal account maps those rules need, taking each
--      product's own existing mapping (missing maps fail at runtime with 134207)
--
-- DPI: BILLED_DPI_INT_AMT / ADV_BILLED_DPI_INT_AMT / BILLED_DPI_INT_WAIVED_AMT are NOT seeded.
-- QA4 has no DPI_BILLED_INTEREST or DPI_BILLED_INT_WAIVE placeholder, so those rules cannot
-- resolve there. Add them only after DPI masterdata lands.
--
-- Catalogues 22 (DEATH_FORECLOSURE) and 428 (RSCH_DEATH_FORECLOSURE) already match local and
-- are NOT touched. Catalogue 11 (LOAN_PREPAYMENT) is NOT touched.
--
-- Idempotent: safe to re-run. Resolves the catalogue by type/sub_type, never by hardcoded id.
-- AFTER APPLY: restart accounting, or flush Redis DB5 keys
--              transaction_accounting_rule::*findByTransactionCatalogueId_<id>
--
-- TDPQA-240 needs NO setup. That fix is code only; the BILLING/NORMAL_BILLING catalogue it
-- posts through already exists on QA4 and is untouched here.
--
-- EXPECTED ON QA4 (measured against mfi_qa4 before writing this):
--   UPDATE 28   old rules soft-deleted
--   INSERT 27   fixed rules
--   INSERT ~118 placeholder maps created
--   final: 27 active rules, 0 unresolved placeholders
-- If the AFTER checks do not show 27 and an empty unresolved list, do not commit.
--
-- Run:  psql -h <qa-host> -p 5433 -U <user> -d mfi_qa4 -v ON_ERROR_STOP=1 -f <this file>
-- Dry run first: change the final COMMIT to ROLLBACK and confirm the AFTER output.

\set ON_ERROR_STOP on
BEGIN;

\echo '--- BEFORE ---'
SELECT tc.id AS catalogue,
       COUNT(*) FILTER (WHERE COALESCE(tar.is_deleted,false)=false) AS active_rules
FROM mfi_accounting.transaction_catalogue tc
LEFT JOIN mfi_accounting.transaction_accounting_rule tar ON tar.transaction_catalogue_id = tc.id
WHERE tc.type='RSCH_LOAN_PREPAYMENT' AND tc.sub_type='CASH' AND COALESCE(tc.is_deleted,false)=false
GROUP BY tc.id;

UPDATE mfi_accounting.transaction_accounting_rule tar
SET is_deleted = true, updated_on = NOW(), updated_by = 'TDPQA72'
WHERE tar.transaction_catalogue_id IN (
        SELECT tc.id FROM mfi_accounting.transaction_catalogue tc
        WHERE tc.type='RSCH_LOAN_PREPAYMENT' AND tc.sub_type='CASH'
          AND COALESCE(tc.is_deleted,false)=false)
  AND COALESCE(tar.is_deleted,false) = false;

INSERT INTO mfi_accounting.transaction_accounting_rule (
  transaction_catalogue_id, sequence_number, entry_type, entry_lookup_code, reference_code,
  reference_description, display_flag, source_amount, product_resolution_placeholder,
  debit_account_placeholder, debit_narration, debit_part_info_1, debit_part_info_2, debit_part_info_3,
  credit_account_placeholder, credit_narration, credit_part_info_1, credit_part_info_2, credit_part_info_3,
  fallback_credit_placeholder, fallback_credit_narration, fallback_credit_part_info_1,
  fallback_credit_part_info_2, fallback_credit_part_info_3, condition_type, condition_expression,
  entry_sub_type, created_on, created_by, approved_on, approved_by, updated_on, updated_by, is_deleted)
SELECT tc.id, v.sequence_number::int, v.entry_type, v.entry_lookup_code, v.reference_code,
       v.reference_description, v.display_flag::boolean, v.source_amount,
       v.product_resolution_placeholder, v.debit_account_placeholder, v.debit_narration,
       v.debit_part_info_1, v.debit_part_info_2, v.debit_part_info_3,
       v.credit_account_placeholder, v.credit_narration, v.credit_part_info_1,
       v.credit_part_info_2, v.credit_part_info_3, v.fallback_credit_placeholder,
       v.fallback_credit_narration, v.fallback_credit_part_info_1, v.fallback_credit_part_info_2,
       v.fallback_credit_part_info_3, v.condition_type, v.condition_expression, v.entry_sub_type,
       NOW(), 'TDPQA72', NOW(), 'TDPQA72', NOW(), 'TDPQA72', false
FROM mfi_accounting.transaction_catalogue tc
CROSS JOIN (VALUES
    (1, 'TRANSFER', NULL, 'ADV_BLD_INT_AMT', 'ADVANCE BILLED INTEREST', 'true', 'ADV_BLD_INT_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'BILLED_INTEREST', 'ADVANCE BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (2, 'TRANSFER', NULL, 'ADV_UNBLD_PRIN_AMT', 'ADVANCE UNBILLED PRINCIPAL', 'true', 'ADV_UNBLD_PRIN_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'ADVANCE UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (3, 'TRANSFER', NULL, 'ADV_PINT_AMT', 'ADVANCE PENAL AMOUNT', 'true', 'ADV_PINT_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'PENAL', 'ADVANCE PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (4, 'TRANSFER', NULL, 'ADV_CBC_FEE_AMT', 'ADVANCE CBC FEE', 'true', 'ADV_CBC_FEE_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'CBC_CHARGE', 'ADVANCE CBC FEE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (6, 'TRANSFER', NULL, 'TRMN_SUSP_AMT', 'TERMINATION SUSPENSE ACCOUNT', 'true', 'TRMN_SUSP_AMT', 'LOAN_ACCOUNT', 'DUE_TO_FC_B', 'DUE TO FC B', NULL, NULL, NULL, 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (7, 'TRANSFER', NULL, 'BLD_INT_AMT', 'BILLED INTEREST', 'true', 'BLD_INT_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (8, 'TRANSFER', NULL, 'BLD_PRIN_AMT', 'BILLED PRINCIPAL', 'true', 'BLD_PRIN_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (9, 'TRANSFER', NULL, 'UNBLD_PRIN_AMT', 'UNBILLED PRINCIPAL', 'true', 'UNBLD_PRIN_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (11, 'TRANSFER', NULL, 'PINT_AMT', 'PENAL AMOUNT', 'true', 'PINT_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (12, 'TRANSFER', NULL, 'CBC_FEE_AMT', 'CBC FEE', 'true', 'CBC_FEE_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'CBC_CHARGE', 'CBC FEE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (13, 'TRANSFER', NULL, 'ROUND_UP_AMT', 'ROUND UP AMOUNT', 'true', 'ROUND_UP_AMT', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'ROUND_OFF', 'ROUND UP AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (14, 'TRANSFER', NULL, 'EXCESS_INCOME_INT_AMT', 'EXCESS INTEREST INCOME', 'true', 'EXCESS_INCOME_INT_AMT', 'LOAN_ACCOUNT', 'INT_INC', 'EXCESS INTEREST INCOME', NULL, NULL, NULL, 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (15, 'TRANSFER', NULL, 'EXCESS_ACCOUNT_INC_AMT', 'EXCESS AMOUNT', 'true', 'EXCESS_ACCOUNT_INC_AMT', 'LOAN_ACCOUNT', 'EXCESS_ACCT', 'EXCESS AMOUNT', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (16, 'TRANSFER', NULL, 'BLD_INT_WAIVED_AMT', 'BILLED INTEREST WAIVED', 'true', 'BLD_INT_WAIVED_AMT', 'LOAN_ACCOUNT', 'BILLED_INT_WAIVE', 'BILLED INTEREST WAIVED', NULL, NULL, NULL, 'BILLED_INTEREST', 'BILLED INTEREST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (17, 'TRANSFER', NULL, 'STD_BLD_PRIN_WAIVED_AMT', 'STD BILLED PRINCIPAL WAIVED', 'true', 'STD_BLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD BILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (18, 'TRANSFER', NULL, 'NPA_BLD_PRIN_WAIVED_AMT', 'NPA BILLED PRINCIPAL WAIVED', 'true', 'NPA_BLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA BILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'BILLED_PRINCIPAL', 'BILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (19, 'TRANSFER', NULL, 'STD_UNBLD_PRIN_WAIVED_AMT', 'STD UNBILLED PRINCIPAL WAIVED', 'true', 'STD_UNBLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_STD', 'STD UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (20, 'TRANSFER', NULL, 'NPA_UNBLD_PRIN_WAIVED_AMT', 'NPA UNBILLED PRINCIPAL WAIVED', 'true', 'NPA_UNBLD_PRIN_WAIVED_AMT', 'LOAN_ACCOUNT', 'PRIN_WAIVE_NPA', 'NPA UNBILLED PRINCIPAL WAIVED', NULL, NULL, NULL, 'LOAN_ACCOUNT', 'UNBILLED PRINCIPAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (22, 'TRANSFER', NULL, 'PINT_AMT_WAIVED', 'PENAL AMOUNT WAIVED', 'true', 'PINT_AMT_WAIVED', 'LOAN_ACCOUNT', 'LOSSES_LPP_WAIVED', 'PENAL AMOUNT WAIVED', NULL, NULL, NULL, 'PENAL', 'PENAL AMOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (23, 'TRANSFER', NULL, 'CBC_FEE_AMT_WAIVED', 'CBC FEE WAIVED', 'true', 'CBC_FEE_AMT_WAIVED', 'LOAN_ACCOUNT', 'FEE_WAIVED', 'FEES WAIVED', NULL, NULL, NULL, 'CBC_CHARGE', 'CBC FEE WAIVED', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (24, 'TRANSFER', NULL, 'ROUND_DOWN_AMT', 'ROUND DOWN AMOUNT', 'true', 'ROUND_DOWN_AMT', 'LOAN_ACCOUNT', 'ROUND_OFF', 'ROUND DOWN AMOUNT', NULL, NULL, NULL, 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (25, 'TRANSFER', NULL, 'FORCLSR_CHRG', 'FORECLOSURE CHARGE', 'true', 'FORCLSR_CHRG', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'PART_PREPAYMENT_CHARGES', 'FORECLOSURE CHARGE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (26, 'TRANSFER', NULL, 'FORCLSR_CHRG_TAX', 'FORECLOSURE CHARGE TAX', 'true', 'FORCLSR_CHRG_TAX', 'LOAN_ACCOUNT', 'TRMN_SUSP', 'TERMINATION SUSPENSE ACCOUNT', NULL, NULL, NULL, 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (27, 'TRANSFER', NULL, 'FORCLSR_CHRG_SGST', 'FORECLOSURE CHARGE SGST', 'true', 'FORCLSR_CHRG_SGST', 'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, 'SGST', 'SGST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (28, 'TRANSFER', NULL, 'FORCLSR_CHRG_CGST', 'FORECLOSURE CHARGE CGST', 'true', 'FORCLSR_CHRG_CGST', 'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, 'CGST', 'CGST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (29, 'TRANSFER', NULL, 'FORCLSR_CHRG_IGST', 'FORECLOSURE CHARGE IGST', 'true', 'FORCLSR_CHRG_IGST', 'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, 'IGST', 'IGST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL),
    (30, 'TRANSFER', NULL, 'FORCLSR_CHRG_UTGST', 'FORECLOSURE CHARGE UTGST', 'true', 'FORCLSR_CHRG_UTGST', 'LOAN_ACCOUNT', 'GST_PAYABLE', 'GST PAYABLE', NULL, NULL, NULL, 'UTGST', 'UTGST', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'NA', NULL, NULL)
) AS v(sequence_number, entry_type, entry_lookup_code, reference_code, reference_description,
       display_flag, source_amount, product_resolution_placeholder, debit_account_placeholder,
       debit_narration, debit_part_info_1, debit_part_info_2, debit_part_info_3,
       credit_account_placeholder, credit_narration, credit_part_info_1, credit_part_info_2,
       credit_part_info_3, fallback_credit_placeholder, fallback_credit_narration,
       fallback_credit_part_info_1, fallback_credit_part_info_2, fallback_credit_part_info_3,
       condition_type, condition_expression, entry_sub_type)
WHERE tc.type='RSCH_LOAN_PREPAYMENT' AND tc.sub_type='CASH' AND COALESCE(tc.is_deleted,false)=false
  AND NOT EXISTS (
        SELECT 1 FROM mfi_accounting.transaction_accounting_rule x
        WHERE x.transaction_catalogue_id = tc.id
          AND x.reference_code = v.reference_code
          AND COALESCE(x.is_deleted,false) = false);

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT need.ptc_id, need.ph, src.iad, false
FROM (
  SELECT ptc.id AS ptc_id, ptc.product_id, ph.code AS ph
  FROM mfi_accounting.product__transaction_catalogue ptc
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
  CROSS JOIN LATERAL (
    SELECT DISTINCT unnest(ARRAY[tar.debit_account_placeholder, tar.credit_account_placeholder]) AS code
    FROM mfi_accounting.transaction_accounting_rule tar
    WHERE tar.transaction_catalogue_id = tc.id AND COALESCE(tar.is_deleted,false)=false) ph
  WHERE tc.type='RSCH_LOAN_PREPAYMENT' AND tc.sub_type='CASH'
    AND COALESCE(tc.is_deleted,false)=false AND COALESCE(ptc.is_deleted,false)=false
    AND ph.code IS NOT NULL
) need
JOIN LATERAL (
  SELECT MIN(m.internal_account_definition_id) AS iad
  FROM mfi_accounting.product_transaction_catalogue__placeholder__iad m
  JOIN mfi_accounting.product__transaction_catalogue sp ON sp.id = m.product_transaction_catalogue_id
  WHERE sp.product_id = need.product_id AND m.placeholder_code = need.ph
    AND COALESCE(m.is_deleted,false)=false
) src ON src.iad IS NOT NULL
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad e
  WHERE e.product_transaction_catalogue_id = need.ptc_id
    AND e.placeholder_code = need.ph AND COALESCE(e.is_deleted,false)=false);

-- FEE_WAIVED is a Sheet15 placeholder that only some products carry, so the per-product source
-- above cannot find it for the rest. It resolves to a single shared waiver account in every
-- environment, so fall back to the one this environment already uses.
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
  (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'FEE_WAIVED', fw.iad, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
CROSS JOIN (
  SELECT MIN(internal_account_definition_id) AS iad
  FROM mfi_accounting.product_transaction_catalogue__placeholder__iad
  WHERE placeholder_code='FEE_WAIVED' AND COALESCE(is_deleted,false)=false) fw
WHERE tc.type='RSCH_LOAN_PREPAYMENT' AND tc.sub_type='CASH'
  AND COALESCE(tc.is_deleted,false)=false AND COALESCE(ptc.is_deleted,false)=false
  AND fw.iad IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad e
    WHERE e.product_transaction_catalogue_id = ptc.id AND e.placeholder_code='FEE_WAIVED'
      AND COALESCE(e.is_deleted,false)=false);

\echo '--- AFTER: active rules (expect 27) ---'
SELECT tc.id AS catalogue,
       COUNT(*) FILTER (WHERE COALESCE(tar.is_deleted,false)=false) AS active_rules
FROM mfi_accounting.transaction_catalogue tc
LEFT JOIN mfi_accounting.transaction_accounting_rule tar ON tar.transaction_catalogue_id = tc.id
WHERE tc.type='RSCH_LOAN_PREPAYMENT' AND tc.sub_type='CASH' AND COALESCE(tc.is_deleted,false)=false
GROUP BY tc.id;

\echo '--- AFTER: unresolved placeholder maps (expect 0 for products 1, 44, 45) ---'
SELECT ptc.product_id, ph.code AS placeholder
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
CROSS JOIN LATERAL (
  SELECT DISTINCT unnest(ARRAY[tar.debit_account_placeholder, tar.credit_account_placeholder]) AS code
  FROM mfi_accounting.transaction_accounting_rule tar
  WHERE tar.transaction_catalogue_id = tc.id AND COALESCE(tar.is_deleted,false)=false) ph
WHERE tc.type='RSCH_LOAN_PREPAYMENT' AND tc.sub_type='CASH'
  AND COALESCE(tc.is_deleted,false)=false AND COALESCE(ptc.is_deleted,false)=false
  AND ph.code IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad m
    WHERE m.product_transaction_catalogue_id = ptc.id AND m.placeholder_code = ph.code
      AND COALESCE(m.is_deleted,false)=false)
ORDER BY ptc.product_id, ph.code;

COMMIT;
