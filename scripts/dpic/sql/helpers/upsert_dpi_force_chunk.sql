-- Set runtime batch chunk for all DPI EOD jobs (platform reads force_chunk at job launch).
-- Usage: psql ... -v force_chunk=500 -f scripts/dpic/sql/helpers/upsert_dpi_force_chunk.sql

\set ON_ERROR_STOP on

UPDATE mfi_batch.batch_job_parameter bjp
SET param_value = :'force_chunk'
FROM mfi_batch.batch_job bj
WHERE bj.id = bjp.job_id
  AND bj.name IN ('dpiAccrualCalculation', 'dpiAccrualBooking', 'dpiBilling')
  AND bjp.param_name = 'force_chunk';

INSERT INTO mfi_batch.batch_job_parameter (job_id, param_name, param_value, param_type)
SELECT bj.id, 'force_chunk', :'force_chunk', 'INT'
FROM mfi_batch.batch_job bj
WHERE bj.name IN ('dpiAccrualCalculation', 'dpiAccrualBooking', 'dpiBilling')
  AND NOT EXISTS (
    SELECT 1 FROM mfi_batch.batch_job_parameter x
    WHERE x.job_id = bj.id AND x.param_name = 'force_chunk'
  );

SELECT bj.name, bjp.param_value AS force_chunk
FROM mfi_batch.batch_job bj
JOIN mfi_batch.batch_job_parameter bjp ON bjp.job_id = bj.id AND bjp.param_name = 'force_chunk'
WHERE bj.name LIKE 'dpi%'
ORDER BY bj.name;
