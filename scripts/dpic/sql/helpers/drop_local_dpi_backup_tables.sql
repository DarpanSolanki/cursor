-- Drop agent-created backup / scratch tables in mfi_accounting (local only).
\set ON_ERROR_STOP on

DROP TABLE IF EXISTS mfi_accounting._demo_dpd_quarantine_backup;
DROP TABLE IF EXISTS mfi_accounting._demo_npa_dpi_backup;
DROP TABLE IF EXISTS mfi_accounting._dpi_emi_first_backup;
DROP TABLE IF EXISTS mfi_accounting._dpi_perf_loan_dpd_backup;
DROP TABLE IF EXISTS mfi_accounting._dpi_perf_psfd_backup;
DROP TABLE IF EXISTS mfi_accounting._dpi_perf_selected;
DROP TABLE IF EXISTS mfi_accounting._dpi_synthetic_loan_map;
DROP TABLE IF EXISTS mfi_accounting._grace_e2e_psfd_backup;
DROP TABLE IF EXISTS mfi_accounting._qa1_month_end_npa_backup;
DROP TABLE IF EXISTS mfi_accounting._qa1_month_end_regular_backup;

\echo '=== backup tables dropped ==='
SELECT tablename
FROM pg_tables
WHERE schemaname = 'mfi_accounting' AND tablename LIKE '\_%' ESCAPE '\'
ORDER BY 1;
