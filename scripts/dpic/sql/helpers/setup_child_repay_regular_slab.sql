-- Reset JLG child loan to regular asset slab before childLoanRepayment (avoid NPA sub_type path).
\set ON_ERROR_STOP on

BEGIN;

UPDATE mfi_accounting.loan_account la
SET asset_criteria_slabs_id = sub.regular_slab,
    npa_tagging_date = NULL,
    npa_ageing_start_date = NULL,
    sec_npa_tagging_date = NULL,
    is_sec_npa = false,
    updated_on = NOW(),
    updated_by = 'LOCAL_CHILD_DPI_TEST'
FROM (
  SELECT acs.id AS regular_slab
  FROM mfi_accounting.loan_account la2
  JOIN mfi_accounting.asset_criteria_slabs acs
    ON acs.asset_criteria_group_id = la2.asset_criteria_group_id
   AND acs.is_deleted = false
   AND acs.is_npa = false
  WHERE la2.account_id = :loan_account_id::bigint
  ORDER BY acs.past_due_days_from
  LIMIT 1
) sub
WHERE la.account_id = :loan_account_id::bigint;

COMMIT;

\echo '=== child regular slab ==='
SELECT account_id, past_due_days, asset_criteria_slabs_id, npa_tagging_date
FROM mfi_accounting.loan_account WHERE account_id = :loan_account_id::bigint;
