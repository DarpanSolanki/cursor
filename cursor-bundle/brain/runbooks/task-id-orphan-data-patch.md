# Runbook — Data patch for orphan `task_id IS NULL` rows (foreclosure / disbursement cancellation)

> Companion to code fix `novopay-platform-accounting-v2 154b500c0` (branch `SDCP-fix-task-id-orphan-3.2.8.4`) — see the 2026-05-04 entry in [`../changelog/CHANGELOG.md`](../changelog/CHANGELOG.md). The code fix prevents new orphans; this runbook handles in-flight rows already in production.
> **READ-ONLY** from this workspace. The DBA executes the actual statements after team sign-off in a controlled window.

## Symptoms

- A loan account is stuck in `loan_status = FORECLOSURE_FREEZE` or `DISB_CNCL_FREEZE`.
- The corresponding row in `loan_account_part_prepayment_details` (foreclosure) or `loan_disbursement_cancellation_details` (cancellation) has `task_id IS NULL`.
- No task exists in the task service for that loan.
- Front-end users cannot proceed because the loan is frozen and no task is assigned.

## Identify affected rows (read-only — run this first)

```sql
-- Schema: mfi_accounting on production. Adjust schema name per tenant.
SET search_path TO mfi_accounting;

-- A. Foreclosure orphans
SELECT a.account_number,
       la.id          AS loan_account_id,
       la.loan_status,
       p.id           AS prepayment_id,
       p.task_id,
       p.task_status,
       p.prepayment_status,
       p.created_on,
       p.updated_on,
       p.created_by
  FROM loan_account la
  JOIN account a ON a.id = la.account_id
  JOIN loan_account_part_prepayment_details p ON p.account_id = a.id
 WHERE la.loan_status = 'FORECLOSURE_FREEZE'
   AND p.task_id IS NULL
   AND p.deleted = false
 ORDER BY p.created_on DESC;

-- B. Disbursement cancellation orphans
SELECT a.account_number,
       la.id           AS loan_account_id,
       la.loan_status,
       d.id            AS cancellation_id,
       d.task_id,
       d.task_status,
       d.cancellation_status,
       d.created_on,
       d.updated_on,
       d.created_by
  FROM loan_account la
  JOIN account a ON a.id = la.account_id
  JOIN loan_disbursement_cancellation_details d ON d.loan_account_id = la.id
 WHERE la.loan_status = 'DISB_CNCL_FREEZE'
   AND d.task_id IS NULL
   AND d.deleted = false
 ORDER BY d.created_on DESC;
```

## Determine the loan's pre-incident status

The loan needs to be reverted from `*_FREEZE` to whatever state it was in before the failed initiation. Read from `audit_log` for the most recent `loan_status` change on the same loan account:

```sql
-- Pre-FREEZE loan_status from the audit_log (one row per affected loan)
SELECT entity_id,
       old_data,                -- contains the prior loan_status
       new_data,                -- contains the FREEZE
       created_on,
       created_by
  FROM audit_log
 WHERE entity_type = 'LOAN_ACCOUNT'
   AND entity_id = ?            -- loan_account.id
   AND new_data LIKE '%FREEZE%'
 ORDER BY created_on DESC
 LIMIT 1;
```

For a typical case, the prior status is `ACTIVE`. **Confirm per loan; do not assume.** If the audit_log path is unavailable, ask the LMS team for the expected pre-incident state.

## Patch (one row at a time — DBA review required)

> **Do not run as a bulk UPDATE.** Each loan's pre-incident status must be confirmed individually. Wrap each loan's patch in a single transaction. A canonical pattern per loan:

```sql
BEGIN;

-- 1. Mark the orphan row as REJECTED so it doesn't continue to block the front-end.
--    Foreclosure:
UPDATE loan_account_part_prepayment_details
   SET task_status         = 'REJECTED',
       prepayment_status   = 'REJECTED',
       reject_reason       = 'SYSTEM_ROLLBACK',
       reject_notes        = '<incident-ref or ticket id>',
       deleted             = true,
       updated_by          = '<DBA-user-id>',
       updated_on          = NOW()
 WHERE id = ?
   AND task_id IS NULL
   AND deleted = false;

-- 1b. (cancellation equivalent — same shape against loan_disbursement_cancellation_details)
-- UPDATE loan_disbursement_cancellation_details SET cancellation_status = 'REJECTED', deleted = true, ...

-- 2. Revert the loan_status (PER-LOAN, value taken from audit_log step above).
UPDATE loan_account
   SET loan_status   = '<value-from-audit-log>',         -- typically 'ACTIVE'
       updated_by    = '<DBA-user-id>',
       updated_on    = NOW()
 WHERE id = ?
   AND loan_status IN ('FORECLOSURE_FREEZE','DISB_CNCL_FREEZE');

-- 3. Sanity check before commit
SELECT id, loan_status FROM loan_account WHERE id = ?;
SELECT id, task_id, task_status, deleted FROM loan_account_part_prepayment_details WHERE id = ?;
-- (or loan_disbursement_cancellation_details for cancellation)

-- If the rows look right:
COMMIT;
-- If anything is off:
-- ROLLBACK;
```

## SHG / JLG considerations

If the affected loan is an SHG / JLG **parent**, the corresponding **child** loans may also be in `FORECLOSURE_FREEZE` / `DISB_CNCL_FREEZE` because `updateLoanStatusForSHGProcessor` / `updateChildLoanAccountStatusProcessor` ran before the task call. The child loans need their `loan_status` reverted in the same transaction. Identify them:

```sql
SELECT id, account_id, loan_status, parent_loan_account_id
  FROM loan_account
 WHERE parent_loan_account_id = ?       -- the parent loan_account.id
   AND loan_status IN ('FORECLOSURE_FREEZE','DISB_CNCL_FREEZE');
```

For each child, repeat step 2 of the patch with the child's pre-incident status.

## What NOT to touch

- **Do not delete the orphan row.** Marking it `deleted = true, task_status = 'REJECTED'` keeps an audit trail and avoids breaking any reporting that joins on `loan_account_part_prepayment_details` / `loan_disbursement_cancellation_details`.
- **Do not invoke `deleteTask`** in the task service for these rows — there is no task in the task service to delete (that's the entire defect).
- **Do not run the patch in a different schema** before the patch is validated on a single low-risk loan in QA. Then prod, one-by-one.

## Pre-commit checklist (DBA / on-call)

- [ ] Code fix [`154b500c0`](https://github.com/khoslalabs/novopay-platform-accounting-v2/commit/154b500c0) is merged and deployed to prod **before** running this patch (otherwise new orphans can land while the patch is in progress).
- [ ] Per-loan affected-rows query (above) has been run, exported, and reviewed.
- [ ] Pre-incident status for each loan has been retrieved from `audit_log` (or confirmed with LMS team).
- [ ] Patch script is run **per loan** in a transaction, with `SELECT` verification before `COMMIT`.
- [ ] Affected user(s) / branch(es) are notified to retry the foreclosure / cancellation initiation after the patch.
- [ ] Post-patch monitoring window: confirm no new orphans appear in 24h (re-run identification queries).

## Related

- Code fix: 2026-05-04 entry in [`../changelog/CHANGELOG.md`](../changelog/CHANGELOG.md) (`novopay-platform-accounting-v2 154b500c0` on `SDCP-fix-task-id-orphan-3.2.8.4`)
- Lifecycle context: [`claude/accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md)
- Brain doc on the foreclosure flow: [`claude/flows/foreclosure-and-closure.md`](../flows/foreclosure-and-closure.md)
