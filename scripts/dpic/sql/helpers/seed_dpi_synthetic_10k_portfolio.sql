-- Local-only: minimal-template LAN factory for DPI batch perf (10k+ when real pool ~2k).
-- One golden loan → account + loan_account + 1 overdue installment + PRIN/INT dues (~6 rows/loan).
-- Full schedule clone avoided (~2.6k dues/loan blows temp_file_limit).
--
-- Usage:
--   psql ... -v ON_ERROR_STOP=1 -v target_count=10000 -v product_scheme_id=48 \
--     -v past_due_days=45 \
--     -f scripts/dpic/sql/helpers/seed_dpi_synthetic_10k_portfolio.sql
--
-- Restore: restore_dpi_synthetic_10k_portfolio.sql

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mfi_accounting._dpi_synthetic_loan_map (
  new_account_id    BIGINT PRIMARY KEY,
  source_account_id BIGINT NOT NULL,
  copy_index        INT NOT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DELETE FROM mfi_accounting._dpi_synthetic_loan_map;

CREATE TEMP TABLE _dpi_plan (
  new_account_id BIGINT PRIMARY KEY,
  seq            INT NOT NULL,
  source_account_id BIGINT NOT NULL
) ON COMMIT DROP;

INSERT INTO _dpi_plan (new_account_id, seq, source_account_id)
SELECT nextval('mfi_accounting.account_id_seq'), gs.i, tpl.account_id
FROM generate_series(1, :target_count::int) AS gs(i)
CROSS JOIN LATERAL (
  SELECT la.account_id
  FROM mfi_accounting.loan_account la
  WHERE la.loan_status = 'ACTIVE'
    AND la.is_deleted = false
    AND la.la_product_scheme_id = :product_scheme_id::bigint
    AND EXISTS (
      SELECT 1 FROM mfi_accounting.loan_due_details ldd
      WHERE ldd.loan_account_id = la.account_id AND ldd.is_deleted = false
        AND ldd.component_type IN ('PRIN', 'INT')
        AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
    )
  ORDER BY la.account_id
  LIMIT 1
) tpl;

INSERT INTO mfi_accounting._dpi_synthetic_loan_map (new_account_id, source_account_id, copy_index)
SELECT new_account_id, source_account_id, seq FROM _dpi_plan;

INSERT INTO mfi_accounting.account (
  id, office_id, product_scheme_id, type, account_number, currency, opening_date, closing_date,
  status, blocked, created_on, created_by, updated_on, updated_by, approved_on, approved_by,
  office_code, is_deleted, parent_account_id
)
SELECT p.new_account_id, a.office_id, a.product_scheme_id, a.type,
       ('SYN' || p.new_account_id::text), a.currency, a.opening_date, a.closing_date,
       a.status, a.blocked, NOW(), 'DPI_SYN_MIN', NOW(), 'DPI_SYN_MIN',
       a.approved_on, a.approved_by, a.office_code, false, a.parent_account_id
FROM _dpi_plan p
JOIN mfi_accounting.account a ON a.id = p.source_account_id;

INSERT INTO mfi_accounting.loan_account (
  account_id, loan_product_id, customer_id, approved_amount, term, term_unit, purpose,
  expected_disbursement_date, actual_first_repayment_date, first_repayment_date, repayment_frequency,
  first_interest_payment_date, interest_frequency, interest_calculation_basis, maturity_date,
  number_of_installments, loan_amount, disbursed_amount, cross_sell_amount, past_due_days,
  asset_criteria_group_id, asset_criteria_slabs_id, npa_ageing_start_date, npa_ageing_days,
  asset_classification_slabs_id, npa_tagging_date, interest_suspense_amount, overdue_amount,
  excess_amount, broken_period_interest_amount, excess_interest_amount, loan_status, cancelled_on,
  disbursement_status, external_ref_number, refund_allowed, enach_bounce_count, net_off_account,
  net_off_amount, is_external_net_off_acnt, noc_document_id, requested_loan_amount, is_sec_npa,
  sec_npa_stamping_date, sec_npa_reporting_date, sec_npa_asset_classification, delinq_string,
  updated_on, updated_by, created_on, created_by, approved_on, approved_by, refund_remarks,
  is_deleted, filler_1, filler_2, filler_3, filler_4, filler_5, filler_6, filler_7, filler_8,
  filler_9, filler_10, sec_npa_tagging_date, fraction, parent_loan_account_id, has_child_accounts,
  sanction_date, filler_11, sourcing_emp_id, servicing_emp_id, la_account_number, la_office_id,
  la_office_code, la_product_scheme_id, la_currency, la_opening_date, la_closing_date,
  reinit_disbursement_status, reinit_external_error_code, reinit_external_error_message
)
SELECT
  p.new_account_id, la.loan_product_id, la.customer_id,
  la.approved_amount + (p.seq % 50) * 1000.0, la.term, la.term_unit, la.purpose,
  la.expected_disbursement_date, la.actual_first_repayment_date, la.first_repayment_date, la.repayment_frequency,
  la.first_interest_payment_date, la.interest_frequency, la.interest_calculation_basis, la.maturity_date,
  la.number_of_installments,
  la.loan_amount + (p.seq % 50) * 1000.0, la.disbursed_amount, la.cross_sell_amount,
  :past_due_days::int,
  la.asset_criteria_group_id, la.asset_criteria_slabs_id, la.npa_ageing_start_date, la.npa_ageing_days,
  la.asset_classification_slabs_id, la.npa_tagging_date, la.interest_suspense_amount, la.overdue_amount,
  la.excess_amount, la.broken_period_interest_amount, la.excess_interest_amount, la.loan_status, la.cancelled_on,
  la.disbursement_status, ('SYN_PERF_' || p.new_account_id::text), la.refund_allowed, la.enach_bounce_count,
  la.net_off_account, la.net_off_amount, la.is_external_net_off_acnt, la.noc_document_id, la.requested_loan_amount,
  la.is_sec_npa, la.sec_npa_stamping_date, la.sec_npa_reporting_date, la.sec_npa_asset_classification,
  la.delinq_string, NOW(), 'DPI_SYN_MIN', NOW(), 'DPI_SYN_MIN', la.approved_on, la.approved_by,
  la.refund_remarks, false, la.filler_1, la.filler_2, la.filler_3, la.filler_4, la.filler_5, la.filler_6,
  la.filler_7, la.filler_8, la.filler_9, la.filler_10, la.sec_npa_tagging_date, la.fraction,
  la.parent_loan_account_id, la.has_child_accounts, la.sanction_date, la.filler_11, la.sourcing_emp_id,
  la.servicing_emp_id, ('SYNLAN' || p.new_account_id::text), la.la_office_id, la.la_office_code,
  la.la_product_scheme_id, la.la_currency, la.la_opening_date, la.la_closing_date,
  la.reinit_disbursement_status, la.reinit_external_error_code, la.reinit_external_error_message
FROM _dpi_plan p
JOIN mfi_accounting.loan_account la ON la.account_id = p.source_account_id;

INSERT INTO mfi_accounting.account_interest_details (
  account_id, spread, interest_setup_id, base_interest_master_id, interest_rate_type, effective_rate,
  penal_rate, upfront_interest_applicable, upfront_interest_period, upfront_interest_amount,
  updated_on, updated_by, created_by, created_on
)
SELECT p.new_account_id, aid.spread, aid.interest_setup_id, aid.base_interest_master_id, aid.interest_rate_type,
       aid.effective_rate, aid.penal_rate, aid.upfront_interest_applicable, aid.upfront_interest_period,
       aid.upfront_interest_amount, NOW(), 'DPI_SYN_MIN', 'DPI_SYN_MIN', NOW()
FROM _dpi_plan p
JOIN mfi_accounting.account_interest_details aid ON aid.account_id = p.source_account_id;

CREATE TEMP TABLE _dpi_new_inst (
  installment_id  BIGINT NOT NULL,
  loan_account_id BIGINT NOT NULL
) ON COMMIT DROP;

WITH tpl_inst AS (
  SELECT lid.*
  FROM mfi_accounting.loan_installment_details lid
  JOIN _dpi_plan p ON p.source_account_id = lid.loan_account_id
  WHERE lid.is_deleted = false
  ORDER BY lid.overdue_date DESC NULLS LAST, lid.serial_number
  LIMIT 1
)
INSERT INTO mfi_accounting.loan_installment_details (
  loan_account_id, schedule_number, serial_number, rate_of_interest, installment_date,
  installment_amount, overdue_date, settled_amount, last_paid_date, is_settled,
  is_penal_fee_computed, is_part_prepayment_entry, created_on, created_by, updated_on, updated_by, is_deleted
)
SELECT p.new_account_id, ti.schedule_number, ti.serial_number, ti.rate_of_interest, ti.installment_date,
       ti.installment_amount + (p.seq % 20) * 10.0, ti.overdue_date, 0, NULL, false,
       ti.is_penal_fee_computed, ti.is_part_prepayment_entry, NOW(), 'DPI_SYN_MIN', NOW(), 'DPI_SYN_MIN', false
FROM _dpi_plan p
CROSS JOIN tpl_inst ti;

INSERT INTO _dpi_new_inst (installment_id, loan_account_id)
SELECT lid.id, lid.loan_account_id
FROM mfi_accounting.loan_installment_details lid
JOIN _dpi_plan p ON p.new_account_id = lid.loan_account_id
WHERE lid.is_deleted = false AND lid.created_by = 'DPI_SYN_MIN';

WITH tpl_due AS (
  SELECT ldd.component_type, ldd.charge_code, ldd.charge_rate, ldd.charge_fixed_amount, ldd.base_amount,
         ldd.due_date, ldd.overdue_date, ldd.due_amount, ldd.paid_amount, ldd.waived_amount
  FROM mfi_accounting.loan_due_details ldd
  JOIN _dpi_plan p ON p.source_account_id = ldd.loan_account_id
  WHERE ldd.is_deleted = false AND ldd.component_type IN ('PRIN', 'INT')
    AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
  ORDER BY ldd.overdue_date DESC
  LIMIT 2
)
INSERT INTO mfi_accounting.loan_due_details (
  loan_account_id, component_type, charge_code, charge_rate, charge_fixed_amount, base_amount,
  due_date, overdue_date, due_amount, paid_amount, waived_amount, loan_installment_details_id,
  created_on, created_by, updated_on, updated_by, is_deleted
)
SELECT ni.loan_account_id, td.component_type, td.charge_code, td.charge_rate, td.charge_fixed_amount,
       td.base_amount, td.due_date, td.overdue_date,
       td.due_amount + (p.seq % 10) * 5.0, 0, 0, ni.installment_id,
       NOW(), 'DPI_SYN_MIN', NOW(), 'DPI_SYN_MIN', false
FROM _dpi_new_inst ni
JOIN _dpi_plan p ON p.new_account_id = ni.loan_account_id
CROSS JOIN tpl_due td;

COMMIT;

\echo '=== synthetic minimal portfolio ==='
SELECT COUNT(*) AS synthetic_loans FROM mfi_accounting._dpi_synthetic_loan_map;
SELECT COUNT(*) AS synthetic_installments
FROM mfi_accounting.loan_installment_details WHERE created_by = 'DPI_SYN_MIN' AND is_deleted = false;
SELECT COUNT(*) AS synthetic_dues
FROM mfi_accounting.loan_due_details WHERE created_by = 'DPI_SYN_MIN' AND is_deleted = false;
