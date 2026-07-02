-- Local QA only (Yugabyte, schema mfi_accounting). Aggressive wipe for one customer + test correlators.
-- Voids all loan_account rows for the customer, soft-deletes common children, cancels matching mandates,
-- soft-deletes loan_account_events_queue for those account_ids, archives CRR by LAN.
--
-- Does NOT truncate tables; uses is_deleted / CLOSED / VOID external_ref like local_reset_mfi_customer_loans.
--
-- Usage:
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
--     -v customer_id='10000304' \
--     -v ext_ref='4495972134234554346565' \
--     -v group_id='397489' \
--     -f scripts/local_full_wipe_mfi_customer_test_yugabyte.sql
--
-- Pass ext_ref='' and/or group_id='' to skip those mandate predicates.

BEGIN;
SET search_path TO mfi_accounting;

DROP TABLE IF EXISTS _wipe_acc;
CREATE TEMP TABLE _wipe_acc AS
SELECT DISTINCT la.account_id
FROM loan_account la
WHERE la.customer_id = CAST(btrim(:'customer_id') AS bigint);

-- Mandates: by loan_account, LOS ref, or group+customer (when vars non-blank)
UPDATE repayment_mandate_details rmd
SET
  is_deleted = true,
  mandate_status = 'CANCELLED',
  loan_account_id = NULL,
  rejected_or_cancelled_date = CURRENT_TIMESTAMP
WHERE rmd.loan_account_id IN (SELECT account_id FROM _wipe_acc)
   OR (btrim(:'ext_ref') <> '' AND rmd.loan_application_id = btrim(:'ext_ref'))
   OR (
        btrim(:'group_id') <> ''
        AND rmd.group_id = CAST(btrim(:'group_id') AS bigint)
        AND rmd.customer_id = CAST(btrim(:'customer_id') AS bigint)
      );

UPDATE file_staging_post_disbursement_insurance t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE file_staging_proactive_refund t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_account_charge_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_account_insurance_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_account_noc_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_account_noc_dispatch_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_account_nominee_details t
SET is_deleted = true
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_account_restructuring_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_disbursement_cancellation_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_disbursement_charge_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_disbursement_mode_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_disbursement_transaction t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_due_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_installment_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_repayment_schedule_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE prepayment_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE presentation_bounce_charge_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE si_failed_presentation_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE si_manual_presentation_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE si_presentation_loan_account_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE transaction_reversal_details t
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE t.loan_account_id IN (SELECT account_id FROM _wipe_acc) AND t.is_deleted = false;

UPDATE loan_account_events_queue q
SET is_deleted = true, updated_on = CURRENT_TIMESTAMP, updated_by = 'local_full_wipe'
WHERE q.parent_account_id IN (SELECT account_id FROM _wipe_acc) AND q.is_deleted = false;

UPDATE client_request_response_log c
SET
  uri = concat_ws(
    ' | ',
    NULLIF(btrim(coalesce(c.uri, '')), ''),
    'LOCAL_FULL_WIPE_ORIG_LAN=' || c.loan_account_number,
    'LOCAL_FULL_WIPE_ORIG_STATUS=' || c.status
  ),
  loan_account_number = '~' || c.id::text,
  status = 'LOCAL_FULL_WIPE_ARCHIVED',
  eligible_for_retry = false,
  updated_on = CURRENT_TIMESTAMP
FROM account a
WHERE c.loan_account_number = a.account_number
  AND a.id IN (SELECT account_id FROM _wipe_acc);

UPDATE loan_account la
SET
  is_deleted = true,
  loan_status = 'CLOSED',
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_full_wipe',
  external_ref_number = LEFT(
    'VOID_' || la.account_id::text || '_' || COALESCE(NULLIF(TRIM(la.external_ref_number), ''), 'NA'),
    64
  )
WHERE la.customer_id = CAST(btrim(:'customer_id') AS bigint);

UPDATE account a
SET
  is_deleted = true,
  status = 'CLOSED',
  closing_date = COALESCE(closing_date, CURRENT_TIMESTAMP),
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_full_wipe'
FROM loan_account la
WHERE la.account_id = a.id AND la.customer_id = CAST(btrim(:'customer_id') AS bigint);

SELECT 'local_full_wipe done' AS note,
       (SELECT count(*) FROM _wipe_acc) AS account_ids_scoped;

DROP TABLE IF EXISTS _wipe_acc;

COMMIT;

\echo ''
\echo '=== local_full_wipe: customer loans voided; children + mandates + queue cleaned; CRR archived by LAN ==='
