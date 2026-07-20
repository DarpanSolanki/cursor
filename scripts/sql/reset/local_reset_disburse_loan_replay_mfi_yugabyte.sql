-- Local QA only (Yugabyte / PostgreSQL, schema mfi_accounting).
-- Resets PARENT + ALL MEMBER loans for one JLG-style disburseLoan payload (same request, multiple LOS external refs).
--
-- \set variables (edit per request):
--   ext_ref           — parent disbursement_details.external_ref_number
--   member_ext_refs   — comma-separated member_details[].external_ref_number (no spaces, or trim applied)
--   lan               — optional parent account.account_number; leave '' to match parent only by ext_ref
--   group_id          — optional group_details.group_id for mandate branch; '' to skip
--   product_id — documentation only (echo)
--   customer_id — optional on mandate row when non-blank (echo + placeholder mandate)
--   repayment_account_* — REP_ACCT details derived from the request JSON
--   target_disb_status — loan_account.disbursement_status after reset (e.g. DTFC_SUCCESS)
--
-- For each matched loan (parent + members): canonical external_ref → status/fillers → UTR clear →
-- CRR soft-archive (no hard DELETE — keeps request/response for analysis) → queue (parent id) →
-- mandates → optional placeholder mandate (134488) → __LOCAL_DEDUPE_BYPASS suffix → account INACTIVE.
--
-- CRR table has no is_deleted; loan_account_number is varchar(24). Archived rows: loan_account_number
-- becomes '~' || id (excluded from app lookups); original LAN appended to uri as LOCAL_RESET_ORIG_LAN=...
--
-- Usage:
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
--     -f scripts/local_reset_disburse_loan_replay_mfi_yugabyte.sql

-- Required psql variables (pass via -v):
--   ext_ref            — disbursement_details.external_ref_number
--   member_ext_refs   — comma-separated member_details[].external_ref_number (empty string if member_details=null)
--   lan                — optional parent loan_details.account_number; '' to match by ext_ref only
--   group_id          — optional group_details.group_id; '' to skip mandate branch
--   product_id        — documentation only (echo)
--   customer_id       — optional on placeholder mandate when non-blank; pass '' if unknown
--   target_disb_status— loan_account.disbursement_status after reset (e.g. DTFC_SUCCESS)
--
-- After mandate repair: if no REGISTRATION_PENDING/ACTIVE row exists for a ref, inserts a minimal local SI mandate
-- linked to the request REP_ACCT CASA. Both the mandate and link are required by pre-disbursement validation.

BEGIN;
SET search_path TO mfi_accounting;

DROP TABLE IF EXISTS _ldr_loan;
DROP TABLE IF EXISTS _ldr_ref;

CREATE TEMP TABLE _ldr_ref (ref text NOT NULL PRIMARY KEY);
INSERT INTO _ldr_ref (ref) VALUES (btrim(:'ext_ref'));
INSERT INTO _ldr_ref (ref)
SELECT DISTINCT trim(both FROM u.f)
FROM unnest(string_to_array(btrim(:'member_ext_refs'), ',')) AS u(f)
WHERE btrim(:'member_ext_refs') <> ''
  AND trim(both FROM u.f) <> ''
ON CONFLICT DO NOTHING;

CREATE TEMP TABLE _ldr_loan (
  account_id bigint NOT NULL PRIMARY KEY,
  account_number text NOT NULL,
  canonical_ref text NOT NULL
);

INSERT INTO _ldr_loan (account_id, account_number, canonical_ref)
SELECT la.account_id, a.account_number, r.ref
FROM loan_account la
JOIN account a ON a.id = la.account_id
JOIN _ldr_ref r
  ON la.external_ref_number = r.ref
  OR la.external_ref_number = r.ref || '__LOCAL_DEDUPE_BYPASS'
WHERE la.is_deleted = false
  AND a.is_deleted = false;

-- 0) Canonical external_ref on every matched loan
UPDATE loan_account la
SET
  external_ref_number = s.canonical_ref,
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset_disburse_replay'
FROM _ldr_loan s
WHERE la.account_id = s.account_id;

-- 0b) Account ACTIVE (repair prior INACTIVE)
UPDATE account a
SET
  status = 'ACTIVE',
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset_disburse_replay'
FROM _ldr_loan s
WHERE a.id = s.account_id;

UPDATE loan_account la
SET
  disbursement_status = :'target_disb_status',
  filler_1 = '',
  filler_2 = '',
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset_disburse_replay'
FROM _ldr_loan s
WHERE la.account_id = s.account_id;

UPDATE loan_disbursement_mode_details d
SET
  utr_number = NULL,
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset_disburse_replay'
FROM _ldr_loan s
WHERE d.loan_account_id = s.account_id
  AND d.is_deleted = false;

-- Soft-archive CRR: preserve payloads; detach from real LAN so findOneByLoanAccountNumber* misses these rows.
UPDATE client_request_response_log c
SET
  uri = concat_ws(
    ' | ',
    NULLIF(btrim(coalesce(c.uri, '')), ''),
    'LOCAL_RESET_ORIG_LAN=' || c.loan_account_number,
    'LOCAL_RESET_ORIG_STATUS=' || c.status
  ),
  loan_account_number = '~' || c.id::text,
  status = 'LOCAL_RESET_ARCHIVED',
  eligible_for_retry = false,
  updated_on = CURRENT_TIMESTAMP
FROM _ldr_loan s
WHERE c.loan_account_number = s.account_number;

-- CLMT / CLB: parent_account_id = parent loan's account_id (prefer \set lan when set, else parent ext_ref)
UPDATE loan_account_events_queue q
SET
  is_deleted = true,
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset_disburse_replay'
WHERE q.is_deleted = false
  AND q.parent_account_id = COALESCE(
    (SELECT s.account_id FROM _ldr_loan s
     WHERE btrim(:'lan') <> '' AND s.account_number = btrim(:'lan')
     LIMIT 1),
    (SELECT s.account_id FROM _ldr_loan s
     WHERE s.canonical_ref = btrim(:'ext_ref')
     LIMIT 1)
  );

UPDATE repayment_mandate_details rmd
SET
  loan_account_id = NULL,
  is_deleted = false,
  mandate_status = CASE
    WHEN rmd.mandate_status = 'CANCELLED' OR rmd.is_deleted THEN 'REGISTRATION_PENDING'
    ELSE rmd.mandate_status
  END,
  rejected_or_cancelled_date = CASE
    WHEN rmd.mandate_status = 'CANCELLED' OR rmd.is_deleted THEN NULL
    ELSE rmd.rejected_or_cancelled_date
  END
WHERE rmd.loan_account_id IN (SELECT account_id FROM _ldr_loan)
   OR rmd.loan_application_id IN (SELECT ref FROM _ldr_ref)
   OR (btrim(:'group_id') <> '' AND rmd.group_id = CAST(btrim(:'group_id') AS bigint));

-- 7b) Local-only: ensure the request REP_ACCT exists and mandates are linked to it.
INSERT INTO repayment_account_details (
  account_number,
  account_type,
  ifsc_code,
  bank_name,
  hold_status,
  lien_status,
  created_on,
  created_by,
  updated_on,
  updated_by,
  is_deleted,
  account_holder_name
)
SELECT
  btrim(:'repayment_account_number'),
  btrim(:'repayment_account_type'),
  NULLIF(btrim(:'repayment_account_ifsc'), ''),
  NULLIF(btrim(:'repayment_account_bank_name'), ''),
  0,
  0,
  CURRENT_TIMESTAMP,
  'local_reset_disburse_replay',
  CURRENT_TIMESTAMP,
  'local_reset_disburse_replay',
  false,
  NULLIF(btrim(:'repayment_account_holder_name'), '')
WHERE btrim(:'repayment_account_number') <> ''
  AND NOT EXISTS (
    SELECT 1
    FROM repayment_account_details rad
    WHERE rad.account_number = btrim(:'repayment_account_number')
      AND rad.is_deleted = false
  );

INSERT INTO repayment_mandate_details (
  loan_application_id,
  loan_account_id,
  group_id,
  customer_id,
  repayment_account_details_id,
  start_date,
  end_date,
  repayment_frequency,
  purpose_code,
  max_amount,
  mandate_type,
  mandate_status,
  mandate_category,
  created_on,
  created_by,
  is_deleted,
  is_parent_account
)
SELECT
  r.ref,
  NULL,
  CASE WHEN btrim(:'group_id') = '' THEN NULL ELSE CAST(btrim(:'group_id') AS bigint) END,
  CASE WHEN btrim(:'customer_id') = '' THEN NULL ELSE CAST(btrim(:'customer_id') AS bigint) END,
  (
    SELECT rad.id
    FROM repayment_account_details rad
    WHERE rad.account_number = btrim(:'repayment_account_number')
      AND rad.is_deleted = false
    ORDER BY rad.id
    LIMIT 1
  ),
  (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - 30,
  DATE '2099-01-01',
  'MONTHLY',
  'LOAN_REPMT',
  1000000,
  'RECURRING',
  'REGISTRATION_PENDING',
  'SI',
  CURRENT_TIMESTAMP,
  'local_reset_disburse_replay',
  false,
  false
FROM _ldr_ref r
WHERE NOT EXISTS (
  SELECT 1
  FROM repayment_mandate_details m
  WHERE m.loan_application_id = r.ref
    AND m.mandate_status IN ('REGISTRATION_PENDING', 'ACTIVE')
    AND m.is_deleted = false
);

UPDATE repayment_mandate_details rmd
SET repayment_account_details_id = (
  SELECT rad.id
  FROM repayment_account_details rad
  WHERE rad.account_number = btrim(:'repayment_account_number')
    AND rad.is_deleted = false
  ORDER BY rad.id
  LIMIT 1
)
WHERE btrim(:'repayment_account_number') <> ''
  AND rmd.loan_application_id IN (SELECT ref FROM _ldr_ref)
  AND rmd.mandate_status IN ('REGISTRATION_PENDING', 'ACTIVE')
  AND rmd.is_deleted = false;

UPDATE loan_account la
SET
  external_ref_number = s.canonical_ref || '__LOCAL_DEDUPE_BYPASS',
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset_disburse_replay'
FROM _ldr_loan s
WHERE la.account_id = s.account_id;

UPDATE account a
SET
  status = 'INACTIVE',
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'local_reset_disburse_replay'
FROM _ldr_loan s
WHERE a.id = s.account_id;

SELECT 'local_reset_disburse_replay scope' AS note, l.account_id, l.account_number, l.canonical_ref
FROM _ldr_loan l
ORDER BY l.canonical_ref;

DROP TABLE IF EXISTS _ldr_loan;
DROP TABLE IF EXISTS _ldr_ref;

COMMIT;

\echo ''
\echo '=== JLG local reset done (parent + all member_ext_refs) ========================'
\echo 'See SELECT above: each row got suffix + INACTIVE; CRR soft-archived per LAN (rows kept for analysis).'
\echo 'ext_ref=' :'ext_ref' ' member_ext_refs=' :'member_ext_refs'
\echo 'If SELECT returned 0 rows, no loan matched — fix ext_ref / member_ext_refs / DB.'
\echo 'Mandate: one active/pending row per ref linked to request REP_ACCT (avoids missing/unlinked mandate failure).'
\echo 'Request: set expected_disbursement_date (epoch ms) and a numeric client_reference_number.'
\echo '================================================================================'
\echo ''
