-- Generic GL partition leg assert for a posted transaction.
-- psql vars:
--   txn_reference   (required) — transaction_master.reference_number
--   catalogue_type  (required) — e.g. LOAN_PREPAYMENT, LOAN_PART-PREPAYMENT
--   reference_codes (required) — comma-separated, e.g. BILLED_DPI_INT_AMT,ADV_BILLED_DPI_INT_AMT
--   stan            (optional)  — when set, txn must match transaction_master.stan
\set ON_ERROR_STOP on

SELECT count(*)::text AS leg_count,
       COALESCE(max(tpd.amount), 0)::text AS max_leg_amount
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE tm.reference_number = NULLIF(:'txn_reference', '')
  AND tc.type = NULLIF(:'catalogue_type', '')
  AND tm.reversed = false
  AND tpd.amount > 0
  AND tpd.reference_code = ANY(string_to_array(NULLIF(:'reference_codes', ''), ','))
  AND (
    NULLIF(:'stan', '') IS NULL
    OR tm.stan = NULLIF(:'stan', '')
  );
