-- Pattern B: accounting ahead (REUPLOAD_DOCUMENTS), task + staging behind.
-- Expect: task = Insurance Claim Initiated, staging claim_status = Pending for FR.
-- Run on QA first. Schema: mfi_accounting, mfi_task.

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
    d.id              AS dcf_id,
    d.task_id,
    ttv.description   AS task_stage,
    d.death_foreclosure_status,
    ls.id             AS staging_id,
    ls.claim_status,
    ls.inout_status,
    d.fr_comments     AS dcf_fr_comments,
    ls.fr_comments    AS staging_fr_comments
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
  AND ls.inout_status = 'INBOUND_SUCCESS'
ORDER BY la.la_account_number;
