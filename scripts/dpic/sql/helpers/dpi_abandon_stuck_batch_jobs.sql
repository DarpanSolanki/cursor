-- Local harness: abandon hung Spring Batch jobs so the next dpi_call_batch can run.
-- Marks STARTED / STARTING dpi* executions older than :older_than_seconds as FAILED.
\set ON_ERROR_STOP on

UPDATE mfi_batch.batch_job_execution bje
SET status = 'FAILED',
    exit_code = 'FAILED',
    exit_message = COALESCE(exit_message, '') || ' | abandoned by dpi_abandon_stuck_batch_jobs',
    end_time = NOW()
FROM mfi_batch.batch_job_instance bji
WHERE bji.job_instance_id = bje.job_instance_id
  AND bji.job_name LIKE 'dpi%'
  AND bje.status IN ('STARTED', 'STARTING', 'UNKNOWN')
  AND bje.create_time < NOW() - ((:older_than_seconds::int || ' seconds')::interval);

SELECT COUNT(*) AS abandoned
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name LIKE 'dpi%'
  AND bje.status = 'FAILED'
  AND COALESCE(bje.exit_message, '') LIKE '%abandoned by dpi_abandon_stuck_batch_jobs%'
  AND bje.end_time > NOW() - INTERVAL '1 minute';
