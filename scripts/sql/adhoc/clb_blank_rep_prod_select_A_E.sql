-- READ-ONLY prod fact pack for blank REP_ACCT CLB poison rows.
-- Queues: 423952, 434237, 402411
-- Parents: 23404704 / 6001644197, 23478002 / 6001650487, 23061803 / 6001612031
-- Schema proven on mfi_integration_v3.4.2.5 entities + mfi_accounting_structure.sql
-- NOTE: loan_account_events_queue has parent_account_id (not loan_account_id).
-- Run against mfi_accounting. Export CSV and return before any UPDATE.

-- =============================================================================
-- A — stuck CLB rows
-- =============================================================================
SELECT
  q.id,
  q.parent_account_id AS loan_account_id,  -- entity column is parent_account_id
  q.event_type,
  q.event_status,
  q.filler_1,
  q.data::text AS data_text,
  q.created_on,
  q.updated_on,
  q.created_by,
  q.updated_by,
  q.is_deleted,
  q.reference_number
FROM mfi_accounting.loan_account_events_queue q
WHERE q.id IN (423952, 434237, 402411)
ORDER BY q.id;

-- =============================================================================
-- B — parent loan_account (+ LAN) for the three parents
-- =============================================================================
SELECT
  la.account_id,
  a.account_number AS lan,
  a.status AS account_status,
  la.loan_status,
  la.disbursement_status,
  la.parent_loan_account_id,
  la.has_child_accounts,
  la.external_ref_number,
  la.customer_id,
  la.loan_amount,
  la.disbursed_amount,
  la.is_deleted,
  la.created_on,
  la.updated_on
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id AND a.is_deleted = false
WHERE la.is_deleted = false
  AND (
    la.account_id IN (23404704, 23478002, 23061803)
    OR a.account_number IN ('6001644197', '6001650487', '6001612031')
  )
ORDER BY la.account_id;

-- =============================================================================
-- C — canonical parent/group repayment CASA sources
-- Priority: (1) loan_repayment_mode_details  (2) mandate → repayment_account_details
--           (3) parent DSBR (loan_disbursement_mode_details) — cross-check only
-- Critical for parent 23478002 / 6001650487 (all member REP blank in Downloads CSVs).
-- =============================================================================

-- C1 — parent loan_repayment_mode_details (DIRDR repayment CASA after parent create)
SELECT
  lrmd.id,
  lrmd.loan_account_id,
  a.account_number AS lan,
  lrmd.mode,
  lrmd.account_type,
  lrmd.account_number AS repayment_casa,
  lrmd.account_holder_name,
  lrmd.bank_name,
  lrmd.routing_type,
  lrmd.routing_value,
  lrmd.created_on,
  lrmd.updated_on
FROM mfi_accounting.loan_repayment_mode_details lrmd
JOIN mfi_accounting.account a ON a.id = lrmd.loan_account_id
WHERE lrmd.loan_account_id IN (23404704, 23478002, 23061803)
ORDER BY lrmd.loan_account_id, lrmd.id;

-- C2 — parent repayment_mandate_details → repayment_account_details (mandate CASA)
SELECT
  rmd.id AS mandate_id,
  rmd.loan_account_id,
  a.account_number AS lan,
  rmd.is_parent_account,
  rmd.mandate_status,
  rmd.mandate_category,
  rmd.mandate_type,
  rmd.purpose_code,
  rmd.group_id,
  rmd.group_name,
  rmd.group_formatted_id,
  rmd.repayment_account_details_id,
  rmd.is_deleted AS mandate_is_deleted,
  rad.account_number AS mandate_casa,
  rad.account_holder_name AS mandate_casa_holder,
  rad.account_type,
  rad.bank_name,
  rad.ifsc_code,
  rad.is_deleted AS rad_is_deleted,
  rmd.created_on AS mandate_created_on
FROM mfi_accounting.repayment_mandate_details rmd
JOIN mfi_accounting.account a ON a.id = rmd.loan_account_id
LEFT JOIN mfi_accounting.repayment_account_details rad
  ON rad.id = rmd.repayment_account_details_id
WHERE rmd.loan_account_id IN (23404704, 23478002, 23061803)
ORDER BY rmd.loan_account_id, rmd.is_deleted, rmd.id;

-- C3 — parent DSBR only (NOT canonical REP; useful when holder name matches blank REP)
SELECT
  ldmd.id,
  ldmd.loan_account_id,
  a.account_number AS lan,
  ldmd.mode,
  ldmd.account_type,
  ldmd.account_number AS dsbr_casa,
  ldmd.account_holder_name,
  ldmd.bank_name,
  ldmd.bank_customer_id,
  ldmd.is_deleted,
  ldmd.created_on
FROM mfi_accounting.loan_disbursement_mode_details ldmd
JOIN mfi_accounting.account a ON a.id = ldmd.loan_account_id
WHERE ldmd.loan_account_id IN (23404704, 23478002, 23061803)
  AND ldmd.is_deleted = false
ORDER BY ldmd.loan_account_id, ldmd.id;

-- C4 — optional: original disburseLoan CRR request (parent REP in request JSON)
-- Uncomment / tighten api_name filter if row volume is high.
SELECT
  c.id,
  c.loan_account_number,
  c.client_reference_number,
  c.status,
  c.uri,
  c.created_on,
  left(c.request, 4000) AS request_head
FROM mfi_accounting.client_request_response_log c
WHERE c.loan_account_number IN ('6001644197', '6001650487', '6001612031')
  AND (
    c.uri ILIKE '%disburseLoan%'
    OR c.uri ILIKE '%createOrUpdateLoanAccount%'
    OR COALESCE(c.transaction_type, '') ILIKE '%DISBURSE%'
  )
ORDER BY c.loan_account_number, c.created_on DESC
LIMIT 30;

-- =============================================================================
-- D — child loan_accounts already under these parents
-- =============================================================================
SELECT
  la.parent_loan_account_id,
  COUNT(*) AS child_count,
  COUNT(*) FILTER (WHERE la.loan_status = 'ACTIVE') AS active_cnt,
  COUNT(*) FILTER (WHERE la.loan_status = 'CLOSED') AS closed_cnt,
  COUNT(*) FILTER (WHERE la.is_deleted = true) AS deleted_cnt,
  array_agg(a.account_number ORDER BY la.account_id)
    FILTER (WHERE la.is_deleted = false) AS sample_child_lans
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.parent_loan_account_id IN (23404704, 23478002, 23061803)
GROUP BY la.parent_loan_account_id
ORDER BY la.parent_loan_account_id;

-- D detail (sample rows + child repayment CASA if any)
SELECT
  la.parent_loan_account_id,
  la.account_id AS child_account_id,
  a.account_number AS child_lan,
  a.status AS account_status,
  la.loan_status,
  la.disbursement_status,
  la.customer_id,
  la.is_deleted,
  lrmd.mode AS child_repay_mode,
  lrmd.account_number AS child_repayment_casa,
  lrmd.account_holder_name AS child_repayment_holder
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
LEFT JOIN mfi_accounting.loan_repayment_mode_details lrmd
  ON lrmd.loan_account_id = la.account_id
WHERE la.parent_loan_account_id IN (23404704, 23478002, 23061803)
ORDER BY la.parent_loan_account_id, la.account_id
LIMIT 200;

-- =============================================================================
-- E — jsonb extract: each member's REP_ACCT.account_number from queue data
-- =============================================================================
SELECT
  q.id AS queue_id,
  q.parent_account_id,
  m.m_ord AS member_ord,
  COALESCE(acc #>> '{purpose,0,code}', '') AS purpose_code,
  acc #>> '{account_number}' AS account_number,
  acc #>> '{account_holder_name}' AS account_holder_name,
  acc #>> '{product_type}' AS product_type,
  length(COALESCE(acc #>> '{account_number}', '')) AS account_number_len
FROM mfi_accounting.loan_account_events_queue q
CROSS JOIN LATERAL jsonb_array_elements(q.data::jsonb)
  WITH ORDINALITY AS m(m_elem, m_ord)
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(
    m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}',
    '[]'::jsonb
  )
) AS a(acc)
WHERE q.id IN (423952, 434237, 402411)
  AND COALESCE(acc #>> '{purpose,0,code}', '') = 'REP_ACCT'
ORDER BY q.id, m.m_ord;

-- E summary: blank vs non-blank REP per queue
SELECT
  q.id AS queue_id,
  q.parent_account_id,
  COUNT(*) AS rep_rows,
  COUNT(*) FILTER (
    WHERE NULLIF(BTRIM(acc #>> '{account_number}'), '') IS NULL
  ) AS blank_rep_rows,
  COUNT(*) FILTER (
    WHERE NULLIF(BTRIM(acc #>> '{account_number}'), '') IS NOT NULL
  ) AS nonblank_rep_rows,
  MAX(NULLIF(BTRIM(acc #>> '{account_number}'), '')) AS any_nonblank_rep_casa,
  MAX(NULLIF(BTRIM(acc #>> '{account_holder_name}'), ''))
    FILTER (WHERE NULLIF(BTRIM(acc #>> '{account_number}'), '') IS NOT NULL)
    AS any_nonblank_rep_holder
FROM mfi_accounting.loan_account_events_queue q
CROSS JOIN LATERAL jsonb_array_elements(q.data::jsonb) AS m(m_elem)
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(
    m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}',
    '[]'::jsonb
  )
) AS a(acc)
WHERE q.id IN (423952, 434237, 402411)
  AND COALESCE(acc #>> '{purpose,0,code}', '') = 'REP_ACCT'
GROUP BY q.id, q.parent_account_id
ORDER BY q.id;
