-- Local demo: only the target loan stays DPI-eligible for calc + booking.
-- Calc: zero past_due_days on other ACTIVE loans (existing).
-- Booking: soft-delete unposted dpi_accrual_details on other loans (DpiAccrualBookingItemReader
--   selects accrual_posting_date IS NULL AND total_accrued_amount > 0 — DPD alone does not shrink it).
-- Reversible via restore_dpd_portfolio.sql (snapshot-restore aware backup tables).
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mfi_accounting._demo_dpd_quarantine_backup (
  account_id      BIGINT PRIMARY KEY,
  past_due_days   INT NOT NULL,
  backed_up_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Also update existing backup rows so purge_local restore cannot revive stale DPD forever.
INSERT INTO mfi_accounting._demo_dpd_quarantine_backup (account_id, past_due_days)
SELECT la.account_id, la.past_due_days
FROM mfi_accounting.loan_account la
WHERE la.account_id <> :loan_account_id::bigint
  AND la.past_due_days > 0
  AND la.loan_status = 'ACTIVE'
ON CONFLICT (account_id) DO UPDATE
  SET past_due_days = EXCLUDED.past_due_days, backed_up_at = NOW();

UPDATE mfi_accounting.loan_account la
SET past_due_days = 0,
    updated_on = NOW(),
    updated_by = 'DEMO_DPD_QUARANTINE'
WHERE la.account_id <> :loan_account_id::bigint
  AND la.past_due_days > 0
  AND la.loan_status = 'ACTIVE';

-- Booking quarantine: park non-fixture unposted accruals (reversible).
CREATE TABLE IF NOT EXISTS mfi_accounting._demo_dpi_booking_quarantine_backup (
  accrual_id      BIGINT PRIMARY KEY,
  loan_account_id BIGINT NOT NULL,
  backed_up_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO mfi_accounting._demo_dpi_booking_quarantine_backup (accrual_id, loan_account_id)
SELECT da.id, da.loan_account_id
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_account la ON la.account_id = da.loan_account_id
WHERE da.loan_account_id <> :loan_account_id::bigint
  AND da.is_deleted = false
  AND da.accrual_posting_date IS NULL
  AND da.total_accrued_amount > 0
  AND la.loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE')
ON CONFLICT (accrual_id) DO UPDATE
  SET loan_account_id = EXCLUDED.loan_account_id, backed_up_at = NOW();

UPDATE mfi_accounting.dpi_accrual_details da
SET is_deleted = true
FROM mfi_accounting._demo_dpi_booking_quarantine_backup b
WHERE da.id = b.accrual_id
  AND da.is_deleted = false;

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

\echo '=== Booking quarantine (unposted accruals eligible for dpiAccrualBooking) ==='
SELECT COUNT(DISTINCT da.loan_account_id) AS booking_eligible_loans,
       COUNT(*) AS booking_eligible_rows
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_account la ON la.account_id = da.loan_account_id
WHERE da.is_deleted = false
  AND da.accrual_posting_date IS NULL
  AND da.total_accrued_amount > 0
  AND la.loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE');
