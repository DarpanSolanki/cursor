-- Pattern A patch: set death_foreclosure_status = REUPLOAD_DOCUMENTS only.
-- Task and staging are not changed.
-- Review 03_pattern_a_list.sql first. If row count wrong, ROLLBACK.

BEGIN;

CREATE TEMP TABLE ops_dcf_sync_a ON COMMIT DROP AS
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

SELECT la_account_number, dcf_id FROM ops_dcf_sync_a ORDER BY la_account_number;
SELECT COUNT(*) AS pattern_a_row_count FROM ops_dcf_sync_a;

UPDATE mfi_accounting.death_foreclosure_details d
SET
    death_foreclosure_status = 'REUPLOAD_DOCUMENTS',
    updated_on               = NOW(),
    updated_by               = 'OPS_DCF_SYNC_PATCH_A'
FROM ops_dcf_sync_a e
WHERE d.id = e.dcf_id;

COMMIT;
