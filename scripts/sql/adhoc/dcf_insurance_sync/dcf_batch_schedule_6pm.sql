SELECT
    bg.code,
    bg.name,
    bs.id AS schedule_id,
    bs.cron_expression,
    bs.next_run_on,
    bs.status
FROM mfi_batch.batch_group bg
JOIN mfi_batch.batch_schedule bs
    ON bs.group_id = bg.id AND COALESCE(bs.is_deleted, false) = false
WHERE bg.code = 'INSURANCE_DETH_FRCLS'
  AND COALESCE(bg.is_deleted, false) = false;

UPDATE mfi_batch.batch_schedule bs
SET
    cron_expression = '0 30 11,14,17 * * *',
    updated_on      = NOW(),
    updated_by      = 'OPS_DCF_SYNC'
FROM mfi_batch.batch_group bg
WHERE bs.group_id = bg.id
  AND bg.code = 'INSURANCE_DETH_FRCLS'
  AND COALESCE(bg.is_deleted, false) = false
  AND COALESCE(bs.is_deleted, false) = false;

SELECT
    bg.code,
    bg.name,
    bs.id AS schedule_id,
    bs.cron_expression,
    bs.next_run_on,
    bs.status
FROM mfi_batch.batch_group bg
JOIN mfi_batch.batch_schedule bs
    ON bs.group_id = bg.id AND COALESCE(bs.is_deleted, false) = false
WHERE bg.code = 'INSURANCE_DETH_FRCLS'
  AND COALESCE(bg.is_deleted, false) = false;
