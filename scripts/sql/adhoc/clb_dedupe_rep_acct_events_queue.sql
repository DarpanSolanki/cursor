-- CLB poison-row ops: at most one purpose[0].code='REP_ACCT' per member in
-- loan_account_events_queue.data (createLoanAccountRequest.disbursement_repayment_account_details).
-- Keeps all non-REP_ACCT entries; for REP_ACCT keeps rn=1 (first) only.
--
-- Usage (psql / Yugabyte):
--   \set queue_id 402411
--   \i scripts/sql/adhoc/clb_dedupe_rep_acct_events_queue.sql
--
-- Or:
--   psql ... -v queue_id=402411 -f scripts/sql/adhoc/clb_dedupe_rep_acct_events_queue.sql
--
-- Verify before/after:
--   SELECT q.id,
--     (SELECT count(*) FROM jsonb_array_elements(q.data::jsonb) m(m_elem),
--       jsonb_array_elements(m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}') a(acc)
--      WHERE COALESCE(acc #>> '{purpose,0,code}', '') = 'REP_ACCT') AS rep_total,
--     (SELECT count(*) FROM (
--        SELECT m_ord FROM jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord),
--          jsonb_array_elements(m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}') a(acc)
--        WHERE COALESCE(acc #>> '{purpose,0,code}', '') = 'REP_ACCT'
--        GROUP BY m_ord HAVING count(*) > 1
--      ) d) AS members_with_dup_rep
--   FROM mfi_accounting.loan_account_events_queue q WHERE q.id = :'queue_id';

UPDATE mfi_accounting.loan_account_events_queue q
SET data = (
  SELECT jsonb_agg(
    jsonb_set(
      m_elem,
      '{createLoanAccountRequest,disbursement_repayment_account_details}',
      (
        SELECT COALESCE(jsonb_agg(acc_elem ORDER BY acc_ord), '[]'::jsonb)
        FROM (
          SELECT
            acc_elem,
            acc_ord,
            COALESCE(acc_elem #>> '{purpose,0,code}', '') AS code,
            ROW_NUMBER() OVER (
              PARTITION BY COALESCE(acc_elem #>> '{purpose,0,code}', '')
              ORDER BY acc_ord
            ) AS rn
          FROM jsonb_array_elements(
            COALESCE(
              m_elem #> '{createLoanAccountRequest,disbursement_repayment_account_details}',
              '[]'::jsonb
            )
          ) WITH ORDINALITY AS a(acc_elem, acc_ord)
        ) x
        WHERE x.code <> 'REP_ACCT' OR (x.code = 'REP_ACCT' AND x.rn = 1)
      ),
      true
    )
    ORDER BY m_ord
  )
  FROM jsonb_array_elements(q.data::jsonb) WITH ORDINALITY AS m(m_elem, m_ord)
)::text,
    updated_on = NOW()
WHERE q.id = :'queue_id'::bigint
  AND q.event_type = 'CLB'
  AND q.is_deleted = false;
