-- Bump past_due_days to NPA slab (61+) for loanAccountAssetCriteriaJob forward movement test.
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mfi_accounting._demo_npa_dpi_backup (
  account_id                BIGINT PRIMARY KEY,
  past_due_days             INT,
  asset_criteria_slabs_id   BIGINT,
  npa_tagging_date          TIMESTAMP,
  npa_ageing_start_date     TIMESTAMP,
  backed_up_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO mfi_accounting._demo_npa_dpi_backup (
  account_id, past_due_days, asset_criteria_slabs_id, npa_tagging_date, npa_ageing_start_date
)
SELECT la.account_id, la.past_due_days, la.asset_criteria_slabs_id, la.npa_tagging_date, la.npa_ageing_start_date
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint
ON CONFLICT (account_id) DO UPDATE SET
  past_due_days = EXCLUDED.past_due_days,
  asset_criteria_slabs_id = EXCLUDED.asset_criteria_slabs_id,
  npa_tagging_date = EXCLUDED.npa_tagging_date,
  npa_ageing_start_date = EXCLUDED.npa_ageing_start_date,
  backed_up_at = NOW();

UPDATE mfi_accounting.loan_account la
SET past_due_days = :target_past_due_days::int,
    asset_criteria_slabs_id = 1,
    npa_tagging_date = NULL,
    npa_ageing_start_date = NULL,
    updated_on = NOW(),
    updated_by = 'LOCAL_NPA_DPI_TEST'
WHERE la.account_id = :loan_account_id::bigint;

COMMIT;

\echo '=== NPA trigger state ==='
SELECT account_id, past_due_days, asset_criteria_slabs_id, npa_tagging_date
FROM mfi_accounting.loan_account
WHERE account_id = :loan_account_id::bigint;
