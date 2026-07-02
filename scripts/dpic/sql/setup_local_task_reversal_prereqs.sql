-- Local prerequisites for loanAccountTransactionReversal INITIATE (createOrUpdateTask).
-- Task service entity expects columns that may be missing on older local mfi_task dumps.
\set ON_ERROR_STOP on

ALTER TABLE mfi_task.task_activity
  ADD COLUMN IF NOT EXISTS activity_initiated_user_role_code varchar(128) NULL;
