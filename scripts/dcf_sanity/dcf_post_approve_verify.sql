-- Post-approve verification for death foreclosure (run after deathForeclosureInsuranceJob APPROVE).
-- Usage:
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
--     -v lan='6002681039' \
--     -f scripts/dcf_sanity/dcf_post_approve_verify.sql

\set ON_ERROR_STOP on
\set schema 'mfi_accounting'

\echo '=== Loan + account ==='
SELECT la.account_number,
       la.loan_status,
       a.status AS account_status,
       la.past_due_days,
       la.excess_amount
FROM :schema.loan_account la
JOIN :schema.account a ON a.id = la.account_id AND a.is_deleted = false
WHERE la.account_number = :'lan'
  AND la.is_deleted = false;

\echo '=== Death foreclosure case ==='
SELECT dfd.id,
       dfd.death_foreclosure_status,
       dfd.task_status,
       dfd.outstanding_loan_balance,
       dfd.balance_claim_amount,
       dfd.date_of_death,
       dfd.created_on AS reporting_date
FROM :schema.death_foreclosure_details dfd
JOIN :schema.loan_account la ON la.id = dfd.loan_account_id
WHERE la.account_number = :'lan'
ORDER BY dfd.id DESC
LIMIT 1;

\echo '=== Insurance staging ==='
SELECT s.id,
       s.claim_status,
       s.inout_status,
       s.outstanding_loan_balance,
       s.balance_claim_amount,
       s.claim_number
FROM :schema.death_foreclosure_insurance_staging_details s
JOIN :schema.death_foreclosure_details dfd ON dfd.id = s.death_foreclosure_details_id
JOIN :schema.loan_account la ON la.id = dfd.loan_account_id
WHERE la.account_number = :'lan'
ORDER BY s.id DESC
LIMIT 1;

\echo '=== Closure txn (DEATH_FORECLOSURE) ==='
SELECT td.id,
       td.reference_number,
       td.transaction_type,
       td.transaction_sub_type,
       td.amount,
       td.value_date
FROM :schema.transaction_details td
JOIN :schema.loan_account_closure_details lacd
  ON lacd.transaction_reference_number = td.reference_number
JOIN :schema.loan_account la ON la.id = lacd.loan_account_id
WHERE la.account_number = :'lan'
  AND lacd.identifier_type = 'DEATH_FORECLOSURE'
ORDER BY td.id DESC
LIMIT 1;

\echo '=== GL partitions (Sheet15 reference codes) ==='
SELECT tpd.reference_code,
       tpd.debit_amount,
       tpd.credit_amount,
       tpd.debit_placeholder,
       tpd.credit_placeholder
FROM :schema.transaction_partition_details tpd
JOIN :schema.transaction_details td ON td.id = tpd.transaction_id
JOIN :schema.loan_account_closure_details lacd
  ON lacd.transaction_reference_number = td.reference_number
JOIN :schema.loan_account la ON la.id = lacd.loan_account_id
WHERE la.account_number = :'lan'
  AND lacd.identifier_type = 'DEATH_FORECLOSURE'
  AND td.transaction_type = 'DEATH_FORECLOSURE'
ORDER BY tpd.reference_code;

\echo '=== Pending dues (should be 0 after close) ==='
SELECT ldd.component_type,
       ldd.due_date,
       ldd.due_amount,
       ldd.paid_amount,
       ldd.waived_amount,
       (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) AS pending
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.id = ldd.loan_account_id
WHERE la.account_number = :'lan'
  AND ldd.is_deleted = false
  AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) <> 0
ORDER BY ldd.due_date, ldd.component_type;

\echo '=== Billed principal bucket (sanity) ==='
SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0) AS unpaid_billed_prin
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.id = ldd.loan_account_id
WHERE la.account_number = :'lan'
  AND ldd.component_type = 'PRIN'
  AND ldd.is_deleted = false
  AND EXISTS (
    SELECT 1 FROM :schema.loan_account_billing_details bd
    WHERE bd.loan_installment_details_id = ldd.loan_installment_details_id
      AND bd.reversed = false
  );
