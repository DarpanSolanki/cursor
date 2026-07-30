-- Local DPIC harness: register DPI jobs via default (single-node) Spring Batch profile.
-- Parallel Kafka manager/worker path needs multinode infra — local boot leaves jobs unregistered.
-- Run before accounting restart (dpi_demo_fixture dpi_ensure_local_batch_registration).
\set ON_ERROR_STOP on

INSERT INTO mfi_batch.batch_job_parameter (job_id, param_name, param_value, param_type)
SELECT bj.id, 'is_multi_node', 'FALSE', 'String'
FROM mfi_batch.batch_job bj
WHERE LOWER(TRIM(bj.name)) IN (
    'dpiaccrualcalculation',
    'dpiaccrualbooking',
    'dpibilling'
)
AND NOT EXISTS (
    SELECT 1 FROM mfi_batch.batch_job_parameter existing
    WHERE existing.job_id = bj.id AND existing.param_name = 'is_multi_node'
);

UPDATE mfi_batch.batch_job_parameter bjp
SET param_value = 'FALSE'
FROM mfi_batch.batch_job bj
WHERE bj.id = bjp.job_id
  AND bjp.param_name = 'is_multi_node'
  AND LOWER(TRIM(bj.name)) IN (
      'dpiaccrualcalculation',
      'dpiaccrualbooking',
      'dpibilling'
  );
