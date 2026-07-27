-- SP-329: before/after EXPLAIN for EOD JdbcCursorItemReader SQLs (read-only).
-- Usage (example QA3):
--   sed -e 's/:min_id/11158/g' -e 's/:max_id/11983461/g' -e "s/:biz_date/'2026-07-21'/g" \
--     scripts/sql/adhoc/sp329_batch_reader_nestloop_explain.sql | \
--     bash -c 'source scripts/db/env/qa3.env; export PGPASSWORD; psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -f -'
-- GUCs: enable_nestloop, yb_enable_batchednl, yb_prefer_bnl, work_mem (verified on QA3/QA6 2026-07-21).
-- No yb_nestedloop GUC exists on those envs.
-- work_mem default in NestloopDisabledJdbcCursorItemReader is 4MB (matches prod) (override BATCH_READER_WORK_MEM).

-- SP-329 Phase 0: reader EXPLAIN before/after nestloop disable
-- Params substituted by runner: :min_id :max_id :biz_date
SET search_path TO mfi_accounting;

\echo ===== 1 INTEREST_ACCRUAL_CALC baseline =====
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.la_currency, la.expected_disbursement_date, acs.stop_interest_accrual,
 la.asset_classification_slabs_id, lp.product_id, la.la_account_number, la.la_office_id, la.interest_calculation_basis, la.approved_amount,
 la.interest_frequency, ps.interest_calculation_days_in_month, ps.interest_calculation_days_in_year, la.maturity_date, la.first_repayment_date, lp.interest_rounding_factor
FROM loan_account la
 JOIN loan_product lp ON la.loan_product_id = lp.id
 JOIN product_scheme ps ON la.la_product_scheme_id = ps.id
 JOIN loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id AND lpac.is_deleted = false
 JOIN asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
  AND lpac.asset_criteria_slab_id = la.asset_criteria_slabs_id
WHERE (la.loan_status = 'ACTIVE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;

\echo ===== 1 INTEREST_ACCRUAL_CALC tuned SET LOCAL =====
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.la_currency, la.expected_disbursement_date, acs.stop_interest_accrual,
 la.asset_classification_slabs_id, lp.product_id, la.la_account_number, la.la_office_id, la.interest_calculation_basis, la.approved_amount,
 la.interest_frequency, ps.interest_calculation_days_in_month, ps.interest_calculation_days_in_year, la.maturity_date, la.first_repayment_date, lp.interest_rounding_factor
FROM loan_account la
 JOIN loan_product lp ON la.loan_product_id = lp.id
 JOIN product_scheme ps ON la.la_product_scheme_id = ps.id
 JOIN loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id AND lpac.is_deleted = false
 JOIN asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
  AND lpac.asset_criteria_slab_id = la.asset_criteria_slabs_id
WHERE (la.loan_status = 'ACTIVE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;
ROLLBACK;

\echo ===== 1b INTEREST_ACCRUAL_CALC inline hint =====
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT /*+ Set(enable_nestloop off) Set(yb_enable_batchednl off) Set(yb_prefer_bnl off) */ la.account_id, la.la_currency, la.expected_disbursement_date, acs.stop_interest_accrual,
 la.asset_classification_slabs_id, lp.product_id, la.la_account_number, la.la_office_id, la.interest_calculation_basis, la.approved_amount,
 la.interest_frequency, ps.interest_calculation_days_in_month, ps.interest_calculation_days_in_year, la.maturity_date, la.first_repayment_date, lp.interest_rounding_factor
FROM loan_account la
 JOIN loan_product lp ON la.loan_product_id = lp.id
 JOIN product_scheme ps ON la.la_product_scheme_id = ps.id
 JOIN loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id AND lpac.is_deleted = false
 JOIN asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
  AND lpac.asset_criteria_slab_id = la.asset_criteria_slabs_id
WHERE (la.loan_status = 'ACTIVE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;

\echo ===== 2 INTEREST_ACCRUAL_BOOKING baseline =====
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.la_currency, la.interest_frequency, la.la_account_number,
 la.asset_classification_slabs_id, acs.stop_interest_accrual,
 la.la_office_id, lp.id, lp.product_id, la.npa_ageing_start_date, la.sec_npa_tagging_date
FROM loan_account la
 JOIN loan_product lp ON la.loan_product_id = lp.id
 JOIN product_scheme ps ON la.la_product_scheme_id = ps.id
 JOIN loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id AND lpac.is_deleted = false
 JOIN asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
  AND lpac.asset_criteria_slab_id = la.asset_criteria_slabs_id
WHERE (la.loan_status = 'ACTIVE' OR la.loan_status = 'FORECLOSURE_FREEZE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;

\echo ===== 2 INTEREST_ACCRUAL_BOOKING tuned =====
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.la_currency, la.interest_frequency, la.la_account_number,
 la.asset_classification_slabs_id, acs.stop_interest_accrual,
 la.la_office_id, lp.id, lp.product_id, la.npa_ageing_start_date, la.sec_npa_tagging_date
FROM loan_account la
 JOIN loan_product lp ON la.loan_product_id = lp.id
 JOIN product_scheme ps ON la.la_product_scheme_id = ps.id
 JOIN loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id AND lpac.is_deleted = false
 JOIN asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
  AND lpac.asset_criteria_slab_id = la.asset_criteria_slabs_id
WHERE (la.loan_status = 'ACTIVE' OR la.loan_status = 'FORECLOSURE_FREEZE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;
ROLLBACK;

\echo ===== 3 PENAL_CALC baseline =====
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.la_currency, la.expected_disbursement_date, 'false' AS stop_interest_accrual,
 la.asset_classification_slabs_id, lp.product_id, la.la_account_number, la.la_office_id, la.interest_calculation_basis, la.approved_amount,
 la.interest_frequency, ps.interest_calculation_days_in_month, ps.interest_calculation_days_in_year, la.maturity_date, la.first_repayment_date
FROM loan_account la
 JOIN loan_product lp ON la.loan_product_id = lp.id
 JOIN product_scheme ps ON la.la_product_scheme_id = ps.id
WHERE (la.loan_status = 'ACTIVE') AND la.past_due_days > 0
  AND la.account_id >= :min_id AND la.account_id <= :max_id;

\echo ===== 3 PENAL_CALC tuned =====
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.la_currency, la.expected_disbursement_date, 'false' AS stop_interest_accrual,
 la.asset_classification_slabs_id, lp.product_id, la.la_account_number, la.la_office_id, la.interest_calculation_basis, la.approved_amount,
 la.interest_frequency, ps.interest_calculation_days_in_month, ps.interest_calculation_days_in_year, la.maturity_date, la.first_repayment_date
FROM loan_account la
 JOIN loan_product lp ON la.loan_product_id = lp.id
 JOIN product_scheme ps ON la.la_product_scheme_id = ps.id
WHERE (la.loan_status = 'ACTIVE') AND la.past_due_days > 0
  AND la.account_id >= :min_id AND la.account_id <= :max_id;
ROLLBACK;

\echo ===== 4 PENAL_BOOKING baseline =====
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT pia.loan_account_id, pia.installment_id, pia.overdue_date, pia.base_amount, pia.charge_code,
 pia.charge_fixed_amount, pia.penal_rate, pia.total_accrued_amount, pia.id, la.account_id, pia.start_date, pia.end_date, la.has_child_accounts
FROM penal_interest_accrual_details pia
 JOIN loan_account la ON la.account_id = pia.loan_account_id
WHERE pia.accrual_posting_date IS NULL AND la.loan_status = 'ACTIVE'
  AND la.account_id >= :min_id AND la.account_id <= :max_id;

\echo ===== 4 PENAL_BOOKING tuned =====
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT pia.loan_account_id, pia.installment_id, pia.overdue_date, pia.base_amount, pia.charge_code,
 pia.charge_fixed_amount, pia.penal_rate, pia.total_accrued_amount, pia.id, la.account_id, pia.start_date, pia.end_date, la.has_child_accounts
FROM penal_interest_accrual_details pia
 JOIN loan_account la ON la.account_id = pia.loan_account_id
WHERE pia.accrual_posting_date IS NULL AND la.loan_status = 'ACTIVE'
  AND la.account_id >= :min_id AND la.account_id <= :max_id;
ROLLBACK;

\echo ===== 5 BILLING baseline =====
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.la_currency, la.la_account_number, '' as stop_interest_accrual,
 la.la_office_id, la.expected_disbursement_date
FROM loan_account la
WHERE la.loan_status IN ('ACTIVE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;

\echo ===== 5 BILLING tuned =====
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.la_currency, la.la_account_number, '' as stop_interest_accrual,
 la.la_office_id, la.expected_disbursement_date
FROM loan_account la
WHERE la.loan_status IN ('ACTIVE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;
ROLLBACK;

\echo ===== 6 ADVANCE_REPAYMENT baseline =====
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT DISTINCT la.la_account_number, la.la_currency, la.la_office_id, la.excess_amount, la.account_id, la.account_id
FROM loan_account la
 JOIN loan_installment_details lid ON lid.loan_account_id = la.account_id
WHERE (la.loan_status = 'ACTIVE') AND la.excess_amount > 0
  AND lid.installment_date <= DATE(:biz_date) AND lid.is_part_prepayment_entry=false AND lid.is_settled=FALSE AND lid.is_deleted = FALSE
  AND la.account_id >= :min_id AND la.account_id <= :max_id;

\echo ===== 6 ADVANCE_REPAYMENT tuned =====
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT DISTINCT la.la_account_number, la.la_currency, la.la_office_id, la.excess_amount, la.account_id, la.account_id
FROM loan_account la
 JOIN loan_installment_details lid ON lid.loan_account_id = la.account_id
WHERE (la.loan_status = 'ACTIVE') AND la.excess_amount > 0
  AND lid.installment_date <= DATE(:biz_date) AND lid.is_part_prepayment_entry=false AND lid.is_settled=FALSE AND lid.is_deleted = FALSE
  AND la.account_id >= :min_id AND la.account_id <= :max_id;
ROLLBACK;

\echo ===== 7 AUTO_CLOSURE baseline =====
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.la_account_number, la.account_id
FROM loan_account la
WHERE la.loan_status IN ('ACTIVE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;

\echo ===== 7 AUTO_CLOSURE tuned =====
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.la_account_number, la.account_id
FROM loan_account la
WHERE la.loan_status IN ('ACTIVE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;
ROLLBACK;

\echo ===== 8 DPD_CALC baseline =====
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.loan_product_id, la.past_due_days, a.account_number, a.currency,
 acs.criteria, acs.id, la.expected_disbursement_date, lp.product_id, la.loan_status, la.npa_ageing_start_date, a.office_id
FROM loan_account la
 JOIN account a ON a.id = la.account_id
 JOIN asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
 JOIN loan_product lp ON lp.id = la.loan_product_id
 JOIN product_scheme ps ON ps.id = a.product_scheme_id
WHERE la.loan_status IN ('ACTIVE','FORECLOSURE_FREEZE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;

\echo ===== 8 DPD_CALC tuned =====
BEGIN;
SET LOCAL enable_nestloop = off;
SET LOCAL yb_enable_batchednl = off;
SET LOCAL yb_prefer_bnl = off;
SET LOCAL work_mem = '4MB';
EXPLAIN (ANALYZE, BUFFERS, COSTS, FORMAT TEXT)
SELECT la.account_id, la.loan_product_id, la.past_due_days, a.account_number, a.currency,
 acs.criteria, acs.id, la.expected_disbursement_date, lp.product_id, la.loan_status, la.npa_ageing_start_date, a.office_id
FROM loan_account la
 JOIN account a ON a.id = la.account_id
 JOIN asset_criteria_slabs acs ON acs.id = la.asset_criteria_slabs_id
 JOIN loan_product lp ON lp.id = la.loan_product_id
 JOIN product_scheme ps ON ps.id = a.product_scheme_id
WHERE la.loan_status IN ('ACTIVE','FORECLOSURE_FREEZE')
  AND la.account_id >= :min_id AND la.account_id <= :max_id;
ROLLBACK;
