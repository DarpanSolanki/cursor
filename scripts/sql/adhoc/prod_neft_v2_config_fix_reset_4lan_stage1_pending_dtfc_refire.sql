-- PROD mfi_accounting: soft-archive 4 NEFT_STAGE_1_PENDING CRR (Cohort B only) → DTFC_SUCCESS re-fire.
-- Scope: stage-1 pending LANs only. Cohort A (FAIL/DTFC) not included.
-- Soft-archive: ~||id, eligible_for_retry=false, keep status SUCCESS (no uri change, no transaction_type filter).
-- ROLLBACK by default. COMMIT only after ops/bank confirm.

BEGIN;

UPDATE mfi_accounting.client_request_response_log
SET
  loan_account_number = '~' || id::text,
  eligible_for_retry = false,
  updated_on = CURRENT_TIMESTAMP
WHERE id IN (
  59321603, 59321607, 59321609, 59321707
)
  AND loan_account_number NOT LIKE '~%';

UPDATE mfi_accounting.loan_account la
SET
  disbursement_status = 'DTFC_SUCCESS',
  filler_1 = NULL,
  filler_2 = NULL,
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'prod_neft_v2_cfgfix_4lan_stage1_pending_reset'
FROM mfi_accounting.account a
WHERE la.account_id = a.id
  AND la.is_deleted = false
  AND a.is_deleted = false
  AND a.account_number IN (
    '6001693619', '6001693623', '6001693624', '6001693625'
  );

ROLLBACK;
-- COMMIT;
