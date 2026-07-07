-- DCF fixture prep: remove accrual-unbacked phantom PINT rows (due_amount=100 with no penal_interest_accrual).
-- Symptom: child closes with 100 PINT pending after DFC when billed PINT > accrued penal.
-- Safe when SUM(loan_due_details PINT due) > SUM(penal_interest_accrual_details) for the loan.
-- Usage: psql ... -v parent_lan=6000137433 -f scripts/sql/setup/local_setup_dcf_fixture_penal_reconcile.sql

\set ON_ERROR_STOP on

UPDATE mfi_accounting.loan_due_details ldd
SET is_deleted = true, updated_on = NOW(), updated_by = 'DCF_FIXTURE_PREP'
FROM mfi_accounting.loan_account la
WHERE la.account_id = ldd.loan_account_id
  AND la.parent_loan_account_id = (SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number = :'parent_lan')
  AND ldd.component_type = 'PINT'
  AND ldd.due_amount = 100
  AND COALESCE(ldd.is_deleted, false) = false
  AND (
    SELECT COALESCE(SUM(d.due_amount), 0)
    FROM mfi_accounting.loan_due_details d
    WHERE d.loan_account_id = la.account_id AND d.component_type = 'PINT' AND COALESCE(d.is_deleted, false) = false
  ) > (
    SELECT COALESCE(SUM(pia.total_accrued_amount), 0)
    FROM mfi_accounting.penal_interest_accrual_details pia
    WHERE pia.loan_account_id = la.account_id
  );
