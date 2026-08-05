-- Local fixture hygiene — restore uniqueness of child queue rows by external ref.
--
-- Why: `DoGenericSyncSTPBankNeftCallBackProcessor.findClmtQueueRowWithRetry` resolves
-- the child CLMT row via `findOneByFiller2(childExtRef, 'CLMT')` — a GLOBAL lookup with
-- no parent scope. Canonical local payloads reuse fixed member external refs
-- (e.g. 134020221), so every SHG/JLG group disbursement adds another CLMT row with the
-- same filler_2. Once more than one live row exists the lookup throws
--
--   IncorrectResultSizeDataAccessException: Query did not return a unique result: N results
--
-- the NEFT child callback aborts, the CLMT row stays P/NEFT_STAGE_1_PENDING, and
-- `syncParentAfterChildQueueProgress` never fires — the group parent is stuck at
-- PARENT_SUCCESS forever. That is a local fixture artifact (production external refs are
-- unique per loan application), so the fix belongs in the reset path, not the product.
--
-- Keeps the newest row per (filler_2, event_type) and soft-deletes the older duplicates.
-- Local only (127.0.0.1:5433). Idempotent.
--   bash scripts/bin/db-local-write.sh --file scripts/sql/reset/local_dedupe_child_queue_rows.sql

SET search_path TO mfi_accounting;

UPDATE loan_account_events_queue q
SET is_deleted = true,
    updated_on = NOW(),
    updated_by = 'LOCAL_QUEUE_DEDUPE'
FROM (
  SELECT id,
         ROW_NUMBER() OVER (PARTITION BY filler_2, event_type ORDER BY id DESC) AS rn
  FROM loan_account_events_queue
  WHERE COALESCE(is_deleted,false) = false
    AND filler_2 IS NOT NULL
    AND filler_2 <> ''
) dup
WHERE q.id = dup.id
  AND dup.rn > 1;

-- verify: no live external ref may map to more than one queue row of a given type
SELECT filler_2, event_type, COUNT(*) AS live_rows
FROM loan_account_events_queue
WHERE COALESCE(is_deleted,false) = false
  AND filler_2 IS NOT NULL AND filler_2 <> ''
GROUP BY filler_2, event_type
HAVING COUNT(*) > 1
ORDER BY 3 DESC;
