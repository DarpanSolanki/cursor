\set ON_ERROR_STOP on

SELECT count(*)::text AS dpi_npa_txn_count
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.account a ON a.id = :loan_account_id::bigint
WHERE tm.client_reference_number LIKE a.account_number || '%DPI%REGULAR_TO_NPA%'
  AND tc.type = 'REGULAR_TO_NPA'
  AND tc.sub_type = 'DPI_INT_INCOME'
  AND tm.reversed = false;

SELECT COALESCE(sum(ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount, 0)), 0)::text AS billed_dpi_open
FROM mfi_accounting.loan_due_details ldd
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.component_type = 'DPI'
  AND ldd.is_deleted = false
  AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount, 0)) > 0;
