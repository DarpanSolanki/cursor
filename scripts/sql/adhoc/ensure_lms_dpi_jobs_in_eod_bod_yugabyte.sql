-- Idempotent: link LMS-DPIC / LMS-DPIB / LMS-DPIBL to LMS-EOD-BOD with priorities after interest (14–16).
-- DPI calc=17, booking=18, billing=19; LAR bumped to 20 (was 17).
-- Local Yugabyte only (mfi_batch schema).
\set ON_ERROR_STOP on

BEGIN;

WITH target AS (
  SELECT id AS group_id
  FROM mfi_batch.batch_group
  WHERE code = 'LMS-EOD-BOD' AND is_deleted = false
),
jobs AS (
  SELECT
    bj.id AS job_id,
    bj.code,
    CASE bj.code
      WHEN 'LMS-DPIC'  THEN '17'
      WHEN 'LMS-DPIB'  THEN '18'
      WHEN 'LMS-DPIBL' THEN '19'
      WHEN 'LMS-LAR'   THEN '20'
    END AS priority
  FROM mfi_batch.batch_job bj
  WHERE bj.code IN ('LMS-DPIC', 'LMS-DPIB', 'LMS-DPIBL', 'LMS-LAR')
    AND bj.is_deleted = false
)
UPDATE mfi_batch.batch_group_job bgj
SET group_id = target.group_id,
    priority = jobs.priority
FROM target, jobs
WHERE bgj.job_id = jobs.job_id;

INSERT INTO mfi_batch.batch_group_job (job_id, group_id, priority)
SELECT j.job_id, t.group_id, j.priority
FROM (
  SELECT
    bj.id AS job_id,
    CASE bj.code
      WHEN 'LMS-DPIC'  THEN '17'
      WHEN 'LMS-DPIB'  THEN '18'
      WHEN 'LMS-DPIBL' THEN '19'
      WHEN 'LMS-LAR'   THEN '20'
    END AS priority
  FROM mfi_batch.batch_job bj
  WHERE bj.code IN ('LMS-DPIC', 'LMS-DPIB', 'LMS-DPIBL', 'LMS-LAR')
    AND bj.is_deleted = false
) j
CROSS JOIN (
  SELECT id AS group_id
  FROM mfi_batch.batch_group
  WHERE code = 'LMS-EOD-BOD' AND is_deleted = false
) t
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_batch.batch_group_job x WHERE x.job_id = j.job_id
);

COMMIT;

SELECT bg.code AS group_code, bj.code AS job_code, bgj.priority
FROM mfi_batch.batch_group_job bgj
JOIN mfi_batch.batch_job bj ON bj.id = bgj.job_id
JOIN mfi_batch.batch_group bg ON bg.id = bgj.group_id
WHERE bg.code = 'LMS-EOD-BOD'
  AND bj.code IN ('LMS-IAC', 'LMS-IAP', 'LMS-LABJ', 'LMS-DPIC', 'LMS-DPIB', 'LMS-DPIBL', 'LMS-LAR')
ORDER BY CAST(bgj.priority AS INTEGER);
