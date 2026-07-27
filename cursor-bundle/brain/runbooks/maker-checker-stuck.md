# Runbook — Maker-checker stuck

## Symptoms

- Loan stuck in `*_FREEZE` (e.g. `FORECLOSURE_FREEZE`, `PART_PREPAYMENT_FREEZE`, `LOAN_RESTR_FREEZE`).
- Master record (GL, holiday, interest setup, etc.) not visible after maker submit.
- approval `application` row stuck in PENDING; checker can't see it; or sees it but approve fails silently.

## First SQL

```sql
-- approval-side state for the loan / entity
SELECT * FROM mfi_approval.application
 WHERE target_payload LIKE '%' || ? || '%'   -- account_number / entity ref
 ORDER BY id DESC LIMIT 5;

-- maker-side audit trail
SELECT * FROM mfi_audit.audit_log
 WHERE entity_type LIKE 'SEND_FOR_APPROVAL_%'
   AND new_data LIKE '%' || ? || '%'
 ORDER BY created_on DESC LIMIT 10;

-- task linked to this approval
SELECT * FROM mfi_task.task
 WHERE attribute1 = (SELECT id::text FROM mfi_approval.application WHERE …)
    OR description LIKE '%' || ? || '%'
 ORDER BY id DESC LIMIT 10;
```

## Decision tree

### A. application status = PENDING, no checker action

1. Is the approval task created in `mfi_task.task`? If not, check use-case master config (which role is the checker, did the task creation step run?).
2. Is the checker user logged in / using the dashboard?
3. Push the operator. No system fix needed.

### B. application status = PENDING, no application row found

Maker-side flow failed before `submitApplication` ran. Check:
1. Maker-side audit for `SEND_FOR_APPROVAL_*` entry — is it there?
2. Application logs in the originating service around the maker submit timestamp.
3. Cause is usually a validator failure earlier in the maker pipeline. Operator needs to fix input data and re-submit.

### C. application status = APPROVED but state didn't change in target

The APPROVE branch fired but the target processor pipeline failed. Look at originating service log around the approve timestamp:
1. Find the Request name (= `application.target_api_name`).
2. Check for exceptions in that Request's APPROVE branch.
3. Common: idempotency violation in APPROVE — the maker-side branch already wrote a row that the APPROVE side tries to re-write but with stricter validation.

### D. Loan stuck in `*_FREEZE` indefinitely

Each FREEZE state is paired with an approval workflow. Check `mfi_approval.application` first:
- Status PENDING → see (A).
- Status APPROVED → see (C).
- No row → maker-side failed before submit; see (B).

**Do not directly UPDATE `loan_status` to ACTIVE.** Each FREEZE state has draft + workflow + (often) task + audit linkage. Direct DB writes leave orphans that future flows then re-encounter. The supported path is to either:
- Run the missing approval action (operator does it manually).
- If the approval row is corrupt, run `rejectApplication` first to release the FREEZE, then re-submit cleanly.

### E. RESUBMIT loop

If the maker keeps submitting and the checker keeps sending back for clarification, the application history shows multiple `SEND_FOR_APPROVAL_*` audit rows. The application_id stays the same; only `status` flips. Operator-process issue, not a system bug.

### F. Use-case master mis-configured

Symptoms:
- Wrong role can approve (or no one can).
- Maker action goes through without maker-checker (when expected).

Check:
1. `${maker_checker_enabled}` config in masterdata for the relevant use-case.
2. `getUseCaseDetails` on actor — does the use-case master have correct roles?
3. Use-case mapping to the Request — review `<API id="…_submitApplication">` declaration in originating Request.

## Code anchors

- approval Requests: [`trustt-platform-approval/deploy/application/orchestration/ServiceOrchestrationXML.xml`](../../trustt-platform-approval/deploy/application/orchestration/ServiceOrchestrationXML.xml)
- Maker pattern: every `createOrUpdate*` Request in accounting wraps with `${maker_checker_enabled}` Control
- Lifecycle: [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md)

## Related

- Maker-checker flow: [`../flows/maker-checker.md`](../flows/maker-checker.md)
- Approval service: [`../services/novopay-platform-approval.md`](../services/novopay-platform-approval.md)
- Task service: [`../services/novopay-platform-task.md`](../services/novopay-platform-task.md)
