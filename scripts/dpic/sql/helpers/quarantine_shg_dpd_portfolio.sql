-- Local demo: only SHG parent + its children stay DPI-eligible (past_due_days > 0).
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
WHERE la.past_due_days > 0
  AND la.loan_status = 'ACTIVE'
  AND la.account_id <> :parent_loan_account_id::bigint
  AND COALESCE(la.parent_loan_account_id, -1) <> :parent_loan_account_id::bigint
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting._demo_dpd_quarantine_backup b
    WHERE b.account_id = la.account_id
  );

UPDATE mfi_accounting.loan_account la
SET past_due_days = 0,
    updated_on = NOW(),
    updated_by = 'SHG_DPD_QUARANTINE'
WHERE la.past_due_days > 0
  AND la.loan_status = 'ACTIVE'
  AND la.account_id <> :parent_loan_account_id::bigint
  AND COALESCE(la.parent_loan_account_id, -1) <> :parent_loan_account_id::bigint;

COMMIT;

\echo '=== SHG DPD quarantine eligible ==='
SELECT la.account_id, a.account_number, la.past_due_days
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency
 AND psfd.is_deleted = false
WHERE la.loan_status = 'ACTIVE'
  AND la.past_due_days > 0
  AND psfd.dpi_applicable = 'YES'
  AND (la.account_id = :parent_loan_account_id::bigint
       OR la.parent_loan_account_id = :parent_loan_account_id::bigint)
ORDER BY la.account_id;
