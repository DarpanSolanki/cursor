-- DCF insurance sync — PROD dry run (no data saved).
-- Source inventory: DCF.csv — PATCH_B=4, PATCH_A=101 (105 loans total).
-- Pattern B first, then Pattern A. Ends with ROLLBACK.
--
-- Run:
--   psql ... -v ON_ERROR_STOP=1 -f 09_apply_dcf_sync_dry_run.sql
-- Then apply:
--   psql ... -v ON_ERROR_STOP=1 -f 09_apply_dcf_sync.sql
-- Verify:
--   psql ... -v ON_ERROR_STOP=1 -f 05_verify.sql   (expect 0 rows)

BEGIN;

-- ---------------------------------------------------------------------------
-- PATCH B (4 loans): task Insurance Claim Initiated + DCF REUPLOAD_DOCUMENTS
--                   + staging Pending for FR + INBOUND_SUCCESS
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS ops_dcf_sync_b;

CREATE TEMP TABLE ops_dcf_sync_b AS
WITH latest_dcf AS (
    SELECT DISTINCT ON (d.loan_account_id) d.*
    FROM mfi_accounting.death_foreclosure_details d
    ORDER BY
        d.loan_account_id,
        CASE WHEN d.death_foreclosure_status = 'REJECTED' THEN 1 ELSE 0 END,
        d.created_on DESC,
        d.id DESC
),
latest_staging AS (
    SELECT DISTINCT ON (s.death_foreclosure_details_id) s.*
    FROM mfi_accounting.death_foreclosure_insurance_staging_details s
    WHERE COALESCE(s.is_deleted, false) = false
    ORDER BY
        s.death_foreclosure_details_id,
        s.updated_on DESC,
        s.id DESC
)
SELECT
    la.account_number AS la_account_number,
    d.id AS dcf_id,
    d.task_id,
    ls.id AS staging_id,
    ls.fr_comments,
    ls.fr_reasons
FROM latest_dcf d
JOIN mfi_accounting.loan_account la
    ON la.account_id = d.loan_account_id
   AND COALESCE(la.is_deleted, false) = false
JOIN mfi_accounting.account a
    ON a.id = la.account_id
   AND COALESCE(a.is_deleted, false) = false
JOIN mfi_task.task t
    ON t.id = d.task_id
   AND COALESCE(t.is_deleted, false) = false
JOIN mfi_task.task_type_version ttv
    ON ttv.id = t.task_type_version_id
JOIN latest_staging ls
    ON ls.death_foreclosure_details_id = d.id
WHERE ttv.description = 'Insurance Claim Initiated'
  AND d.death_foreclosure_status = 'REUPLOAD_DOCUMENTS'
  AND ls.claim_status = 'Pending for FR'
  AND ls.inout_status = 'INBOUND_SUCCESS';

SELECT la_account_number, dcf_id, task_id, staging_id
FROM ops_dcf_sync_b
ORDER BY la_account_number;

SELECT COUNT(*) AS pattern_b_row_count FROM ops_dcf_sync_b;

DO $guard_b$
DECLARE
    c int;
BEGIN
    SELECT COUNT(*)::int INTO c FROM ops_dcf_sync_b;
    IF c <> 4 THEN
        RAISE EXCEPTION 'PATCH_B: got % rows, expected 4 (prod DCF.csv) — ROLLBACK', c;
    END IF;
END $guard_b$;

UPDATE mfi_task.task t
SET
    task_type_version_id = rt.task_type_version_id,
    task_type_id         = rt.task_type_id,
    name                 = 'Re-Upload Document',
    current_status       = 'UN_ASSIGNED',
    assignee_contributor = NULL,
    updated_on           = NOW(),
    updated_by           = 'OPS_DCF_SYNC_PATCH_B'
FROM ops_dcf_sync_b e
CROSS JOIN LATERAL (
    SELECT tt.id AS task_type_id, ttv.id AS task_type_version_id
    FROM mfi_task.task_type_version ttv
    JOIN mfi_task.task_type tt ON tt.task_type_version_id = ttv.id
    WHERE ttv.description = 'Re-Upload Document'
      AND COALESCE(tt.is_deleted, false) = false
    LIMIT 1
) rt
WHERE t.id = e.task_id
  AND COALESCE(t.is_deleted, false) = false;

UPDATE mfi_accounting.death_foreclosure_details d
SET
    fr_comments = COALESCE(NULLIF(TRIM(d.fr_comments), ''), e.fr_comments),
    fr_reasons  = COALESCE(NULLIF(TRIM(d.fr_reasons), ''), e.fr_reasons),
    updated_on  = NOW(),
    updated_by  = 'OPS_DCF_SYNC_PATCH_B'
FROM ops_dcf_sync_b e
WHERE d.id = e.dcf_id;

UPDATE mfi_accounting.death_foreclosure_insurance_staging_details s
SET
    claim_status = 'REJECTED',
    updated_on   = NOW(),
    updated_by   = 'OPS_DCF_SYNC_PATCH_B'
FROM ops_dcf_sync_b e
WHERE s.id = e.staging_id
  AND COALESCE(s.is_deleted, false) = false;

DROP TABLE IF EXISTS ops_dcf_sync_b;

-- ---------------------------------------------------------------------------
-- PATCH A (101 loans): task Re-Upload Document + DCF INITIATED_INSURACE_CLAIM
--                     + staging REJECTED + INBOUND_SUCCESS
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS ops_dcf_sync_a;

CREATE TEMP TABLE ops_dcf_sync_a AS
WITH latest_dcf AS (
    SELECT DISTINCT ON (d.loan_account_id) d.*
    FROM mfi_accounting.death_foreclosure_details d
    ORDER BY
        d.loan_account_id,
        CASE WHEN d.death_foreclosure_status = 'REJECTED' THEN 1 ELSE 0 END,
        d.created_on DESC,
        d.id DESC
),
latest_staging AS (
    SELECT DISTINCT ON (s.death_foreclosure_details_id) s.*
    FROM mfi_accounting.death_foreclosure_insurance_staging_details s
    WHERE COALESCE(s.is_deleted, false) = false
    ORDER BY
        s.death_foreclosure_details_id,
        s.updated_on DESC,
        s.id DESC
)
SELECT
    la.account_number AS la_account_number,
    d.id AS dcf_id
FROM latest_dcf d
JOIN mfi_accounting.loan_account la
    ON la.account_id = d.loan_account_id
   AND COALESCE(la.is_deleted, false) = false
JOIN mfi_accounting.account a
    ON a.id = la.account_id
   AND COALESCE(a.is_deleted, false) = false
JOIN mfi_task.task t
    ON t.id = d.task_id
   AND COALESCE(t.is_deleted, false) = false
JOIN mfi_task.task_type_version ttv
    ON ttv.id = t.task_type_version_id
JOIN latest_staging ls
    ON ls.death_foreclosure_details_id = d.id
WHERE ttv.description = 'Re-Upload Document'
  AND d.death_foreclosure_status = 'INITIATED_INSURACE_CLAIM'
  AND ls.claim_status = 'REJECTED'
  AND ls.inout_status = 'INBOUND_SUCCESS';

SELECT la_account_number, dcf_id
FROM ops_dcf_sync_a
ORDER BY la_account_number;

SELECT COUNT(*) AS pattern_a_row_count FROM ops_dcf_sync_a;

DO $guard_a$
DECLARE
    c int;
BEGIN
    SELECT COUNT(*)::int INTO c FROM ops_dcf_sync_a;
    IF c <> 101 THEN
        RAISE EXCEPTION 'PATCH_A: got % rows, expected 101 (prod DCF.csv) — ROLLBACK', c;
    END IF;
END $guard_a$;

UPDATE mfi_accounting.death_foreclosure_details d
SET
    death_foreclosure_status = 'REUPLOAD_DOCUMENTS',
    updated_on               = NOW(),
    updated_by               = 'OPS_DCF_SYNC_PATCH_A'
FROM ops_dcf_sync_a e
WHERE d.id = e.dcf_id;

DROP TABLE IF EXISTS ops_dcf_sync_a;

ROLLBACK;
