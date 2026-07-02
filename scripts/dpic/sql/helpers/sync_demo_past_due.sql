-- Local demo helper when loanAccountDpdCalcJob fails (JDBC pool / INACTIVE job).
-- Sets past_due_days = business_date - earliest unsettled EMI on or before business_date.
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.loan_account la
SET past_due_days = GREATEST(0, sub.dpd),
    updated_on = NOW(),
    updated_by = 'LOCAL_DEMO_DPD_SYNC'
FROM (
  SELECT :loan_account_id::bigint AS account_id,
         COALESCE(
           (DATE_TRUNC('day', TO_TIMESTAMP(:business_date_ms::bigint / 1000.0))
            - MIN(lid.installment_date::date))::int,
           0
         ) AS dpd
  FROM mfi_accounting.loan_installment_details lid
  WHERE lid.loan_account_id = :loan_account_id::bigint
    AND lid.is_deleted = false
    AND lid.is_settled = false
    AND lid.installment_date::date
        <= DATE_TRUNC('day', TO_TIMESTAMP(:business_date_ms::bigint / 1000.0))::date
) sub
WHERE la.account_id = sub.account_id;

COMMIT;

\echo '=== past_due_days after sync ==='
SELECT account_id, past_due_days, loan_status
FROM mfi_accounting.loan_account
WHERE account_id = :loan_account_id::bigint;
