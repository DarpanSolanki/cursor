-- Local demo: only the target loan stays DPI-eligible (past_due_days > 0).
-- Other ACTIVE loans are zeroed so dpiAccrualCalculation scans 1 account, not ~2000.
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mfi_accounting._demo_dpd_quarantine_backup (
  account_id      BIGINT PRIMARY KEY,
  past_due_days   INT NOT NULL,
  backed_up_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO mfi_accounting._demo_dpd_quarantine_backup (account_id, past_due_days)
SELECT la.account_id, la.past_due_days
FROM mfi_accounting.loan_account la
WHERE la.account_id <> :loan_account_id::bigint
  AND la.past_due_days > 0
  AND la.loan_status = 'ACTIVE'
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting._demo_dpd_quarantine_backup b
    WHERE b.account_id = la.account_id
  );

UPDATE mfi_accounting.loan_account la
SET past_due_days = 0,
    updated_on = NOW(),
    updated_by = 'DEMO_DPD_QUARANTINE'
WHERE la.account_id <> :loan_account_id::bigint
  AND la.past_due_days > 0
  AND la.loan_status = 'ACTIVE';

COMMIT;

\echo '=== DPD quarantine (eligible loans for DPI calc) ==='
SELECT COUNT(*) AS eligible_loans
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency
 AND psfd.is_deleted = false
WHERE la.loan_status = 'ACTIVE'
  AND la.past_due_days > 0
  AND la.repayment_frequency = 'MONTHLY'
  AND psfd.dpi_applicable = 'YES';
