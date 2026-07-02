-- DCF task ↔ accounting sync inventory (READ-ONLY — no writes, no psql variables).
-- Schemas: mfi_accounting, mfi_task. Run on QA or prod Yugabyte as-is.
--
-- CSV output (any host):
--   psql -h HOST -p PORT -U USER -d yugabyte -v ON_ERROR_STOP=1 --csv \
--     -f scripts/sql/adhoc/dcf_insurance_sync/06_export_dcf_sync_inventory.sql \
--     -o dcf_sync_inventory.csv
--
-- Screen preview:
--   psql ... -f scripts/sql/adhoc/dcf_insurance_sync/06_export_dcf_sync_inventory.sql

WITH death_task_stages AS (
    SELECT unnest(ARRAY[
        'Download Death Claim Form',
        'Upload Death Claim Form',
        'Death Claim Review',
        'Death Claim Approval',
        'Insurance Claim Initiated',
        'Re-Upload Document'
    ]) AS task_stage_description
),
canonical_dcf AS (
    SELECT DISTINCT ON (d.loan_account_id)
        d.*
    FROM mfi_accounting.death_foreclosure_details d
    ORDER BY
        d.loan_account_id,
        CASE WHEN d.death_foreclosure_status = 'REJECTED' THEN 1 ELSE 0 END,
        d.created_on DESC,
        d.id DESC
),
staging_stats AS (
    SELECT
        s.death_foreclosure_details_id,
        COUNT(*) FILTER (WHERE COALESCE(s.is_deleted, false) = false) AS staging_active_row_count,
        COUNT(*) AS staging_total_row_count,
        MAX(s.id) FILTER (WHERE COALESCE(s.is_deleted, false) = false) AS max_active_staging_id
    FROM mfi_accounting.death_foreclosure_insurance_staging_details s
    GROUP BY s.death_foreclosure_details_id
),
latest_staging AS (
    SELECT DISTINCT ON (s.death_foreclosure_details_id)
        s.*
    FROM mfi_accounting.death_foreclosure_insurance_staging_details s
    WHERE COALESCE(s.is_deleted, false) = false
    ORDER BY
        s.death_foreclosure_details_id,
        s.updated_on DESC NULLS LAST,
        s.id DESC
),
task_workflow AS (
    SELECT
        t.id AS task_id,
        ttv.description AS task_stage_description,
        tt.task_code,
        tt.task_type,
        wm.code AS workflow_master_code,
        wsd.sequence AS workflow_stage_sequence
    FROM mfi_task.task t
    JOIN mfi_task.task_type_version ttv
        ON ttv.id = t.task_type_version_id
    JOIN mfi_task.task_type tt
        ON tt.id = t.task_type_id
       AND COALESCE(tt.is_deleted, false) = false
    LEFT JOIN mfi_task.task_attributes ta
        ON ta.task_id = t.id
       AND ta.prop_key = 'WORKFLOW_MASTER_CODE'
       AND COALESCE(ta.is_deleted, false) = false
    LEFT JOIN mfi_task.workflow_master wm
        ON wm.code = ta.prop_value
       AND COALESCE(wm.is_deleted, false) = false
    LEFT JOIN mfi_task.workflow_stage_details wsd
        ON wsd.workflow_master_id = wm.id
       AND wsd.task_type_version_id = t.task_type_version_id
    WHERE COALESCE(t.is_deleted, false) = false
),
base AS (
    SELECT
        cd.id AS dcf_id,
        cd.loan_account_id,
        a.account_number AS lan,
        la.loan_status,
        la.customer_id,
        la.loan_product_id,
        cd.deceased_person,
        cd.deceased_person_name,
        cd.date_of_death,
        cd.date_of_birth,
        cd.claim_type,
        cd.cause_of_death,
        cd.date_of_diagnosis,
        cd.date_of_accident,
        cd.place_of_death,
        cd.death_claim_form_document_id,
        cd.is_nominee_under_age,
        cd.death_foreclosure_status,
        cd.task_id,
        cd.task_status AS dcf_task_status,
        cd.reject_reason,
        cd.reject_notes,
        cd.fr_reasons AS dcf_fr_reasons,
        cd.fr_comments AS dcf_fr_comments,
        cd.excess_amount,
        cd.outstanding_loan_balance AS dcf_outstanding_loan_balance,
        cd.balance_claim_amount AS dcf_balance_claim_amount,
        cd.group_id,
        cd.group_name,
        cd.approved_on AS dcf_approved_on,
        cd.approved_by AS dcf_approved_by,
        cd.created_on AS dcf_created_on,
        cd.created_by AS dcf_created_by,
        cd.updated_on AS dcf_updated_on,
        cd.updated_by AS dcf_updated_by,
        t.id AS task_row_id,
        t.name AS task_name,
        tw.task_stage_description,
        tw.task_code,
        tw.task_type,
        tw.workflow_master_code,
        tw.workflow_stage_sequence,
        t.current_status AS task_current_status,
        t.assignee_contributor AS task_assignee_contributor,
        t.office_id AS task_office_id,
        t.identifier AS task_identifier,
        COALESCE(t.is_deleted, false) AS task_is_deleted,
        t.created_on AS task_created_on,
        t.updated_on AS task_updated_on,
        t.updated_by AS task_updated_by,
        COALESCE(ss.staging_active_row_count, 0) AS staging_active_row_count,
        COALESCE(ss.staging_total_row_count, 0) AS staging_total_row_count,
        ls.id AS staging_id,
        ls.file_upload_id AS staging_file_upload_id,
        ls.loan_account_number AS staging_lan,
        ls.policy_number AS staging_policy_number,
        ls.product_code AS staging_product_code,
        ls.claim_type AS staging_claim_type,
        ls.claim_status AS staging_claim_status,
        ls.inout_status AS staging_inout_status,
        ls.status AS staging_batch_status,
        ls.claim_number AS staging_claim_number,
        ls.fr_reasons AS staging_fr_reasons,
        ls.fr_comments AS staging_fr_comments,
        ls.outstanding_loan_balance AS staging_outstanding_loan_balance,
        ls.balance_claim_amount AS staging_balance_claim_amount,
        ls.payment_amount_for_nominee AS staging_payment_amount_for_nominee,
        ls.sum_assured AS staging_sum_assured,
        ls.original_loan_amount AS staging_original_loan_amount,
        ls.created_on AS staging_created_on,
        ls.updated_on AS staging_updated_on,
        ls.updated_by AS staging_updated_by,
        COALESCE(ls.is_deleted, false) AS staging_is_deleted,
        CASE
            WHEN cd.task_id IS NULL THEN false
            WHEN t.id IS NULL THEN false
            WHEN COALESCE(t.is_deleted, false) THEN false
            ELSE cd.task_id = t.id
        END AS task_dcf_link_ok,
        CASE
            WHEN ls.id IS NULL THEN NULL
            WHEN ls.loan_account_number IS NULL OR a.account_number IS NULL THEN NULL
            ELSE ls.loan_account_number = a.account_number
        END AS staging_lan_matches_account,
        CASE
            WHEN cd.fr_reasons IS NULL AND ls.fr_reasons IS NULL THEN true
            WHEN cd.fr_reasons IS NOT DISTINCT FROM ls.fr_reasons THEN true
            ELSE false
        END AS dcf_staging_fr_reasons_match,
        CASE
            WHEN cd.fr_comments IS NULL AND ls.fr_comments IS NULL THEN true
            WHEN cd.fr_comments IS NOT DISTINCT FROM ls.fr_comments THEN true
            ELSE false
        END AS dcf_staging_fr_comments_match,
        CASE
            WHEN ls.claim_status IS NOT NULL
             AND ls.claim_status NOT IN ('PENDING', 'REJECTED', 'APPROVED')
             AND COALESCE(ls.inout_status, '') = 'INBOUND_SUCCESS'
            THEN true
            ELSE false
        END AS batch_death_foreclosure_insurance_job_eligible,
        CASE
            WHEN ls.claim_status = 'PENDING' AND ls.inout_status IS NULL THEN true
            ELSE false
        END AS outbound_batch_pending,
        CASE
            WHEN ls.claim_status = 'PENDING' AND ls.inout_status = 'OUTBOUND_SUCCESS' THEN true
            ELSE false
        END AS outbound_batch_sent
    FROM canonical_dcf cd
    JOIN mfi_accounting.loan_account la
        ON la.account_id = cd.loan_account_id
       AND COALESCE(la.is_deleted, false) = false
    JOIN mfi_accounting.account a
        ON a.id = la.account_id
       AND COALESCE(a.is_deleted, false) = false
    LEFT JOIN mfi_task.task t
        ON t.id = cd.task_id
    LEFT JOIN task_workflow tw
        ON tw.task_id = t.id
    LEFT JOIN staging_stats ss
        ON ss.death_foreclosure_details_id = cd.id
    LEFT JOIN latest_staging ls
        ON ls.death_foreclosure_details_id = cd.id
    WHERE
        cd.death_foreclosure_status NOT IN ('REJECTED', 'EXPIRED')
        OR ls.id IS NOT NULL
        OR (t.id IS NOT NULL AND COALESCE(t.is_deleted, false) = false)
),
classified AS (
    SELECT
        b.*,
        CASE
            WHEN b.death_foreclosure_status IN ('APPROVED', 'REJECTED', 'EXPIRED') THEN 'TERMINAL_DCF'
            WHEN b.task_row_id IS NULL AND b.task_id IS NOT NULL THEN 'MISSING_TASK_ROW'
            WHEN b.task_id IS NULL THEN 'DCF_NO_TASK_ID'
            WHEN COALESCE(b.task_is_deleted, false) THEN 'TASK_SOFT_DELETED'
            WHEN b.workflow_master_code IS DISTINCT FROM 'DEATH_FORECLOSURE'
                 AND b.workflow_master_code IS NOT NULL THEN 'NON_DEATH_FORECLOSURE_WORKFLOW'
            WHEN b.workflow_master_code IS NULL
                 AND b.task_stage_description IN (SELECT task_stage_description FROM death_task_stages) THEN 'TASK_MISSING_WORKFLOW_ATTR'
            WHEN b.staging_id IS NULL
                 AND b.task_stage_description IN ('Insurance Claim Initiated', 'Re-Upload Document') THEN 'MISSING_STAGING'
            WHEN b.staging_active_row_count > 1 THEN 'MULTIPLE_ACTIVE_STAGING'
            WHEN b.task_stage_description = 'Download Death Claim Form'
                 AND b.death_foreclosure_status = 'DOWNLOADED_DCF' THEN 'ALIGNED_EARLY'
            WHEN b.task_stage_description = 'Upload Death Claim Form'
                 AND b.death_foreclosure_status = 'UPLOADED_DCF' THEN 'ALIGNED_EARLY'
            WHEN b.task_stage_description = 'Death Claim Review'
                 AND b.death_foreclosure_status = 'REVIEWED_DCF' THEN 'ALIGNED_EARLY'
            WHEN b.task_stage_description = 'Death Claim Approval'
                 AND b.death_foreclosure_status IN ('REVIEWED_DCF', 'APPROVED_DCF') THEN 'ALIGNED_EARLY'
            WHEN b.task_stage_description = 'Insurance Claim Initiated'
                 AND b.death_foreclosure_status = 'INITIATED_INSURACE_CLAIM'
                 AND b.staging_claim_status = 'PENDING'
                 AND b.staging_inout_status IS NULL THEN 'ALIGNED_INSURANCE_OUTBOUND_PENDING'
            WHEN b.task_stage_description = 'Insurance Claim Initiated'
                 AND b.death_foreclosure_status = 'INITIATED_INSURACE_CLAIM'
                 AND b.staging_claim_status = 'PENDING'
                 AND b.staging_inout_status = 'OUTBOUND_SUCCESS' THEN 'ALIGNED_INSURANCE_AWAITING_INBOUND'
            WHEN b.task_stage_description = 'Insurance Claim Initiated'
                 AND b.death_foreclosure_status = 'INITIATED_INSURACE_CLAIM'
                 AND b.staging_claim_status = 'Pending for FR'
                 AND b.staging_inout_status = 'INBOUND_SUCCESS' THEN 'ALIGNED_INSURANCE_INBOUND_BEFORE_BATCH'
            WHEN b.task_stage_description = 'Insurance Claim Initiated'
                 AND b.death_foreclosure_status = 'REUPLOAD_DOCUMENTS'
                 AND b.staging_claim_status = 'Pending for FR'
                 AND b.staging_inout_status = 'INBOUND_SUCCESS' THEN 'DRIFT_PATTERN_B'
            WHEN b.task_stage_description = 'Re-Upload Document'
                 AND b.death_foreclosure_status = 'REUPLOAD_DOCUMENTS'
                 AND b.staging_claim_status = 'REJECTED' THEN 'ALIGNED_INSURANCE_REUPLOAD'
            WHEN b.task_stage_description = 'Re-Upload Document'
                 AND b.death_foreclosure_status = 'INITIATED_INSURACE_CLAIM'
                 AND b.staging_claim_status = 'REJECTED' THEN 'DRIFT_PATTERN_A'
            WHEN b.death_foreclosure_status = 'APPROVED'
                 AND b.staging_claim_status = 'APPROVED' THEN 'ALIGNED_INSURANCE_APPROVED'
            WHEN b.death_foreclosure_status = 'INITIATED_DEATH_FORECLOSURE' THEN 'SENT_BACK_EARLY_WORKFLOW'
            ELSE 'OTHER_DRIFT'
        END AS drift_pattern,
        CASE
            WHEN b.task_stage_description = 'Download Death Claim Form' THEN 'DOWNLOADED_DCF'
            WHEN b.task_stage_description = 'Upload Death Claim Form' THEN 'UPLOADED_DCF'
            WHEN b.task_stage_description = 'Death Claim Review' THEN 'REVIEWED_DCF'
            WHEN b.task_stage_description = 'Death Claim Approval' THEN 'REVIEWED_DCF'
            WHEN b.task_stage_description = 'Insurance Claim Initiated'
                 AND b.staging_claim_status IN ('Pending for FR', 'Claim Closed')
                 AND b.staging_inout_status = 'INBOUND_SUCCESS' THEN 'REUPLOAD_DOCUMENTS'
            WHEN b.task_stage_description = 'Insurance Claim Initiated' THEN 'INITIATED_INSURACE_CLAIM'
            WHEN b.task_stage_description = 'Re-Upload Document' THEN 'REUPLOAD_DOCUMENTS'
            ELSE NULL
        END AS target_dcf_status,
        CASE
            WHEN b.task_stage_description = 'Insurance Claim Initiated'
                 AND b.staging_claim_status IN ('Pending for FR', 'Claim Closed')
                 AND b.staging_inout_status = 'INBOUND_SUCCESS' THEN 'Re-Upload Document'
            WHEN b.task_stage_description = 'Re-Upload Document'
                 AND b.staging_claim_status = 'REJECTED' THEN 'Re-Upload Document'
            WHEN b.task_stage_description = 'Insurance Claim Initiated' THEN 'Insurance Claim Initiated'
            ELSE b.task_stage_description
        END AS target_task_stage,
        CASE
            WHEN b.task_stage_description = 'Insurance Claim Initiated'
                 AND b.staging_inout_status = 'INBOUND_SUCCESS'
                 AND b.staging_claim_status IN ('Pending for FR', 'Claim Closed') THEN 'REJECTED'
            WHEN b.task_stage_description = 'Re-Upload Document' THEN 'REJECTED'
            WHEN b.task_stage_description = 'Insurance Claim Initiated'
                 AND b.staging_inout_status IS NULL THEN 'PENDING'
            WHEN b.death_foreclosure_status = 'APPROVED' THEN 'APPROVED'
            ELSE b.staging_claim_status
        END AS target_staging_claim_status,
        CASE
            WHEN b.task_stage_description IN ('Insurance Claim Initiated', 'Re-Upload Document')
                 AND b.staging_inout_status = 'INBOUND_SUCCESS' THEN 'INBOUND_SUCCESS'
            WHEN b.task_stage_description = 'Insurance Claim Initiated'
                 AND b.staging_inout_status = 'OUTBOUND_SUCCESS' THEN 'OUTBOUND_SUCCESS'
            ELSE b.staging_inout_status
        END AS target_staging_inout_status
    FROM base b
)
SELECT
    now() AT TIME ZONE 'UTC' AS export_utc_ts,
    lan,
    loan_account_id,
    loan_status,
    customer_id,
    loan_product_id,
    dcf_id,
    death_foreclosure_status,
    dcf_task_status,
    task_id,
    task_row_id,
    task_name,
    task_stage_description,
    task_code,
    task_type,
    workflow_master_code,
    workflow_stage_sequence,
    task_current_status,
    task_assignee_contributor,
    task_office_id,
    task_identifier,
    task_is_deleted,
    task_dcf_link_ok,
    deceased_person,
    deceased_person_name,
    date_of_death,
    date_of_birth,
    claim_type,
    cause_of_death,
    date_of_diagnosis,
    date_of_accident,
    place_of_death,
    death_claim_form_document_id,
    is_nominee_under_age,
    reject_reason,
    reject_notes,
    dcf_fr_reasons,
    dcf_fr_comments,
    excess_amount,
    dcf_outstanding_loan_balance,
    dcf_balance_claim_amount,
    group_id,
    group_name,
    dcf_approved_on,
    dcf_approved_by,
    dcf_created_on,
    dcf_created_by,
    dcf_updated_on,
    dcf_updated_by,
    staging_active_row_count,
    staging_total_row_count,
    staging_id,
    staging_file_upload_id,
    staging_lan,
    staging_lan_matches_account,
    staging_policy_number,
    staging_product_code,
    staging_claim_type,
    staging_claim_status,
    staging_inout_status,
    staging_batch_status,
    staging_claim_number,
    staging_fr_reasons,
    staging_fr_comments,
    dcf_staging_fr_reasons_match,
    dcf_staging_fr_comments_match,
    staging_outstanding_loan_balance,
    staging_balance_claim_amount,
    staging_payment_amount_for_nominee,
    staging_sum_assured,
    staging_original_loan_amount,
    staging_created_on,
    staging_updated_on,
    staging_updated_by,
    staging_is_deleted,
    outbound_batch_pending,
    outbound_batch_sent,
    batch_death_foreclosure_insurance_job_eligible,
    drift_pattern,
    CASE
        WHEN drift_pattern LIKE 'ALIGNED%' THEN 'NONE'
        WHEN drift_pattern = 'DRIFT_PATTERN_B' THEN 'PATCH_B_THEN_PATCH_A_IF_NEEDED'
        WHEN drift_pattern = 'DRIFT_PATTERN_A' THEN 'PATCH_A'
        WHEN drift_pattern = 'MISSING_STAGING' THEN 'MANUAL_REVIEW'
        WHEN drift_pattern = 'MULTIPLE_ACTIVE_STAGING' THEN 'MANUAL_REVIEW_STAGING_ROWS'
        WHEN drift_pattern IN ('MISSING_TASK_ROW', 'DCF_NO_TASK_ID', 'TASK_SOFT_DELETED') THEN 'MANUAL_REVIEW_TASK'
        WHEN drift_pattern = 'TERMINAL_DCF' THEN 'SKIP'
        WHEN drift_pattern = 'SENT_BACK_EARLY_WORKFLOW' THEN 'SKIP_OR_EARLY_FLOW'
        ELSE 'MANUAL_REVIEW'
    END AS proposed_sync_action,
    target_task_stage,
    target_dcf_status,
    target_staging_claim_status,
    target_staging_inout_status,
    CASE
        WHEN drift_pattern LIKE 'ALIGNED%' THEN true
        ELSE false
    END AS is_aligned,
    task_created_on,
    task_updated_on,
    task_updated_by
FROM classified
WHERE
    workflow_master_code = 'DEATH_FORECLOSURE'
    OR task_stage_description IN (SELECT task_stage_description FROM death_task_stages)
    OR staging_id IS NOT NULL
    OR death_foreclosure_status NOT IN ('REJECTED', 'EXPIRED')
ORDER BY
    CASE WHEN drift_pattern LIKE 'ALIGNED%' THEN 1 ELSE 0 END,
    drift_pattern,
    lan,
    dcf_id;
