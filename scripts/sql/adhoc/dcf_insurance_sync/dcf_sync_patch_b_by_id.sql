-- PATCH_B by direct ids (LAN 6000231481, 6000290751)
-- task: 358962804, 503962707 | dcf: 84602, 166402

UPDATE mfi_task.task t
SET
    task_type_version_id = rt.task_type_version_id,
    task_type_id         = rt.task_type_id,
    name                 = 'Re-Upload Document',
    current_status       = 'UN_ASSIGNED',
    assignee_contributor = NULL,
    updated_on           = NOW(),
    updated_by           = 'OPS_DCF_SYNC'
FROM (
    SELECT tt.id AS task_type_id, ttv.id AS task_type_version_id
    FROM mfi_task.task_type_version ttv
    JOIN mfi_task.task_type tt ON tt.task_type_version_id = ttv.id
    WHERE ttv.description = 'Re-Upload Document'
      AND COALESCE(tt.is_deleted, false) = false
    LIMIT 1
) rt
WHERE t.id IN (358962804, 503962707)
  AND COALESCE(t.is_deleted, false) = false;

UPDATE mfi_accounting.death_foreclosure_details d
SET
    fr_comments = COALESCE(NULLIF(TRIM(d.fr_comments), ''), s.fr_comments),
    fr_reasons  = COALESCE(NULLIF(TRIM(d.fr_reasons), ''), s.fr_reasons),
    updated_on  = NOW(),
    updated_by  = 'OPS_DCF_SYNC'
FROM mfi_accounting.death_foreclosure_insurance_staging_details s
WHERE d.id IN (84602, 166402)
  AND s.death_foreclosure_details_id = d.id
  AND COALESCE(s.is_deleted, false) = false
  AND s.claim_status = 'Pending for FR'
  AND s.inout_status = 'INBOUND_SUCCESS';

UPDATE mfi_accounting.death_foreclosure_insurance_staging_details
SET
    claim_status = 'REJECTED',
    status       = NULL,
    reason       = NULL,
    updated_on   = NOW(),
    updated_by   = 'OPS_DCF_SYNC'
WHERE death_foreclosure_details_id IN (84602, 166402)
  AND COALESCE(is_deleted, false) = false
  AND claim_status = 'Pending for FR'
  AND inout_status = 'INBOUND_SUCCESS';
