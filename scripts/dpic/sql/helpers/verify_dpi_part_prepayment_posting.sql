-- Assert DPI GL legs on latest LOAN_PART-PREPAYMENT txn for LAN (or matching stan).
-- psql vars: lan, stan (optional — when empty, uses latest part-prep txn for lan)
\set ON_ERROR_STOP on

SELECT count(*)::text AS dpi_leg_count,
       COALESCE(max(tpd.amount), 0)::text AS max_dpi_leg_amount
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE tpd.account_number = :'lan'
  AND tc.type = 'LOAN_PART-PREPAYMENT'
  AND tm.reversed = false
  AND tpd.reference_code IN ('BILLED_DPI_INT_AMT', 'ADV_BILLED_DPI_INT_AMT')
  AND tpd.amount > 0
  AND tm.id = (
    SELECT tm2.id
    FROM mfi_accounting.transaction_master tm2
    JOIN mfi_accounting.transaction_catalogue tc2 ON tc2.id = tm2.transaction_catalogue_id
    JOIN mfi_accounting.transaction_partition_details tpd2 ON tpd2.transaction_id = tm2.id
    WHERE tpd2.account_number = :'lan'
      AND tc2.type = 'LOAN_PART-PREPAYMENT'
      AND tm2.reversed = false
      AND (
        NULLIF(:'stan', '') IS NULL
        OR tm2.stan = NULLIF(:'stan', '')
      )
    ORDER BY tm2.id DESC
    LIMIT 1
  );
