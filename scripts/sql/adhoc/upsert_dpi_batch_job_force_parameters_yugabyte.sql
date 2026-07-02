-- Upsert force_* / multi-node batch parameters for DPI EOD jobs (aligned with interest/LMS jobs).
-- Schema: mfi_batch (change per tenant). Run after accounting-v2 deploy on envs where jobs already exist.
--
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
--     -f scripts/sql/adhoc/upsert_dpi_batch_job_force_parameters_yugabyte.sql
--
-- Jobs: dpiAccrualCalculation (LMS-DPIC), dpiAccrualBooking (LMS-DPIB), dpiBilling (LMS-DPIBL)
\set ON_ERROR_STOP on

INSERT INTO mfi_batch.batch_job_parameter (job_id, param_name, param_value, param_type)
SELECT bj.id, defs.param_name, defs.param_value, 'String'
FROM mfi_batch.batch_job bj
CROSS JOIN (
    VALUES
        ('minId', '1'),
        ('maxId', '1000'),
        ('force_chunk', '100'),
        ('force_grid_size', '50'),
        ('force_async', 'TRUE'),
        ('is_multi_node', 'TRUE')
) AS defs(param_name, param_value)
WHERE LOWER(TRIM(bj.name)) IN (
    'dpiaccrualcalculation',
    'dpiaccrualbooking',
    'dpibilling'
)
AND NOT EXISTS (
    SELECT 1
    FROM mfi_batch.batch_job_parameter existing
    WHERE existing.job_id = bj.id
      AND existing.param_name = defs.param_name
);

UPDATE mfi_batch.batch_job_parameter bjp
SET param_value = defs.param_value
FROM mfi_batch.batch_job bj,
     (VALUES
         ('force_chunk', '100'),
         ('force_grid_size', '50'),
         ('force_async', 'TRUE'),
         ('is_multi_node', 'TRUE')
     ) AS defs(param_name, param_value)
WHERE bj.id = bjp.job_id
  AND bjp.param_name = defs.param_name
  AND LOWER(TRIM(bj.name)) IN (
      'dpiaccrualcalculation',
      'dpiaccrualbooking',
      'dpibilling'
  );

SELECT bj.name AS job_name,
       bj.code,
       bjp.param_name,
       bjp.param_value
FROM mfi_batch.batch_job bj
LEFT JOIN mfi_batch.batch_job_parameter bjp ON bj.id = bjp.job_id
WHERE LOWER(TRIM(bj.name)) IN (
    'dpiaccrualcalculation',
    'dpiaccrualbooking',
    'dpibilling'
)
AND (bjp.param_name IS NULL OR bjp.param_name IN (
    'minId', 'maxId', 'force_chunk', 'force_grid_size', 'force_async', 'is_multi_node'
))
ORDER BY bj.name, bjp.param_name;
