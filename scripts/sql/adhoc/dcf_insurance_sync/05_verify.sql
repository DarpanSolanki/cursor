-- After patches: should return 0 rows.
-- Aligned re-upload rows should show Re-Upload Document + REUPLOAD_DOCUMENTS + REJECTED.

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
    ttv.description   AS task_stage,
    d.death_foreclosure_status,
    ls.claim_status
FROM latest_dcf d
JOIN mfi_accounting.loan_account la
    ON la.account_id = d.loan_account_id
   AND COALESCE(la.is_deleted, false) = false
JOIN mfi_task.task t
    ON t.id = d.task_id
   AND COALESCE(t.is_deleted, false) = false
JOIN mfi_task.task_type_version ttv
    ON ttv.id = t.task_type_version_id
LEFT JOIN latest_staging ls
    ON ls.death_foreclosure_details_id = d.id
WHERE d.death_foreclosure_status NOT IN ('APPROVED', 'REJECTED', 'EXPIRED')
  AND (
        (ttv.description = 'Re-Upload Document'
         AND d.death_foreclosure_status <> 'REUPLOAD_DOCUMENTS')
     OR (ttv.description = 'Insurance Claim Initiated'
         AND d.death_foreclosure_status = 'REUPLOAD_DOCUMENTS')
      )
ORDER BY la.la_account_number;
