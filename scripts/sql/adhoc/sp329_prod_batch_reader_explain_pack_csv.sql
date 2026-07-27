SELECT '===== 0 SLICE_COUNTS =====' AS section;
SELECT count(*) AS active_in_sample_partition
FROM mfi_accounting.loan_account
WHERE loan_status = 'ACTIVE'
  AND account_id >= 2 AND account_id <= 2044302;

SELECT '===== 1 INTEREST_ACCRUAL_CALC baseline =====' AS section;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.la_currency, la.expected_disbursement_date, acs.stop_interest_accrual,
 la.asset_classification_slabs_id, lp.product_id, la.la_account_number, la.la_office_id, la.interest_calculation_basis, la.approved_amount,
 la.interest_frequency, ps.interest_calculation_days_in_month, ps.interest_calculation_days_in_year, la.maturity_date, la.first_repayment_date, lp.interest_rounding_factor
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.loan_product lp ON la.loan_product_id = lp.id
 JOIN mfi_accounting.product_scheme ps ON la.la_product_scheme_id = ps.id
 JOIN mfi_accounting.loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id AND lpac.is_deleted = false
 JOIN mfi_accounting.asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
  AND lpac.asset_criteria_slab_id = la.asset_criteria_slabs_id
WHERE (la.loan_status = 'ACTIVE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;

SELECT '===== 1 INTEREST_ACCRUAL_CALC tuned =====' AS section;
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
SELECT current_setting('enable_nestloop') AS enable_nestloop_must_be_off,
       current_setting('yb_enable_batchednl') AS yb_batchednl_must_be_off,
       current_setting('yb_prefer_bnl') AS yb_prefer_bnl_must_be_off,
       current_setting('work_mem') AS work_mem_must_be_4MB;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.la_currency, la.expected_disbursement_date, acs.stop_interest_accrual,
 la.asset_classification_slabs_id, lp.product_id, la.la_account_number, la.la_office_id, la.interest_calculation_basis, la.approved_amount,
 la.interest_frequency, ps.interest_calculation_days_in_month, ps.interest_calculation_days_in_year, la.maturity_date, la.first_repayment_date, lp.interest_rounding_factor
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.loan_product lp ON la.loan_product_id = lp.id
 JOIN mfi_accounting.product_scheme ps ON la.la_product_scheme_id = ps.id
 JOIN mfi_accounting.loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id AND lpac.is_deleted = false
 JOIN mfi_accounting.asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
  AND lpac.asset_criteria_slab_id = la.asset_criteria_slabs_id
WHERE (la.loan_status = 'ACTIVE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;
ROLLBACK;

SELECT '===== 2 INTEREST_ACCRUAL_BOOKING baseline =====' AS section;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.la_currency, la.interest_frequency, la.la_account_number,
 la.asset_classification_slabs_id, acs.stop_interest_accrual,
 la.la_office_id, lp.id, lp.product_id, la.npa_ageing_start_date, la.sec_npa_tagging_date
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.loan_product lp ON la.loan_product_id = lp.id
 JOIN mfi_accounting.product_scheme ps ON la.la_product_scheme_id = ps.id
 JOIN mfi_accounting.loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id AND lpac.is_deleted = false
 JOIN mfi_accounting.asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
  AND lpac.asset_criteria_slab_id = la.asset_criteria_slabs_id
WHERE (la.loan_status = 'ACTIVE' OR la.loan_status = 'FORECLOSURE_FREEZE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;

SELECT '===== 2 INTEREST_ACCRUAL_BOOKING tuned =====' AS section;
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
SELECT current_setting('enable_nestloop') AS enable_nestloop_must_be_off,
       current_setting('yb_enable_batchednl') AS yb_batchednl_must_be_off,
       current_setting('yb_prefer_bnl') AS yb_prefer_bnl_must_be_off,
       current_setting('work_mem') AS work_mem_must_be_4MB;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.la_currency, la.interest_frequency, la.la_account_number,
 la.asset_classification_slabs_id, acs.stop_interest_accrual,
 la.la_office_id, lp.id, lp.product_id, la.npa_ageing_start_date, la.sec_npa_tagging_date
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.loan_product lp ON la.loan_product_id = lp.id
 JOIN mfi_accounting.product_scheme ps ON la.la_product_scheme_id = ps.id
 JOIN mfi_accounting.loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id AND lpac.is_deleted = false
 JOIN mfi_accounting.asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
  AND lpac.asset_criteria_slab_id = la.asset_criteria_slabs_id
WHERE (la.loan_status = 'ACTIVE' OR la.loan_status = 'FORECLOSURE_FREEZE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;
ROLLBACK;

SELECT '===== 3 PENAL_CALC baseline =====' AS section;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.la_currency, la.expected_disbursement_date, 'false' AS stop_interest_accrual,
 la.asset_classification_slabs_id, lp.product_id, la.la_account_number, la.la_office_id, la.interest_calculation_basis, la.approved_amount,
 la.interest_frequency, ps.interest_calculation_days_in_month, ps.interest_calculation_days_in_year, la.maturity_date, la.first_repayment_date
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.loan_product lp ON la.loan_product_id = lp.id
 JOIN mfi_accounting.product_scheme ps ON la.la_product_scheme_id = ps.id
WHERE (la.loan_status = 'ACTIVE') AND la.past_due_days > 0
  AND la.account_id >= 2 AND la.account_id <= 2044302;

SELECT '===== 3 PENAL_CALC tuned =====' AS section;
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
SELECT current_setting('enable_nestloop') AS enable_nestloop_must_be_off,
       current_setting('yb_enable_batchednl') AS yb_batchednl_must_be_off,
       current_setting('yb_prefer_bnl') AS yb_prefer_bnl_must_be_off,
       current_setting('work_mem') AS work_mem_must_be_4MB;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.la_currency, la.expected_disbursement_date, 'false' AS stop_interest_accrual,
 la.asset_classification_slabs_id, lp.product_id, la.la_account_number, la.la_office_id, la.interest_calculation_basis, la.approved_amount,
 la.interest_frequency, ps.interest_calculation_days_in_month, ps.interest_calculation_days_in_year, la.maturity_date, la.first_repayment_date
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.loan_product lp ON la.loan_product_id = lp.id
 JOIN mfi_accounting.product_scheme ps ON la.la_product_scheme_id = ps.id
WHERE (la.loan_status = 'ACTIVE') AND la.past_due_days > 0
  AND la.account_id >= 2 AND la.account_id <= 2044302;
ROLLBACK;

SELECT '===== 4 PENAL_BOOKING baseline =====' AS section;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT pia.loan_account_id, pia.installment_id, pia.overdue_date, pia.base_amount, pia.charge_code,
 pia.charge_fixed_amount, pia.penal_rate, pia.total_accrued_amount, pia.id, la.account_id, pia.start_date, pia.end_date, la.has_child_accounts
FROM mfi_accounting.penal_interest_accrual_details pia
 JOIN mfi_accounting.loan_account la ON la.account_id = pia.loan_account_id
WHERE pia.accrual_posting_date IS NULL AND la.loan_status = 'ACTIVE'
  AND la.account_id >= 2 AND la.account_id <= 2044302;

SELECT '===== 4 PENAL_BOOKING tuned =====' AS section;
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
SELECT current_setting('enable_nestloop') AS enable_nestloop_must_be_off,
       current_setting('yb_enable_batchednl') AS yb_batchednl_must_be_off,
       current_setting('yb_prefer_bnl') AS yb_prefer_bnl_must_be_off,
       current_setting('work_mem') AS work_mem_must_be_4MB;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT pia.loan_account_id, pia.installment_id, pia.overdue_date, pia.base_amount, pia.charge_code,
 pia.charge_fixed_amount, pia.penal_rate, pia.total_accrued_amount, pia.id, la.account_id, pia.start_date, pia.end_date, la.has_child_accounts
FROM mfi_accounting.penal_interest_accrual_details pia
 JOIN mfi_accounting.loan_account la ON la.account_id = pia.loan_account_id
WHERE pia.accrual_posting_date IS NULL AND la.loan_status = 'ACTIVE'
  AND la.account_id >= 2 AND la.account_id <= 2044302;
ROLLBACK;

SELECT '===== 5 BILLING baseline =====' AS section;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.la_currency, la.la_account_number, '' as stop_interest_accrual,
 la.la_office_id, la.expected_disbursement_date
FROM mfi_accounting.loan_account la
WHERE la.loan_status IN ('ACTIVE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;

SELECT '===== 5 BILLING tuned =====' AS section;
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
SELECT current_setting('enable_nestloop') AS enable_nestloop_must_be_off,
       current_setting('yb_enable_batchednl') AS yb_batchednl_must_be_off,
       current_setting('yb_prefer_bnl') AS yb_prefer_bnl_must_be_off,
       current_setting('work_mem') AS work_mem_must_be_4MB;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.la_currency, la.la_account_number, '' as stop_interest_accrual,
 la.la_office_id, la.expected_disbursement_date
FROM mfi_accounting.loan_account la
WHERE la.loan_status IN ('ACTIVE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;
ROLLBACK;

SELECT '===== 6 ADVANCE_REPAYMENT baseline =====' AS section;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT DISTINCT la.la_account_number, la.la_currency, la.la_office_id, la.excess_amount, la.account_id, la.account_id
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.loan_installment_details lid ON lid.loan_account_id = la.account_id
WHERE (la.loan_status = 'ACTIVE') AND la.excess_amount > 0
  AND lid.installment_date <= CURRENT_DATE AND lid.is_part_prepayment_entry=false AND lid.is_settled=FALSE AND lid.is_deleted = FALSE
  AND la.account_id >= 2 AND la.account_id <= 2044302;

SELECT '===== 6 ADVANCE_REPAYMENT tuned =====' AS section;
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
SELECT current_setting('enable_nestloop') AS enable_nestloop_must_be_off,
       current_setting('yb_enable_batchednl') AS yb_batchednl_must_be_off,
       current_setting('yb_prefer_bnl') AS yb_prefer_bnl_must_be_off,
       current_setting('work_mem') AS work_mem_must_be_4MB;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT DISTINCT la.la_account_number, la.la_currency, la.la_office_id, la.excess_amount, la.account_id, la.account_id
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.loan_installment_details lid ON lid.loan_account_id = la.account_id
WHERE (la.loan_status = 'ACTIVE') AND la.excess_amount > 0
  AND lid.installment_date <= CURRENT_DATE AND lid.is_part_prepayment_entry=false AND lid.is_settled=FALSE AND lid.is_deleted = FALSE
  AND la.account_id >= 2 AND la.account_id <= 2044302;
ROLLBACK;

SELECT '===== 7 AUTO_CLOSURE baseline =====' AS section;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.la_account_number, la.account_id
FROM mfi_accounting.loan_account la
WHERE la.loan_status IN ('ACTIVE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;

SELECT '===== 7 AUTO_CLOSURE tuned =====' AS section;
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
SELECT current_setting('enable_nestloop') AS enable_nestloop_must_be_off,
       current_setting('yb_enable_batchednl') AS yb_batchednl_must_be_off,
       current_setting('yb_prefer_bnl') AS yb_prefer_bnl_must_be_off,
       current_setting('work_mem') AS work_mem_must_be_4MB;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.la_account_number, la.account_id
FROM mfi_accounting.loan_account la
WHERE la.loan_status IN ('ACTIVE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;
ROLLBACK;

SELECT '===== 8 DPD_CALC baseline =====' AS section;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.loan_product_id, la.past_due_days, a.account_number, a.currency,
 acs.criteria, acs.id, la.expected_disbursement_date, lp.product_id, la.loan_status, la.npa_ageing_start_date, a.office_id
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.account a ON a.id = la.account_id
 JOIN mfi_accounting.asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
 JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
 JOIN mfi_accounting.product_scheme ps ON ps.id = a.product_scheme_id
WHERE la.loan_status IN ('ACTIVE','FORECLOSURE_FREEZE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;

SELECT '===== 8 DPD_CALC tuned =====' AS section;
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
SELECT current_setting('enable_nestloop') AS enable_nestloop_must_be_off,
       current_setting('yb_enable_batchednl') AS yb_batchednl_must_be_off,
       current_setting('yb_prefer_bnl') AS yb_prefer_bnl_must_be_off,
       current_setting('work_mem') AS work_mem_must_be_4MB;
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT JSON)
SELECT la.account_id, la.loan_product_id, la.past_due_days, a.account_number, a.currency,
 acs.criteria, acs.id, la.expected_disbursement_date, lp.product_id, la.loan_status, la.npa_ageing_start_date, a.office_id
FROM mfi_accounting.loan_account la
 JOIN mfi_accounting.account a ON a.id = la.account_id
 JOIN mfi_accounting.asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
 JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
 JOIN mfi_accounting.product_scheme ps ON ps.id = a.product_scheme_id
WHERE la.loan_status IN ('ACTIVE','FORECLOSURE_FREEZE')
  AND la.account_id >= 2 AND la.account_id <= 2044302;
ROLLBACK;
