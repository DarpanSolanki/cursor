-- Clone DPI-related internal accounts from source office to target office (local dev).
-- IADs match setup_local_dev_product_6367.sql placeholder mapping + billing cat 1330.
-- Usage: psql ... -v source_office_id=1 -v target_office_id=2 -f seed_office_internal_accounts_for_dpi.sql

\set ON_ERROR_STOP on

INSERT INTO mfi_accounting.internal_account (
  office_id, internal_account_definition_id, code, name, description,
  balance_limit, created_on, created_by, updated_on, updated_by, is_deleted
)
SELECT :target_office_id, src.internal_account_definition_id, src.code, src.name, src.description,
       src.balance_limit, NOW(), 'DPIC_LOCAL_DEV', NOW(), 'DPIC_LOCAL_DEV', false
FROM mfi_accounting.internal_account src
WHERE src.office_id = :source_office_id
  AND src.is_deleted = false
  AND src.internal_account_definition_id IN (5, 6, 8, 12, 28, 6293)
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.internal_account tgt
    WHERE tgt.office_id = :target_office_id
      AND tgt.internal_account_definition_id = src.internal_account_definition_id
      AND tgt.is_deleted = false
  );

\echo 'Office' :target_office_id 'DPI internal accounts:'
SELECT ia.office_id, ia.internal_account_definition_id, ia.code, ia.name
FROM mfi_accounting.internal_account ia
WHERE ia.office_id = :target_office_id
  AND ia.internal_account_definition_id IN (5, 6, 8, 12, 28, 6293)
  AND ia.is_deleted = false
ORDER BY ia.internal_account_definition_id;
