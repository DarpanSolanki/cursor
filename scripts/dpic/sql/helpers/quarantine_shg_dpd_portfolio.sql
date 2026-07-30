-- Local demo: only SHG parent + its children stay DPI-eligible (calc DPD + booking unposted).
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

CREATE TABLE IF NOT EXISTS mfi_accounting._demo_dpi_booking_quarantine_backup (
  accrual_id      BIGINT PRIMARY KEY,
  loan_account_id BIGINT NOT NULL,
  backed_up_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO mfi_accounting._demo_dpi_booking_quarantine_backup (accrual_id, loan_account_id)
SELECT da.id, da.loan_account_id
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_account la ON la.account_id = da.loan_account_id
WHERE da.is_deleted = false
  AND da.accrual_posting_date IS NULL
  AND da.total_accrued_amount > 0
  AND la.loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE')
  AND da.loan_account_id <> :parent_loan_account_id::bigint
  AND COALESCE(la.parent_loan_account_id, -1) <> :parent_loan_account_id::bigint
ON CONFLICT (accrual_id) DO UPDATE
  SET loan_account_id = EXCLUDED.loan_account_id, backed_up_at = NOW();

UPDATE mfi_accounting.dpi_accrual_details da
SET is_deleted = true
FROM mfi_accounting._demo_dpi_booking_quarantine_backup b
WHERE da.id = b.accrual_id
  AND da.is_deleted = false;

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

\echo '=== SHG booking quarantine eligible loans ==='
SELECT COUNT(DISTINCT da.loan_account_id) AS booking_eligible_loans
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_account la ON la.account_id = da.loan_account_id
WHERE da.is_deleted = false
  AND da.accrual_posting_date IS NULL
  AND da.total_accrued_amount > 0
  AND la.loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE');
