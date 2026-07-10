-- Local QA only (Yugabyte / PostgreSQL, schema mfi_accounting).
--
-- Purpose: force a loan into a specific retry stage by:
-- - setting loan_account.disbursement_status
-- - clearing utr_number (so NEFT is re-attempted when appropriate)
-- - optionally soft-archiving CRR rows for selected transaction types (so service does not "see" prior SUCCESS)
--
-- This is intentionally surgical (per LAN) and additive to the main reset script.
--
-- Required psql variables (pass via -v):
--   lan                 — account.account_number of the target loan (required)
--   target_disb_status  — loan_account.disbursement_status to set (required)
--   archive_gl          — 'true' or 'false' (archive DISB_GL_CBS_INTEGRATION + NETOFF rows for this LAN)
--   archive_neft        — 'true' or 'false' (archive DISBURSEMENT_NEFT rows for this LAN)
--   archive_mft         — 'true' or 'false' (archive DISBURSEMENT_MFT rows for this LAN)
--
-- Usage:
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
--     -v lan='6001937616' -v target_disb_status='DTFC_SUCCESS' -v archive_gl='false' -v archive_neft='true' -v archive_mft='false' \
--     -f scripts/sql/utility/local_force_disburse_stage_for_retry_mfi_yugabyte.sql

BEGIN;
SET search_path TO mfi_accounting;

-- Resolve account_id
WITH tgt AS (
  SELECT la.account_id
  FROM loan_account la
  JOIN account a ON a.id = la.account_id
  WHERE a.account_number = btrim(:'lan')
    AND la.is_deleted = false
    AND a.is_deleted = false
  LIMIT 1
)
UPDATE loan_account la
SET
  disbursement_status = :'target_disb_status',
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_force_stage'
FROM tgt
WHERE la.account_id = tgt.account_id;

-- Clear UTR so NEFT can be attempted when stage allows it
WITH tgt AS (
  SELECT la.account_id
  FROM loan_account la
  JOIN account a ON a.id = la.account_id
  WHERE a.account_number = btrim(:'lan')
    AND la.is_deleted = false
    AND a.is_deleted = false
  LIMIT 1
)
UPDATE loan_disbursement_mode_details d
SET
  utr_number = NULL,
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_force_stage'
FROM tgt
WHERE d.loan_account_id = tgt.account_id
  AND d.is_deleted = false;

-- Soft-archive CRR rows (preserve evidence, detach from LAN so app lookups miss them)
-- Note: we avoid DO blocks so psql var substitution is reliable.

-- Archive GL legs (DTFC)
UPDATE client_request_response_log c
SET
  uri = concat_ws(
    ' | ',
    NULLIF(btrim(coalesce(c.uri, '')), ''),
    'LOCAL_FORCE_STAGE_ORIG_LAN=' || c.loan_account_number,
    'LOCAL_FORCE_STAGE_ORIG_STATUS=' || c.status
  ),
  loan_account_number = '~' || c.id::text,
  status = 'LOCAL_FORCE_STAGE_ARCHIVED',
  eligible_for_retry = false,
  updated_on = CURRENT_TIMESTAMP
WHERE lower(btrim(:'archive_gl')) = 'true'
  AND c.loan_account_number = btrim(:'lan')
  AND c.transaction_type IN ('DISB_GL_CBS_INTEGRATION', 'DISB_GL_CBS_INTEGRATION_NETOFF');

-- Archive NEFT leg
UPDATE client_request_response_log c
SET
  uri = concat_ws(
    ' | ',
    NULLIF(btrim(coalesce(c.uri, '')), ''),
    'LOCAL_FORCE_STAGE_ORIG_LAN=' || c.loan_account_number,
    'LOCAL_FORCE_STAGE_ORIG_STATUS=' || c.status
  ),
  loan_account_number = '~' || c.id::text,
  status = 'LOCAL_FORCE_STAGE_ARCHIVED',
  eligible_for_retry = false,
  updated_on = CURRENT_TIMESTAMP
WHERE lower(btrim(:'archive_neft')) = 'true'
  AND c.loan_account_number = btrim(:'lan')
  AND c.transaction_type IN ('DISBURSEMENT_NEFT');

-- Archive MFT leg
UPDATE client_request_response_log c
SET
  uri = concat_ws(
    ' | ',
    NULLIF(btrim(coalesce(c.uri, '')), ''),
    'LOCAL_FORCE_STAGE_ORIG_LAN=' || c.loan_account_number,
    'LOCAL_FORCE_STAGE_ORIG_STATUS=' || c.status
  ),
  loan_account_number = '~' || c.id::text,
  status = 'LOCAL_FORCE_STAGE_ARCHIVED',
  eligible_for_retry = false,
  updated_on = CURRENT_TIMESTAMP
WHERE lower(btrim(:'archive_mft')) = 'true'
  AND c.loan_account_number = btrim(:'lan')
  AND c.transaction_type IN ('DISBURSEMENT_MFT');

COMMIT;

\echo ''
\echo '=== local_force_stage done ==============================================='
\echo 'lan=' :'lan' ' target_disb_status=' :'target_disb_status' ' archive_gl=' :'archive_gl' ' archive_neft=' :'archive_neft' ' archive_mft=' :'archive_mft'
\echo '==========================================================================='
\echo ''
