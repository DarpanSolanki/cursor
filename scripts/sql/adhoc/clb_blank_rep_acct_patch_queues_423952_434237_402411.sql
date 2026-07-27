-- Prod ops: patch blank REP_ACCT on stuck CLB queues (one UPDATE per queue).
-- Evidence: /home/darpan/Downloads/has_child_accounts.csv (C1_LRMD + C2_MANDATE)
-- Pre/post: simple SELECTs only. Default ROLLBACK — human COMMIT after review.
-- Replay: childLoanEventProcessingBatchJob
-- Per queue: UPDATE → member REP counts → queue row (filler_1 cleared).
-- Safety: Only account_number + account_holder_name; all other keys preserved via jsonb ||
--   (CASE only when purpose=REP_ACCT AND blank account_number; DSBR / filled REP → ELSE acc).

BEGIN;

-- PRE — Query 1
SELECT id, parent_account_id, event_type, event_status, filler_1, created_on, updated_on
FROM mfi_accounting.loan_account_events_queue
WHERE id IN (423952, 434237, 402411);

-- PRE — Query 5 (blank REP rows)
SELECT q.id AS queue_id, m.m_ord AS member_ord,
       acc #>> '{account_number}' AS rep_account_number
FROM mfi_accounting.loan_account_events_queue q
CROSS JOIN LATERAL jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord)
CROSS JOIN LATERAL jsonb_array_elements(
  m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}'
) AS a(acc)
WHERE q.id IN (423952, 434237, 402411)
  AND acc #>> '{purpose,0,code}' = 'REP_ACCT'
ORDER BY q.id, m.m_ord;

-- ---------------------------------------------------------------------------
-- Queue 402411 | parent 23061803 / 6001612031
-- CSV: C1_LRMD 50100881952140 MYSORE MALLI SHG | member 1 already filled; 2-9 blank
-- ---------------------------------------------------------------------------
UPDATE mfi_accounting.loan_account_events_queue q
SET
  data = (
    SELECT jsonb_agg(
      jsonb_set(
        m_elem,
        '{createLoanAccountRequest,disbursement_repayment_account_details}',
        (
          SELECT jsonb_agg(
            CASE
              -- Only account_number + account_holder_name; all other keys preserved via jsonb ||
              WHEN acc #>> '{purpose,0,code}' = 'REP_ACCT'
                   AND COALESCE(BTRIM(acc #>> '{account_number}'), '') = ''
              THEN acc || jsonb_build_object(
                'account_number', '50100881952140',
                'account_holder_name', 'MYSORE MALLI SHG'
              )
              ELSE acc
            END
            ORDER BY acc_ord
          )
          FROM jsonb_array_elements(
            m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}'
          ) WITH ORDINALITY AS t(acc, acc_ord)
        ),
        true
      )
      ORDER BY m_ord
    )
    FROM jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord)
  )::text,
  filler_1 = NULL,
  updated_on = NOW()
WHERE q.id = 402411
  AND q.event_type = 'CLB'
  AND q.event_status = 'P'
  AND q.is_deleted = false;

-- Verify 402411 — REP member counts (expect blank_rep_cnt = 0)
SELECT
  402411 AS queue_id,
  COUNT(*) FILTER (WHERE NULLIF(TRIM(acc #>> '{account_number}'), '') IS NULL) AS blank_rep_cnt,
  COUNT(*) FILTER (WHERE NULLIF(TRIM(acc #>> '{account_number}'), '') IS NOT NULL) AS filled_rep_cnt
FROM mfi_accounting.loan_account_events_queue q
CROSS JOIN LATERAL jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord)
CROSS JOIN LATERAL jsonb_array_elements(
  m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}'
) AS a(acc)
WHERE q.id = 402411
  AND acc #>> '{purpose,0,code}' = 'REP_ACCT';

-- Verify 402411 — queue row (expect filler_1 NULL, event_status P)
SELECT id, event_status, filler_1, updated_on
FROM mfi_accounting.loan_account_events_queue
WHERE id = 402411;

-- ---------------------------------------------------------------------------
-- Queue 423952 | parent 23404704 / 6001644197
-- CSV: C1_LRMD 50100879754726 MAHILA AMANAT SHG HANMANTIYA | member 4 filled; rest blank
-- ---------------------------------------------------------------------------
UPDATE mfi_accounting.loan_account_events_queue q
SET
  data = (
    SELECT jsonb_agg(
      jsonb_set(
        m_elem,
        '{createLoanAccountRequest,disbursement_repayment_account_details}',
        (
          SELECT jsonb_agg(
            CASE
              -- Only account_number + account_holder_name; all other keys preserved via jsonb ||
              WHEN acc #>> '{purpose,0,code}' = 'REP_ACCT'
                   AND COALESCE(BTRIM(acc #>> '{account_number}'), '') = ''
              THEN acc || jsonb_build_object(
                'account_number', '50100879754726',
                'account_holder_name', 'MAHILA AMANAT SHG HANMANTIYA'
              )
              ELSE acc
            END
            ORDER BY acc_ord
          )
          FROM jsonb_array_elements(
            m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}'
          ) WITH ORDINALITY AS t(acc, acc_ord)
        ),
        true
      )
      ORDER BY m_ord
    )
    FROM jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord)
  )::text,
  filler_1 = NULL,
  updated_on = NOW()
WHERE q.id = 423952
  AND q.event_type = 'CLB'
  AND q.event_status = 'P'
  AND q.is_deleted = false;

-- Verify 423952 — REP member counts (expect blank_rep_cnt = 0)
SELECT
  423952 AS queue_id,
  COUNT(*) FILTER (WHERE NULLIF(TRIM(acc #>> '{account_number}'), '') IS NULL) AS blank_rep_cnt,
  COUNT(*) FILTER (WHERE NULLIF(TRIM(acc #>> '{account_number}'), '') IS NOT NULL) AS filled_rep_cnt
FROM mfi_accounting.loan_account_events_queue q
CROSS JOIN LATERAL jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord)
CROSS JOIN LATERAL jsonb_array_elements(
  m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}'
) AS a(acc)
WHERE q.id = 423952
  AND acc #>> '{purpose,0,code}' = 'REP_ACCT';

-- Verify 423952 — queue row (expect filler_1 NULL, event_status P)
SELECT id, event_status, filler_1, updated_on
FROM mfi_accounting.loan_account_events_queue
WHERE id = 423952;

-- ---------------------------------------------------------------------------
-- Queue 434237 | parent 23478002 / 6001650487
-- CSV: C1_LRMD 50100883398981 ASHIRWAD SHG AVALDEWADI MASADE | all 7 members blank
-- ---------------------------------------------------------------------------
UPDATE mfi_accounting.loan_account_events_queue q
SET
  data = (
    SELECT jsonb_agg(
      jsonb_set(
        m_elem,
        '{createLoanAccountRequest,disbursement_repayment_account_details}',
        (
          SELECT jsonb_agg(
            CASE
              -- Only account_number + account_holder_name; all other keys preserved via jsonb ||
              WHEN acc #>> '{purpose,0,code}' = 'REP_ACCT'
                   AND COALESCE(BTRIM(acc #>> '{account_number}'), '') = ''
              THEN acc || jsonb_build_object(
                'account_number', '50100883398981',
                'account_holder_name', 'ASHIRWAD SHG AVALDEWADI MASADE'
              )
              ELSE acc
            END
            ORDER BY acc_ord
          )
          FROM jsonb_array_elements(
            m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}'
          ) WITH ORDINALITY AS t(acc, acc_ord)
        ),
        true
      )
      ORDER BY m_ord
    )
    FROM jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord)
  )::text,
  filler_1 = NULL,
  updated_on = NOW()
WHERE q.id = 434237
  AND q.event_type = 'CLB'
  AND q.event_status = 'P'
  AND q.is_deleted = false;

-- Verify 434237 — REP member counts (expect blank_rep_cnt = 0)
SELECT
  434237 AS queue_id,
  COUNT(*) FILTER (WHERE NULLIF(TRIM(acc #>> '{account_number}'), '') IS NULL) AS blank_rep_cnt,
  COUNT(*) FILTER (WHERE NULLIF(TRIM(acc #>> '{account_number}'), '') IS NOT NULL) AS filled_rep_cnt
FROM mfi_accounting.loan_account_events_queue q
CROSS JOIN LATERAL jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord)
CROSS JOIN LATERAL jsonb_array_elements(
  m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}'
) AS a(acc)
WHERE q.id = 434237
  AND acc #>> '{purpose,0,code}' = 'REP_ACCT';

-- Verify 434237 — queue row (expect filler_1 NULL, event_status P)
SELECT id, event_status, filler_1, updated_on
FROM mfi_accounting.loan_account_events_queue
WHERE id = 434237;

-- POST — all queues summary (optional final check)
SELECT id, parent_account_id, event_type, event_status, filler_1, created_on, updated_on
FROM mfi_accounting.loan_account_events_queue
WHERE id IN (423952, 434237, 402411);

-- POST — Query 5 detail (expect no empty rep_account_number)
SELECT q.id AS queue_id, m.m_ord AS member_ord,
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

-- Human: COMMIT; then run childLoanEventProcessingBatchJob
ROLLBACK;
