-- Prod NEFT v2 — bank remitter + customerId (tenant mfi)
-- Schema: mfi_masterdata.configuration
-- Replaces values from prod_neft_v2_configuration_update_3.4.2.3.sql:
--   remitter.account.number  02402970000091 → 02402970000315  (senderAccountNumber)
--   idcust                   474407         → 176438648         (customerId)
--
-- Run: SELECT first → UPDATE → verify → human COMMIT. Default ROLLBACK.

BEGIN;

-- Pre-check
SELECT prop_key, prop_value
FROM mfi_masterdata.configuration
WHERE prop_key IN (
  'hdfc.bank.neft.version.two.remitter.account.number',
  'hdfc.bank.neft.version.two.idcust'
)
ORDER BY prop_key;

UPDATE mfi_masterdata.configuration
SET prop_value = '02402970000315'
WHERE prop_key = 'hdfc.bank.neft.version.two.remitter.account.number';

UPDATE mfi_masterdata.configuration
SET prop_value = '176438648'
WHERE prop_key = 'hdfc.bank.neft.version.two.idcust';

-- Post-check (expect 2 rows with new values)
SELECT prop_key, prop_value
FROM mfi_masterdata.configuration
WHERE prop_key IN (
  'hdfc.bank.neft.version.two.remitter.account.number',
  'hdfc.bank.neft.version.two.idcust'
)
ORDER BY prop_key;

ROLLBACK;
-- COMMIT;  -- only after SELECT verify

-- =============================================================================
-- Redis clear (AFTER SQL COMMIT) — MASTER_DATA DB index = 1
-- Logical key = config__<prop_key>   (CONFIG_PREFIX=config_ + KEY_SEPARATOR=_)
-- Full key    = {novopay.service.environment.toLowerCase()}{tenantCode}_config__<prop_key>
--   env blank → mfi_config__…
--   env=prod  → prodmfi_config__…
-- Also clear optional MISS markers if present.
-- =============================================================================
--
-- Prefer SCAN then DEL (confirm env prefix first):
--   redis-cli -n 1 --scan --pattern '*config__hdfc.bank.neft.version.two.remitter.account.number'
--   redis-cli -n 1 --scan --pattern '*config__hdfc.bank.neft.version.two.idcust'
--   redis-cli -n 1 --scan --pattern '*config__MISSING__hdfc.bank.neft.version.two.remitter.account.number'
--   redis-cli -n 1 --scan --pattern '*config__MISSING__hdfc.bank.neft.version.two.idcust'
--
-- Explicit DEL (pick the prefix that matches SCAN — usually mfi_ or prodmfi_):
--
-- redis-cli -n 1 DEL \
--   mfi_config__hdfc.bank.neft.version.two.remitter.account.number \
--   mfi_config__hdfc.bank.neft.version.two.idcust \
--   mfi_config__MISSING__hdfc.bank.neft.version.two.remitter.account.number \
--   mfi_config__MISSING__hdfc.bank.neft.version.two.idcust
--
-- If novopay.service.environment=prod:
-- redis-cli -n 1 DEL \
--   prodmfi_config__hdfc.bank.neft.version.two.remitter.account.number \
--   prodmfi_config__hdfc.bank.neft.version.two.idcust \
--   prodmfi_config__MISSING__hdfc.bank.neft.version.two.remitter.account.number \
--   prodmfi_config__MISSING__hdfc.bank.neft.version.two.idcust
