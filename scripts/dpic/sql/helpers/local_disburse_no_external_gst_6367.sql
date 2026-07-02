-- Local script-bank disburse for product 6367: skip scheme PROC_FEE price_setup so postTransaction
-- does not call external GST SOAP (simulator often down). Re-apply via run_setup.sh when needed.
\set ON_ERROR_STOP on
SET search_path TO mfi_accounting, public;

UPDATE product_scheme__transaction_accounting_rule__price_setup
SET is_deleted = true, updated_on = NOW(), updated_by = 'DPIC_LOCAL_NO_EXT_GST'
WHERE product_scheme_id = 2655
  AND transaction_accounting_rule_id = 135
  AND price_setup_code = 'PROC_FEE'
  AND is_deleted = false;
