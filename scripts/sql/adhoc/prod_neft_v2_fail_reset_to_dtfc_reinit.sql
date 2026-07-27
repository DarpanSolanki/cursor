-- PROD ops (mfi_accounting): soft-archive FAIL NEFT_NEF CRR → set DTFC_SUCCESS for re-fire.
-- ⚠️ ROLLBACK by default. Uncomment COMMIT only after bank confirms these LANs were NOT credited.
-- Re-fire: disburseLoan headers.function_sub_code = DTFC_SUCCESS (parent/INDL); CLMT queue if child.
--
-- Soft-archive (minimal / contract-native first):
--   loan_account_number → '~'||id   — LAN-keyed finders / SUCCESS skip miss the row
--   status               → leave 'FAIL' (code contract; do NOT invent LOCAL_RESET_ARCHIVED / PROD_*)
--   eligible_for_retry   → false    — retry job needs status='FAIL' AND eligible_for_retry=TRUE
--   uri                  → ORIG_LAN forensics only
-- Checklist: Minimal permanent = FAIL + retry=false + optional ~ + DTFC_SUCCESS | Contract-native=Yes(FAIL) | Anything lost=No
--
-- Impact (short): FAIL + '~' is safer/simpler than a custom archive status.
--   SUCCESS skip / LAN lookup / ExternalReferenceNoUtil → no row on real LAN (detached).
--   Retry job → blocked by eligible_for_retry=false (status stays FAIL by design).
--   Remaining FAIL rows still on a real LAN still bump bank refs (FAIL.equals).
--   Residual: client_ref callbacks still find the row; loan lookup via '~'||id misses.
--
-- Bank non-credit confirm is mandatory before COMMIT.

SET search_path TO mfi_accounting;

-- Paste LANs here (or leave empty and use window discovery below).
-- Example: WHERE … AND c.loan_account_number IN ('6001…','6002…')

-- 0) FAIL NEF since deploy window (~2026-07-18 17:00 IST), exclude any LAN with SUCCESS NEF
SELECT c.id, c.loan_account_number AS lan, c.client_reference_number,
       c.transaction_type, c.status, c.system_date,
       left(coalesce(c.response, ''), 160) AS response_preview
FROM client_request_response_log c
WHERE c.partner = 'Hdfc'
  AND c.status = 'FAIL'
  AND (c.transaction_type = 'DISBURSEMENT_NEFT_NEF'
       OR c.transaction_type LIKE '%NEFT_NEF%')
  AND c.loan_account_number NOT LIKE '~%'
  AND c.system_date >= TIMESTAMPTZ '2026-07-18 17:00:00+05:30'
  -- AND c.loan_account_number IN ('lan1','lan2')
  AND NOT EXISTS (
    SELECT 1
    FROM client_request_response_log s
    WHERE s.loan_account_number = c.loan_account_number
      AND s.partner = 'Hdfc'
      AND s.status = 'SUCCESS'
      AND s.loan_account_number NOT LIKE '~%'
      AND (s.transaction_type = 'DISBURSEMENT_NEFT_NEF'
           OR s.transaction_type LIKE '%NEFT_NEF%')
  )
ORDER BY c.system_date DESC;

BEGIN;

-- Working set (same filters as SELECT 0)
DROP TABLE IF EXISTS _neft_reset;
CREATE TEMP TABLE _neft_reset AS
SELECT DISTINCT c.loan_account_number AS lan, la.account_id
FROM client_request_response_log c
JOIN account a ON a.account_number = c.loan_account_number AND a.is_deleted = false
JOIN loan_account la ON la.account_id = a.id AND la.is_deleted = false
WHERE c.partner = 'Hdfc'
  AND c.status = 'FAIL'
  AND (c.transaction_type = 'DISBURSEMENT_NEFT_NEF'
       OR c.transaction_type LIKE '%NEFT_NEF%')
  AND c.loan_account_number NOT LIKE '~%'
  AND c.system_date >= TIMESTAMPTZ '2026-07-18 17:00:00+05:30'
  -- AND c.loan_account_number IN ('lan1','lan2')
  AND NOT EXISTS (
    SELECT 1
    FROM client_request_response_log s
    WHERE s.loan_account_number = c.loan_account_number
      AND s.partner = 'Hdfc'
      AND s.status = 'SUCCESS'
      AND s.loan_account_number NOT LIKE '~%'
      AND (s.transaction_type = 'DISBURSEMENT_NEFT_NEF'
           OR s.transaction_type LIKE '%NEFT_NEF%')
  )
  AND la.loan_status NOT IN ('CLOSED', 'CANCELLED');

SELECT * FROM _neft_reset ORDER BY lan;

-- 1) Soft-archive FAIL NEF CRR: detach LAN only; leave status = FAIL
UPDATE client_request_response_log c
SET
  uri = concat_ws(
    ' | ',
    NULLIF(btrim(coalesce(c.uri, '')), ''),
    'PROD_NEFT_V2_FAIL_RESET_ORIG_LAN=' || c.loan_account_number
  ),
  loan_account_number = '~' || c.id::text,
  eligible_for_retry = false,
  updated_on = CURRENT_TIMESTAMP
FROM _neft_reset t
WHERE c.loan_account_number = t.lan
  AND c.partner = 'Hdfc'
  AND c.status = 'FAIL'
  AND (c.transaction_type = 'DISBURSEMENT_NEFT_NEF'
       OR c.transaction_type LIKE '%NEFT_NEF%');

-- 2) loan_account → DTFC_SUCCESS + clear fillers
UPDATE loan_account la
SET
  disbursement_status = 'DTFC_SUCCESS',
  filler_1 = '',
  filler_2 = '',
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'prod_neft_v2_fail_reset'
FROM _neft_reset t
WHERE la.account_id = t.account_id
  AND la.is_deleted = false;

-- 3) Clear UTR (optional but safe)
UPDATE loan_disbursement_mode_details d
SET utr_number = NULL, updated_on = CURRENT_TIMESTAMP, updated_by = 'prod_neft_v2_fail_reset'
FROM _neft_reset t
WHERE d.loan_account_id = t.account_id AND d.is_deleted = false;

-- 4) CLMT queue (optional — parent_account_id)
UPDATE loan_account_events_queue q
SET
  data = jsonb_set(coalesce(q.data, '{}'::jsonb), '{disbursement_status}', '"DTFC_SUCCESS"', true),
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'prod_neft_v2_fail_reset'
FROM _neft_reset t
WHERE q.parent_account_id = t.account_id AND q.is_deleted = false;

ROLLBACK;
-- COMMIT;  -- human only, after review + bank non-credit confirm
