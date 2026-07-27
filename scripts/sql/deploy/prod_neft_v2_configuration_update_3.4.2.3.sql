-- Production NEFT v2 config (mfi_integration_v3.4.2.3)
-- Schema: mfi_masterdata.configuration
-- Prerequisite: V9000462 already applied

UPDATE mfi_masterdata.configuration SET prop_value = 'https://obpstp.hbctxdom.com:9447/GenericSyncSTPTxn/GenericSyncSTPRestService/doGenericSyncSTP' WHERE prop_key = 'hdfc.bank.neft.version.two.nef.url';
UPDATE mfi_masterdata.configuration SET prop_value = 'https://obpstp.hbctxdom.com:9447/GenericSyncSTPInq/GenericSyncSTPRestService/doGenericSyncSTP' WHERE prop_key = 'hdfc.bank.neft.version.two.nei.url';
UPDATE mfi_masterdata.configuration SET prop_value = 'https://obpstp.hbctxdom.com:9447/GenericSyncSTPInq/GenericSyncSTPBatchInquiryRestService/doGenericSyncSTPInquiry' WHERE prop_key = 'hdfc.bank.neft.version.two.inquiry.url';
UPDATE mfi_masterdata.configuration SET prop_value = '08' WHERE prop_key = 'hdfc.bank.neft.version.two.bank.code';
UPDATE mfi_masterdata.configuration SET prop_value = '089999' WHERE prop_key = 'hdfc.bank.neft.version.two.transaction.branch';
UPDATE mfi_masterdata.configuration SET prop_value = '50000012' WHERE prop_key = 'hdfc.bank.neft.version.two.transacting.party.code';
UPDATE mfi_masterdata.configuration SET prop_value = 'NOVSL' WHERE prop_key = 'hdfc.bank.neft.version.two.channel';
UPDATE mfi_masterdata.configuration SET prop_value = 'NOVSLUSER' WHERE prop_key = 'hdfc.bank.neft.version.two.user.id';
UPDATE mfi_masterdata.configuration SET prop_value = 'HDFCNOVSL' WHERE prop_key = 'hdfc.bank.neft.version.two.partner.id';
UPDATE mfi_masterdata.configuration SET prop_value = 'NOVSL' WHERE prop_key = 'hdfc.bank.neft.version.two.extsysname';
UPDATE mfi_masterdata.configuration SET prop_value = '474407' WHERE prop_key = 'hdfc.bank.neft.version.two.idcust';
UPDATE mfi_masterdata.configuration SET prop_value = '08' WHERE prop_key = 'hdfc.bank.neft.version.two.codpriority';
UPDATE mfi_masterdata.configuration SET prop_value = 'INR' WHERE prop_key = 'hdfc.bank.neft.version.two.codcurr';
UPDATE mfi_masterdata.configuration SET prop_value = 'NOVSLUSER' WHERE prop_key = 'hdfc.bank.neft.version.two.iduser';
UPDATE mfi_masterdata.configuration SET prop_value = 'Y' WHERE prop_key = 'hdfc.bank.neft.version.two.forcedebit';
UPDATE mfi_masterdata.configuration SET prop_value = '02402970000091' WHERE prop_key = 'hdfc.bank.neft.version.two.remitter.account.number';
UPDATE mfi_masterdata.configuration SET prop_value = '10' WHERE prop_key = 'hdfc.bank.neft.version.two.remitter.account.type';
UPDATE mfi_masterdata.configuration SET prop_value = 'HDFC BANK 1' WHERE prop_key = 'hdfc.bank.neft.version.two.remitter.name';
UPDATE mfi_masterdata.configuration SET prop_value = 'HDFCNOVSL' WHERE prop_key = 'hdfc.bank.neft.version.two.txnuploadname';

-- =============================================================================
-- Redis clear (after SQL) — MASTER_DATA DB index = 1
-- Logical key = config__<prop_key>
-- Full key    = {novopay.service.environment}{tenantCode}_config__<prop_key>
--   e.g. tenant mfi, empty env → mfi_config__hdfc.bank.neft.version.two.nef.url
-- =============================================================================
-- redis-cli -n 1 DEL \
--   mfi_config__hdfc.bank.neft.version.two.nef.url \
--   mfi_config__hdfc.bank.neft.version.two.nei.url \
--   mfi_config__hdfc.bank.neft.version.two.inquiry.url \
--   mfi_config__hdfc.bank.neft.version.two.bank.code \
--   mfi_config__hdfc.bank.neft.version.two.transaction.branch \
--   mfi_config__hdfc.bank.neft.version.two.transacting.party.code \
--   mfi_config__hdfc.bank.neft.version.two.channel \
--   mfi_config__hdfc.bank.neft.version.two.user.id \
--   mfi_config__hdfc.bank.neft.version.two.partner.id \
--   mfi_config__hdfc.bank.neft.version.two.extsysname \
--   mfi_config__hdfc.bank.neft.version.two.idcust \
--   mfi_config__hdfc.bank.neft.version.two.codpriority \
--   mfi_config__hdfc.bank.neft.version.two.codcurr \
--   mfi_config__hdfc.bank.neft.version.two.iduser \
--   mfi_config__hdfc.bank.neft.version.two.forcedebit \
--   mfi_config__hdfc.bank.neft.version.two.remitter.account.number \
--   mfi_config__hdfc.bank.neft.version.two.remitter.account.type \
--   mfi_config__hdfc.bank.neft.version.two.remitter.name \
--   mfi_config__hdfc.bank.neft.version.two.txnuploadname
--
-- Or pattern (confirm env prefix first):
--   redis-cli -n 1 --scan --pattern '*config__hdfc.bank.neft.version.two.*' | xargs -r redis-cli -n 1 DEL
