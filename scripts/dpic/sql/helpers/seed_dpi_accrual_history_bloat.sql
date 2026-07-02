-- Local-only: insert synthetic POSTED dpi_accrual_details rows to simulate table growth
-- (full-history scans slow down; narrow preload should stay flat).
--
-- Usage:
--   psql ... -v ON_ERROR_STOP=1 \
--     -v history_rows_per_loan=50 \
--     -f scripts/dpic/sql/helpers/seed_dpi_accrual_history_bloat.sql
--
-- Targets loans in _dpi_perf_selected. Run AFTER seed_dpi_batch_perf_portfolio.sql.

\set ON_ERROR_STOP on

BEGIN;

INSERT INTO mfi_accounting.dpi_accrual_details (
  loan_account_id, installment_id, base_amount, start_date, end_date,
  dpi_annual_rate, days_in_year, total_accrued_amount, carry_over_amount,
  accrual_posting_date, billing_posting_date, is_deleted
)
SELECT
  s.account_id,
  lid.id,
  1000.00,
  (DATE '2020-01-01' + (g.i || ' days')::interval)::date,
  (DATE '2020-01-02' + (g.i || ' days')::interval)::date,
  24.00,
  365,
  1,
  0,
  (DATE '2020-01-02' + (g.i || ' days')::interval)::date,
  (DATE '2020-01-03' + (g.i || ' days')::interval)::date,
  false
FROM mfi_accounting._dpi_perf_selected s
CROSS JOIN generate_series(1, :history_rows_per_loan::int) AS g(i)
JOIN LATERAL (
  SELECT lid.id
  FROM mfi_accounting.loan_installment_details lid
  WHERE lid.loan_account_id = s.account_id
    AND lid.is_deleted = false
  ORDER BY lid.installment_date
  LIMIT 1
) lid ON true;

COMMIT;

\echo '=== accrual history bloat ==='
SELECT COUNT(*) AS total_active_rows
FROM mfi_accounting.dpi_accrual_details
WHERE is_deleted = false;

SELECT COUNT(*) AS bloat_rows_on_perf_loans
FROM mfi_accounting.dpi_accrual_details dad
WHERE dad.is_deleted = false
  AND dad.loan_account_id IN (SELECT account_id FROM mfi_accounting._dpi_perf_selected)
  AND dad.accrual_posting_date IS NOT NULL;
