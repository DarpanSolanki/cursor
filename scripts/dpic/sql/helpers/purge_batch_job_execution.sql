-- Local test only: allow re-running Spring Batch with the same job_time.
\set ON_ERROR_STOP on

DELETE FROM mfi_batch.batch_job_execution_context
WHERE job_execution_id IN (
  SELECT bje.job_execution_id
  FROM mfi_batch.batch_job_execution bje
  JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
  JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
  WHERE bji.job_name = :'job_name'
    AND p.parameter_name = 'job_time'
    AND p.parameter_value LIKE '%' || :'job_time' || '%'
);

DELETE FROM mfi_batch.batch_step_execution_context
WHERE step_execution_id IN (
  SELECT bse.step_execution_id
  FROM mfi_batch.batch_step_execution bse
  JOIN mfi_batch.batch_job_execution bje ON bje.job_execution_id = bse.job_execution_id
  JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
  JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
  WHERE bji.job_name = :'job_name'
    AND p.parameter_name = 'job_time'
    AND p.parameter_value LIKE '%' || :'job_time' || '%'
);

DELETE FROM mfi_batch.batch_step_execution
WHERE job_execution_id IN (
  SELECT bje.job_execution_id
  FROM mfi_batch.batch_job_execution bje
  JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
  JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
  WHERE bji.job_name = :'job_name'
    AND p.parameter_name = 'job_time'
    AND p.parameter_value LIKE '%' || :'job_time' || '%'
);

DELETE FROM mfi_batch.batch_job_execution_params
WHERE job_execution_id IN (
  SELECT bje.job_execution_id
  FROM mfi_batch.batch_job_execution bje
  JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
  JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
  WHERE bji.job_name = :'job_name'
    AND p.parameter_name = 'job_time'
    AND p.parameter_value LIKE '%' || :'job_time' || '%'
);

DELETE FROM mfi_batch.batch_job_execution
WHERE job_execution_id IN (
  SELECT bje.job_execution_id
  FROM mfi_batch.batch_job_execution bje
  JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
  JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
  WHERE bji.job_name = :'job_name'
    AND p.parameter_name = 'job_time'
    AND p.parameter_value LIKE '%' || :'job_time' || '%'
);

SELECT COUNT(*) AS remaining_executions
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
WHERE bji.job_name = :'job_name'
  AND p.parameter_name = 'job_time'
  AND p.parameter_value LIKE '%' || :'job_time' || '%';
