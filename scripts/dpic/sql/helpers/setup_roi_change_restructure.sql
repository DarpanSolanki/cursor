\set ON_ERROR_STOP on

DELETE FROM mfi_accounting.loan_account_restructuring_details
WHERE loan_account_id = :loan_account_id::bigint
  AND created_by = 'DPI_ROI_E2E';

INSERT INTO mfi_accounting.loan_account_restructuring_details (
    loan_account_id, restructuring_impact, rescheduling_effective_date,
    is_roi_changed, old_roi, new_roi,
    excess_amount, bpi_amount, overdue_amount, due_amount, penal_amount, fee_amount,
    restructuring_status, task_status,
    created_on, created_by, updated_on, updated_by, approved_on, approved_by, is_deleted)
VALUES (
    :loan_account_id::bigint, 'UPDATE_EMI', :'roi_change_date'::timestamp,
    true, :old_roi::numeric, :new_roi::numeric,
    0, 0, 0, 0, 0, 0,
    'SUCCESS', 'APPROVED',
    NOW(), 'DPI_ROI_E2E', NOW(), 'DPI_ROI_E2E', NOW(), 'DPI_ROI_E2E', false);

UPDATE mfi_accounting.account_interest_details
SET effective_rate = :new_roi::numeric
WHERE account_id = :loan_account_id::bigint;
