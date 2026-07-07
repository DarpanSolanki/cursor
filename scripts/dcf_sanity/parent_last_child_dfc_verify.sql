-- SDCP-10199 parent last-child DFC invariants (run after deathForeclosureInsuranceJob on last child).
-- Usage:
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
--     -v parent_lan='6002329725' -f scripts/dcf_sanity/parent_last_child_dfc_verify.sql

\set ON_ERROR_STOP on
\set schema 'mfi_accounting'

\echo '=== Parent status ==='
SELECT la.account_number,
       la.loan_status,
       la.la_closing_date IS NOT NULL AS has_closing_date,
       a.status AS account_status
FROM :schema.loan_account la
JOIN :schema.account a ON a.id = la.account_id AND a.is_deleted = false
WHERE la.account_number = :'parent_lan'
  AND la.is_deleted = false;

\echo '=== Parent PRIN must be paid (not waived) — pending zero ==='
SELECT ROUND(SUM(ldd.paid_amount)::numeric, 2) AS prin_paid,
       ROUND(SUM(ldd.waived_amount)::numeric, 2) AS prin_waived,
       ROUND(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount)::numeric, 2) AS prin_pending
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.account_number = :'parent_lan'
  AND ldd.component_type = 'PRIN'
  AND ldd.is_deleted = false;

\echo '=== Parent INT — future may be waived; pending zero ==='
SELECT ROUND(SUM(ldd.paid_amount)::numeric, 2) AS int_paid,
       ROUND(SUM(ldd.waived_amount)::numeric, 2) AS int_waived,
       ROUND(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount)::numeric, 2) AS int_pending
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.account_number = :'parent_lan'
  AND ldd.component_type = 'INT'
  AND ldd.is_deleted = false;

\echo '=== Future PRIN rows (paid should equal due; waived should be 0) ==='
SELECT ldd.due_date,
       ldd.due_amount,
       ldd.paid_amount,
       ldd.waived_amount,
       (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) AS pending
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.account_number = :'parent_lan'
  AND ldd.component_type = 'PRIN'
  AND ldd.is_deleted = false
  AND ldd.due_date > CURRENT_DATE
ORDER BY ldd.due_date
LIMIT 12;
