-- Update force_grid_size to '6' and force_chunk to '50' for batch jobs
-- Jobs: updateLoanAccountDerivedFieldsJob, updateLoanAccountDerivedFieldsMonthlyJob
-- Run against your tenant schema (e.g. tenant_product.batch_job_parameter, tenant_product.batch_job)

-- UPDATE force_chunk = '50'
UPDATE batch_job_parameter
SET param_value = '50'
WHERE param_name = 'force_chunk'
  AND job_id IN (
    SELECT id FROM batch_job
    WHERE LOWER(TRIM(name)) IN (
      'updateloanaccountderivedfieldsjob',
      'updateloanaccountderivedfieldsmonthlyjob'
    )
  );

-- UPDATE force_grid_size = '6'
UPDATE batch_job_parameter
SET param_value = '6'
WHERE param_name = 'force_grid_size'
  AND job_id IN (
    SELECT id FROM batch_job
    WHERE LOWER(TRIM(name)) IN (
      'updateloanaccountderivedfieldsjob',
      'updateloanaccountderivedfieldsmonthlyjob'
    )
  );

-- Verification: check updated values
SELECT bj.name, bjp.param_name, bjp.param_value
FROM batch_job bj
JOIN batch_job_parameter bjp ON bjp.job_id = bj.id
WHERE LOWER(TRIM(bj.name)) IN (
  'updateloanaccountderivedfieldsjob',
  'updateloanaccountderivedfieldsmonthlyjob'
)
AND bjp.param_name IN ('force_chunk', 'force_grid_size')
ORDER BY bj.name, bjp.param_name;
