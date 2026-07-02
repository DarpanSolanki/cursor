-- Assert DPI GL legs on latest LOAN_PREPAYMENT (foreclosure) txn — uses verify_gl_legs.sql.
-- psql vars: loan_account_id (bigint), stan (optional)
\set ON_ERROR_STOP on

\set _txn_ref ''
\set _txn_ref `psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -t -A -v ON_ERROR_STOP=1 -v loan_account_id=:'loan_account_id' -f resolve_latest_payment_txn.sql 2>/dev/null || echo ''`

-- Thin wrapper: callers use dpi_assert_gl_legs_from_payment in shell; this file kept for manual psql.
SELECT count(*)::text AS dpi_leg_count,
       COALESCE(max(tpd.amount), 0)::text AS max_dpi_leg_amount
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE tc.type = 'LOAN_PREPAYMENT'
  AND tm.reversed = false
  AND tpd.reference_code = ANY(ARRAY[
    'BILLED_DPI_INT_AMT', 'ADV_BILLED_DPI_INT_AMT', 'BILLED_DPI_INT_WAIVED_AMT'
  ])
  AND tpd.amount > 0
  AND tm.reference_number = (
    SELECT lapd.transaction_reference_number
    FROM mfi_accounting.loan_account_payments_details lapd
    WHERE lapd.loan_account_id = :loan_account_id::bigint
      AND lapd.transaction_reference_number NOT LIKE 'R\_%'
      AND (
        NULLIF(:'stan', '') IS NULL
        OR EXISTS (
          SELECT 1 FROM mfi_accounting.transaction_master tm2
          WHERE tm2.reference_number = lapd.transaction_reference_number
            AND tm2.stan = NULLIF(:'stan', '')
        )
      )
    ORDER BY lapd.id DESC
    LIMIT 1
  );
