-- Spring Batch step metrics for a completed job run (local perf analysis).
\set ON_ERROR_STOP on

SELECT bje.job_execution_id,
       bje.status,
       ROUND(EXTRACT(EPOCH FROM (bje.end_time - bje.start_time))::numeric, 2) AS job_duration_s,
       bse.step_name,
       bse.read_count,
       bse.write_count,
       bse.commit_count,
       bse.rollback_count,
       ROUND(EXTRACT(EPOCH FROM (bse.end_time - bse.start_time))::numeric, 2) AS step_duration_s
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
JOIN mfi_batch.batch_step_execution bse ON bse.job_execution_id = bje.job_execution_id
WHERE bji.job_name = :'job_name'
  AND p.parameter_name = 'job_time'
  AND p.parameter_value LIKE '%' || :'job_time' || '%'
  AND (:run_started::bigint = 0
       OR EXTRACT(EPOCH FROM bje.create_time)::bigint >= :run_started::bigint)
ORDER BY bje.job_execution_id DESC, bse.step_execution_id
LIMIT 30;
