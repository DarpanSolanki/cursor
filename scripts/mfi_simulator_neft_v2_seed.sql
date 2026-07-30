-- Local / QA: MFI bank simulator stubs for HDFC NEFT v2 (Chameleon JSON API).
--
-- Gold-standard shapes from **UAT CRR** (parent LAN 6000051775, 2026-04-15):
--   DISBURSEMENT_*_NEFT_NEF   — id 3899880 / client_ref 600005177520301 — doGenericSyncSTP (ST_NEF)
--   DISBURSEMENT_*_NEFT_NEF   — id 3899980 / client_ref 600005177510301 — second NEF leg
--   DISBURSEMENT_*_NEFT_NEI   — id 3899981 / 3899982 — ST_NEI (payment ref matches NEF client_ref)
--   NEFT_TRANSACTION_INQUIRY  — id 3899881 — Batch inquiry faxml (txtstatus PROCESSED)
--
-- CRR column `response` for ST_NEF/ST_NEI in UAT often looks like Java Map toString, e.g.
--   {isOverriden=false, responseString=2026105354951370, replyCode=0, errorCode=0, externalReferenceNo=600005177520301, ...}
-- because `CallBankAPIForDisbursementProcessor#resolveCrrResponse` falls back to `bank_api_response.toString()`
-- when raw `response` is blank/`{}`; JTF flattening puts replyCode/errorCode at the top level of that map.
--
-- Simulator `api_name` values follow JTF template names (not the bank URL path `doGenericSyncSTP`).
-- Chameleon matching: `validation` tokens must appear in the **request body string** (JSON or XML).
--
-- Usage:
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 -f scripts/mfi_simulator_neft_v2_seed.sql

BEGIN;

INSERT INTO mfi_simulator.simulator_config (api_name, request_type)
SELECT 'doGenericSyncSTPNEF', 'JSON'
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_simulator.simulator_config c
  WHERE c.api_name = 'doGenericSyncSTPNEF' AND upper(c.request_type) = 'JSON');

INSERT INTO mfi_simulator.simulator_config (api_name, request_type)
SELECT 'doGenericSyncSTPNEI', 'JSON'
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_simulator.simulator_config c
  WHERE c.api_name = 'doGenericSyncSTPNEI' AND upper(c.request_type) = 'JSON');

INSERT INTO mfi_simulator.simulator_config (api_name, request_type)
SELECT 'doGenericSyncSTPInquiry', 'JSON'
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_simulator.simulator_config c
  WHERE c.api_name = 'doGenericSyncSTPInquiry' AND upper(c.request_type) = 'JSON');

INSERT INTO mfi_simulator.simulator_response (simulator_config_id, validation, response_code, response, timeout_period, dynamic_response, is_callback_enabled)
SELECT sc.id, '', 200, '{}', 0, false, false
FROM mfi_simulator.simulator_config sc
WHERE sc.api_name IN ('doGenericSyncSTPNEF', 'doGenericSyncSTPNEI', 'doGenericSyncSTPInquiry') AND upper(sc.request_type) = 'JSON'
  AND NOT EXISTS (SELECT 1 FROM mfi_simulator.simulator_response sr WHERE sr.simulator_config_id = sc.id);

-- ST_NEF: envelope matches JTF doGenericSyncSTPNEF_responseTemplate / UAT internalReferenceNumber 2026105354951370
UPDATE mfi_simulator.simulator_response sr
SET validation = 'ST_NEF',
    response = $stpnef$
{"root":{"responseString":2026105354951370,"configVersionId":null,"maintenanceType":null,"status":{"isOverriden":false,"replyText":null,"internalReferenceNumber":2026105354951370,"replyCode":0,"memo":null,"errorCode":0,"validationErrors":null,"externalReferenceNo":600005177520301,"postingDate":null,"extendedReply":{"messages":null},"userReferenceNumber":null}}}
$stpnef$
FROM mfi_simulator.simulator_config sc
WHERE sr.simulator_config_id = sc.id AND sc.api_name = 'doGenericSyncSTPNEF' AND upper(sc.request_type) = 'JSON';

-- ST_NEI: same envelope; distinct internal ref as in UAT NEI rows (2026105355021396 family)
UPDATE mfi_simulator.simulator_response sr
SET validation = 'ST_NEI',
    response = $stpnei$
{"root":{"responseString":2026105355021396,"configVersionId":null,"maintenanceType":null,"status":{"isOverriden":false,"replyText":null,"internalReferenceNumber":2026105355021396,"replyCode":0,"memo":null,"errorCode":0,"validationErrors":null,"externalReferenceNo":600005177520301,"postingDate":null,"extendedReply":{"messages":null},"userReferenceNumber":null}}}
$stpnei$
FROM mfi_simulator.simulator_config sc
WHERE sr.simulator_config_id = sc.id AND sc.api_name = 'doGenericSyncSTPNEI' AND upper(sc.request_type) = 'JSON';

-- Inquiry: top-level faxml (CRR 3899881 / client_ref 600005177510301) — not root.status
UPDATE mfi_simulator.simulator_response sr
SET validation = 'GenericSyncSTPInquiryRequestDTO',
    response = $stpinq$
{"faxml":{"summary":{"countpmt":1,"sumpmt":48750},"header":{"dattxn":"2026-04-15T19:18:13","batchnumext":600005177510301,"iduser":"NOVSL_USER","codcurr":"INR","batchnum":123456,"datvalue":"2026-04-15","txtstatus":"PROCESSED","codpriority":8,"extsysname":"NOVSL","idcust":296355427,"idtxn":"ST_NEF","datpost":"2026-04-15","partnerid":"HDFCNOVSL","codstatus":3},"paymentlist":{"payment":{"BeneAddress_3":"","BeneAddress_4":"","BeneAddress_1":"","BeneAddress_2":"","referenceno":"HDFCH00009930438","BeneIFSCCODE":"ICIC0000104","RemitterAccountType":10,"codcurr":"INR","BeneName":"RAJ M","drbalavailable":0,"refstan":1,"CustId":296355427,"RemitterAccount":50100117339869,"Remitter_Address_1":"","Remitter_Address_2":"","Remitter_Address_3":"","Remitter_Address_4":"","errorcode":0,"RemitterName":"68A03127 JANARDHAN J NAIL","BeneAccountNumber":323001500061,"ContactDetailsID":"EML","Amount":48750,"ContactDetailsDETAIL":"NEFT-Chandivili@hdfcbank.bank.in","paymentrefno":600005177510301,"errorMessage":"Success","txndesc":"6000051775 DISB SHGDL ABCD","BeneAccountType":"","RemitInformation_5":"","RemitInformation_4":"","stanext":1,"RemitInformation_6":"","RemitInformation_1":"","RemitInformation_3":"","RemitInformation_2":""}}}}
$stpinq$
FROM mfi_simulator.simulator_config sc
WHERE sr.simulator_config_id = sc.id AND sc.api_name = 'doGenericSyncSTPInquiry' AND upper(sc.request_type) = 'JSON';

COMMIT;
