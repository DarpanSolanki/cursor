-- Backfill `loan_account_events_queue.filler_2` for pending CLMT rows.
--
-- This is a data-fix to unblock LAR CASH override, which matches pending CLMT rows by `filler_2`
-- (child external_ref_number). Backfill it from `data.external_ref_number`.
--
-- Optional: add `AND q.parent_account_id = <PARENT_ID>` to scope to one parent.

UPDATE mfi_accounting.loan_account_events_queue q
SET filler_2 = q.data::jsonb->>'external_ref_number'
WHERE q.is_deleted = false
  AND q.event_type = 'CLMT'
  AND q.event_status = 'P'
  AND q.filler_2 IS NULL
  AND (q.data::jsonb ? 'external_ref_number')
  AND NULLIF(btrim(q.data::jsonb->>'external_ref_number'), '') IS NOT NULL;

