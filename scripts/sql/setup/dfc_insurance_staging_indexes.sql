-- Ops / QA / prod hot-apply (same as Flyway V000198) — run once per environment before peak DFC volume.
-- Schema: mfi_accounting (Yugabyte YSQL). Idempotent (IF NOT EXISTS).

CREATE INDEX IF NOT EXISTS idx_dfisd_dfc_inout_claim_status
  ON mfi_accounting.death_foreclosure_insurance_staging_details (death_foreclosure_details_id, inout_status, claim_status, status);

CREATE INDEX IF NOT EXISTS idx_dfisd_inout_claim_id
  ON mfi_accounting.death_foreclosure_insurance_staging_details (inout_status, claim_status, id);

CREATE INDEX IF NOT EXISTS idx_dfisd_claim_number_status
  ON mfi_accounting.death_foreclosure_insurance_staging_details (claim_number, claim_status);
