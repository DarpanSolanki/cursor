-- Mark updateLoanAccountDerivedFieldsJob execution as FAILED
-- Run both: step executions first, then job execution
-- Replace 49454 with your job_execution_id if different

-- 1. Mark all step executions for this job as FAILED
UPDATE batch_step_execution
SET status = 'FAILED',
    exit_code = 'FAILED',
    exit_message = 'Marked failed manually',
    end_time = CURRENT_TIMESTAMP
WHERE job_execution_id = 49454;

-- 2. Mark the job execution as FAILED
UPDATE batch_job_execution
SET status = 'FAILED',
    exit_code = 'FAILED',
    exit_message = 'Marked failed manually',
    end_time = CURRENT_TIMESTAMP
WHERE job_execution_id = 49454;
