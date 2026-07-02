-- Pattern B patch: move task to Re-Upload Document, copy FR to DCF, close staging.
-- Does NOT change death_foreclosure_status (already REUPLOAD_DOCUMENTS).
-- Review 01_pattern_b_list.sql first. If row count != expected, ROLLBACK.
-- Run order: 02 (this) before 04_pattern_a_patch.sql

BEGIN;

CREATE TEMP TABLE ops_dcf_sync_b ON COMMIT DROP AS
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
    la.la_account_number,
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

SELECT la_account_number, dcf_id, task_id, staging_id FROM ops_dcf_sync_b ORDER BY la_account_number;
SELECT COUNT(*) AS pattern_b_row_count FROM ops_dcf_sync_b;

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

COMMIT;
