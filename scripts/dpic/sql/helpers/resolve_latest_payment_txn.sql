-- Latest non-reversal payment txn ref for a loan (foreclosure / repayment write asserts).
-- psql vars: loan_account_id (bigint)
\set ON_ERROR_STOP on

SELECT lapd.transaction_reference_number::text AS txn_reference
FROM mfi_accounting.loan_account_payments_details lapd
WHERE lapd.loan_account_id = :loan_account_id::bigint
  AND lapd.transaction_reference_number IS NOT NULL
  AND lapd.transaction_reference_number NOT LIKE 'R\_%'
ORDER BY lapd.id DESC
LIMIT 1;
