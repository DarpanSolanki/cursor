-- INSERT parameters for updateLoanAccountDerivedFieldsJob and updateLoanAccountDerivedFieldsMonthlyJob
-- Parameters: force_async='TRUE', force_chunk='100', force_grid_size='12'
-- This script will INSERT the parameters only if they don't already exist

-- INSERT force_async = 'TRUE'
INSERT INTO batch_job_parameter (job_id, param_name, param_value, param_type)
SELECT 
    bj.id,
    'force_async',
    'TRUE',
    'String'
FROM batch_job bj
WHERE LOWER(TRIM(bj.name)) IN (
    'updateloanaccountderivedfieldsjob',
    'updateloanaccountderivedfieldsmonthlyjob'
)
AND NOT EXISTS (
    SELECT 1 FROM batch_job_parameter bjp 
    WHERE bjp.job_id = bj.id 
    AND bjp.param_name = 'force_async'
);

-- INSERT force_chunk = '100'
INSERT INTO batch_job_parameter (job_id, param_name, param_value, param_type)
SELECT 
    bj.id,
    'force_chunk',
    '100',
    'String'
FROM batch_job bj
WHERE LOWER(TRIM(bj.name)) IN (
    'updateloanaccountderivedfieldsjob',
    'updateloanaccountderivedfieldsmonthlyjob'
)
AND NOT EXISTS (
    SELECT 1 FROM batch_job_parameter bjp 
    WHERE bjp.job_id = bj.id 
    AND bjp.param_name = 'force_chunk'
);

-- INSERT force_grid_size = '12'
INSERT INTO batch_job_parameter (job_id, param_name, param_value, param_type)
SELECT 
    bj.id,
    'force_grid_size',
    '12',
    'String'
FROM batch_job bj
WHERE LOWER(TRIM(bj.name)) IN (
    'updateloanaccountderivedfieldsjob',
    'updateloanaccountderivedfieldsmonthlyjob'
)
AND NOT EXISTS (
    SELECT 1 FROM batch_job_parameter bjp 
    WHERE bjp.job_id = bj.id 
    AND bjp.param_name = 'force_grid_size'
);
