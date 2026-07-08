-- Post-test dev proof for SDCP-10199 group parent last-child DCF.
-- Run after ntest run dcf.group_parent_last_child_e2e (or manual e2e) on local/QA DB.
--
--   psql ... -v parent_lan='6000137433' -v child1_lan='6000137440' -v child2_lan='6000137441' \
--     -f scripts/dcf_sanity/group_dfc_dev_proof.sql
--
-- Paste outcomes into JIRA Dev Test Details (functional labels — no table/column names in JIRA).

\echo '=== loan status ==='
SELECT la.la_account_number AS loan_account,
       la.loan_status AS status,
       CASE WHEN la.la_closing_date IS NOT NULL THEN 'yes' ELSE 'no' END AS closing_date_set
FROM mfi_accounting.loan_account la
WHERE la.la_account_number IN (:'parent_lan', :'child1_lan', :'child2_lan')
ORDER BY la.la_account_number;

\echo '=== principal buckets ==='
SELECT la.la_account_number AS loan_account,
       COALESCE(SUM(CASE WHEN ldd.component_type = 'PRIN' THEN ldd.paid_amount END), 0)   AS prin_paid,
       COALESCE(SUM(CASE WHEN ldd.component_type = 'PRIN' THEN ldd.waived_amount END), 0) AS prin_waived,
       COALESCE(SUM(CASE WHEN ldd.component_type = 'PRIN'
           THEN ldd.due_amount - ldd.paid_amount - ldd.waived_amount END), 0)            AS prin_pending,
       COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0)            AS total_outstanding
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.la_account_number IN (:'parent_lan', :'child1_lan', :'child2_lan')
  AND ldd.is_deleted = false
GROUP BY la.la_account_number
ORDER BY la.la_account_number;

\echo '=== group closure posting (parent) ==='
SELECT tm.original_amount::text AS group_closure_amount
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE tc.type = 'RSCH_DEATH_FORECLOSURE'
  AND tm.client_reference_number LIKE '%_' || :'parent_lan'
ORDER BY tm.id DESC
LIMIT 1;

\echo '=== member death foreclosure postings ==='
SELECT la.la_account_number AS loan_account,
       tm.original_amount::text AS death_foreclosure_amount
FROM mfi_accounting.loan_account_closure_details lacd
JOIN mfi_accounting.loan_account la ON la.account_id = lacd.loan_account_id
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = lacd.transaction_reference_number
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE la.la_account_number IN (:'child1_lan', :'child2_lan')
  AND lacd.identifier_type = 'DEATH_FORECLOSURE'
ORDER BY la.la_account_number;
