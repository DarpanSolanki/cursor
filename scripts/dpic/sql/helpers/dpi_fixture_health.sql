-- One-line DPI fixture health for regression RCA (demo loan 8060160 / 6004044425).
-- psql vars: loan_account_id (bigint)
\set ON_ERROR_STOP on

SELECT la.loan_status::text,
       a.status::text,
       COALESCE((
         SELECT sum(GREATEST(ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount, 0), 0))
         FROM mfi_accounting.loan_due_details ldd
         WHERE ldd.loan_account_id = la.account_id AND ldd.component_type = 'DPI' AND ldd.is_deleted = false
       ), 0)::text AS dpi_open,
       COALESCE((
         SELECT count(*) FROM mfi_accounting.product__transaction_catalogue ptc
         WHERE ptc.product_id = 6367 AND ptc.transaction_catalogue_id IN (10, 11) AND ptc.is_deleted = false
       ), 0)::text AS cat_10_11_linked
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.account_id = :loan_account_id::bigint
  AND la.is_deleted = false;
