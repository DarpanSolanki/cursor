-- Local schema guard: mfi_accounting.loan_account.dpi_suspense_amount
-- Author: DarpanSolanki <darpan@novopay.in>
--
-- WHY: accounting mfi_integration_v3.7.1 code references loan_account.dpi_suspense_amount
--   (LoanAccountEntity.dpiSuspenseAmount; NPA asset-criteria + repayment reverse-movement path),
--   but NO Flyway migration on the 3.7.1 train adds this column. V000001 creates only
--   interest_suspense_amount; the DPI migrations (V000187..V000195) never add dpi_suspense_amount.
--   A fresh local DB therefore lacks it and DPI/foreclosure flows fail on the missing column.
--
-- SCOPE: LOCAL Yugabyte only (127.0.0.1:5433). Idempotent (IF NOT EXISTS). Mirrors
--   interest_suspense_amount type numeric(20,6). Not tracked in flyway_schema_history
--   (hot-apply guard for local reproducibility after teardown).
--
-- RELEASE FLAG: This is a genuine 3.7.1 migration gap. A proper Flyway migration
--   (ALTER TABLE loan_account ADD COLUMN dpi_suspense_amount) must be authored on the
--   initial-setup 3.7.1 train + a prod deploy pack generated (prod runs manual DDL).

ALTER TABLE mfi_accounting.loan_account
    ADD COLUMN IF NOT EXISTS dpi_suspense_amount numeric(20,6);
