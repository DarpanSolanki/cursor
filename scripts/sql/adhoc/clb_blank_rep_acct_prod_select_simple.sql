-- READ-ONLY prod pull — five simple queries (run separately; no UNION).
-- Stuck CLB queues: 423952, 434237, 402411
-- Parents: 23404704, 23478002, 23061803

-- =============================================================================
-- Query 1 — stuck queues only
-- =============================================================================
SELECT id, parent_account_id, event_type, event_status, filler_1, created_on, updated_on
FROM mfi_accounting.loan_account_events_queue
WHERE id IN (423952, 434237, 402411);

-- =============================================================================
-- Query 2 — parent repayment CASA (fill authority)
-- =============================================================================
SELECT loan_account_id, mode, account_type, account_number, account_holder_name
FROM mfi_accounting.loan_repayment_mode_details
WHERE loan_account_id IN (23404704, 23478002, 23061803);

-- =============================================================================
-- Query 3 — mandate fallback
-- =============================================================================
SELECT rmd.loan_account_id, rad.account_number, rad.account_holder_name
FROM mfi_accounting.repayment_mandate_details rmd
JOIN mfi_accounting.repayment_account_details rad
  ON rad.id = rmd.repayment_account_details_id
WHERE rmd.loan_account_id IN (23404704, 23478002, 23061803)
  AND COALESCE(rmd.is_deleted, false) = false;

-- =============================================================================
-- Query 4 — children count per parent
-- =============================================================================
SELECT parent_loan_account_id, COUNT(*) AS child_cnt
FROM mfi_accounting.loan_account
WHERE parent_loan_account_id IN (23404704, 23478002, 23061803)
  AND is_deleted = false
GROUP BY parent_loan_account_id;

-- =============================================================================
-- Query 5 — blank REP check (optional; needs jsonb on data column)
-- Export Query 1 data column if jsonb not available in your client.
-- =============================================================================
SELECT
  q.id AS queue_id,
  q.parent_account_id,
  m.m_ord AS member_ord,
  acc #>> '{account_number}' AS rep_account_number,
  acc #>> '{account_holder_name}' AS rep_holder_name
FROM mfi_accounting.loan_account_events_queue q
CROSS JOIN LATERAL jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord)
CROSS JOIN LATERAL jsonb_array_elements(
  m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}'
) AS a(acc)
WHERE q.id IN (423952, 434237, 402411)
  AND acc #>> '{purpose,0,code}' = 'REP_ACCT'
ORDER BY q.id, m.m_ord;
