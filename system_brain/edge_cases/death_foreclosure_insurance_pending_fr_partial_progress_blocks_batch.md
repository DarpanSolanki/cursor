## Death foreclosure insurance reverse feed `Pending for FR` can partially progress and block batch

### Symptom
- `deathForeclosureInsuranceJob` runs (or is triggered) but ends **FAILED**, and many eligible reverse-feed records are not processed.
- Loans remain in `DEATH_FORECLOSURE_FREEZE` (or DCF case state does not progress) even though inbound reverse-feed rows exist.

### Where
- **Accounting** schema/table: `mfi_accounting.death_foreclosure_insurance_staging_details`
- **Accounting** case table: `mfi_accounting.death_foreclosure_details`
- **Task** schema/tables: `mfi_task.task`, `mfi_task.task_attributes`, workflow tables.
- Batch: `deathForeclosureInsuranceJob` (business logic job, not the inbound CSV ingestion job).

### Root cause pattern (distributed partial progress)
Reverse-feed handling for insurer `claim_status = 'Pending for FR'` is a multi-step sequence that crosses service boundaries:

1) Accounting batch calls Task workflow update (`updateTaskWorkflow`) to push the task into rework/re-upload.
2) Accounting then persists accounting-side updates, including marking the reverse-feed staging row as handled (`death_foreclosure_insurance_staging_details.claim_status = 'REJECTED'`).

Because Task update is a separate microservice transaction, it can **commit** even if accounting later fails/rolls back the chunk. This produces partial progress:
- Task `updated_on` changes / stage moves,
- but insurance staging row remains `Pending for FR` + `INBOUND_SUCCESS` (still eligible),
- so the same rows are re-picked on every run.

### Why this blocks the whole job
`deathForeclosureInsuranceJob` is chunk/partition based. A fatal error for one record (e.g., task workflow update failure / config mismatch / task deleted) can fail the step/job, preventing processing of other eligible rows. Operationally: a small set of stuck `Pending for FR` rows can block closure/unfreeze for unrelated loans.

### Evidence to collect (DB)
1) Find eligible reverse-feed rows:
```sql
select id, death_foreclosure_details_id, loan_account_number, claim_status, inout_status, updated_on
from mfi_accounting.death_foreclosure_insurance_staging_details
where inout_status = 'INBOUND_SUCCESS'
  and claim_status not in ('PENDING','REJECTED','APPROVED')
order by id;
```

2) For stuck `Pending for FR` rows, verify they did not transition to handled state:
```sql
select id, death_foreclosure_details_id, claim_status, inout_status, updated_on
from mfi_accounting.death_foreclosure_insurance_staging_details
where id in (<staging_ids>)
order by id;
```

3) Check partial progress across services:
```sql
-- accounting case state
select id, task_id, death_foreclosure_status, updated_on
from mfi_accounting.death_foreclosure_details
where id in (<death_foreclosure_details_ids>);

-- task state
select id, task_type_version_id, current_status, is_deleted, updated_on
from mfi_task.task
where id in (<task_ids>);
```

### L0 (unblock) approach
Temporarily exclude known poison rows from being picked by marking their staging rows as handled (e.g., `claim_status='REJECTED'`) so the job can process the remaining eligible rows. This is a tactical unblock; root cause still needs fixing.

### L1/L2 (prevent recurrence) direction
- Make reverse-feed processing **per-record isolated**: persist failure_reason per row and continue processing others; do not fail the whole job for one record.
- Add explicit processing status/attempt tracking (or companion table) so eligibility is not inferred from insurer `claim_status` alone.
- Add null/guardrails in Task workflow update path so config holes do not crash (NPE) and failures are surfaced as clear config errors.

